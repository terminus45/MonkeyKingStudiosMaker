"""Meshy.AI 3D model generation — stateless, lazy httpx import."""

import os
import tempfile
from typing import Optional

MESHY_BASE = "https://api.meshy.ai"

# Meshy rejects prompts longer than 800 characters (HTTP 400).
MAX_PROMPT_CHARS = 800


def _cap_prompt(prompt: str) -> str:
    """Trim a prompt to Meshy's 800-char limit at a word boundary."""
    p = (prompt or "").strip()
    if len(p) <= MAX_PROMPT_CHARS:
        return p
    cut = p[:MAX_PROMPT_CHARS]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.strip()


def _client_headers(api_key: Optional[str] = None) -> dict:
    key = api_key or os.environ.get("MESHY_API_KEY", "")
    if not key:
        raise RuntimeError(
            "MESHY_API_KEY is not set. "
            "Add it to your .env file or pass it per-request."
        )
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _check_response(resp, operation: str) -> dict:
    """Raise a clear RuntimeError for non-2xx responses."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed. Run: pip install httpx")

    if resp.status_code in (401, 403):
        raise RuntimeError(
            f"[{operation}] Meshy auth failed ({resp.status_code}). "
            "Check that your MESHY_API_KEY is valid."
        )
    if not resp.is_success:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise RuntimeError(
            f"[{operation}] Meshy returned HTTP {resp.status_code}: {detail}"
        )
    return resp.json()


def create_preview_task(prompt: str, *, api_key: Optional[str] = None) -> str:
    """Submit a text-to-3d preview job. Returns the task_id string."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed. Run: pip install httpx")

    headers = _client_headers(api_key)
    body = {
        "mode": "preview",
        "prompt": _cap_prompt(prompt),
        "art_style": "realistic",
        "should_remesh": True,
    }
    try:
        resp = httpx.post(
            f"{MESHY_BASE}/openapi/v2/text-to-3d",
            headers=headers,
            json=body,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"[create_preview_task] HTTP error: {exc}") from exc

    data = _check_response(resp, "create_preview_task")
    task_id = data.get("result")
    if not task_id:
        raise RuntimeError(
            f"[create_preview_task] Unexpected response (no 'result' key): {data}"
        )
    return task_id


def create_refine_task(preview_task_id: str, *, api_key: Optional[str] = None) -> str:
    """Submit a refine job for a completed preview. Returns the task_id string."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed. Run: pip install httpx")

    headers = _client_headers(api_key)
    body = {"mode": "refine", "preview_task_id": preview_task_id}
    try:
        resp = httpx.post(
            f"{MESHY_BASE}/openapi/v2/text-to-3d",
            headers=headers,
            json=body,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"[create_refine_task] HTTP error: {exc}") from exc

    data = _check_response(resp, "create_refine_task")
    task_id = data.get("result")
    if not task_id:
        raise RuntimeError(
            f"[create_refine_task] Unexpected response (no 'result' key): {data}"
        )
    return task_id


def get_task(task_id: str, *, api_key: Optional[str] = None) -> dict:
    """Fetch the current state of a task. Returns the full task dict."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed. Run: pip install httpx")

    headers = _client_headers(api_key)
    try:
        resp = httpx.get(
            f"{MESHY_BASE}/openapi/v2/text-to-3d/{task_id}",
            headers=headers,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"[get_task] HTTP error: {exc}") from exc

    return _check_response(resp, "get_task")


def download_model(url: str, dest_path: str) -> None:
    """Stream-download a model file to dest_path atomically (temp → rename)."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed. Run: pip install httpx")

    import os

    dir_path = os.path.dirname(dest_path)
    os.makedirs(dir_path, exist_ok=True)

    # Write to a temp file in the same directory, then atomically replace
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            try:
                with httpx.stream("GET", url, timeout=120, follow_redirects=True) as resp:
                    if not resp.is_success:
                        raise RuntimeError(
                            f"[download_model] HTTP {resp.status_code} downloading from {url}"
                        )
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        tmp_file.write(chunk)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"[download_model] HTTP error: {exc}") from exc
        os.replace(tmp_path, dest_path)
    except Exception:
        # Clean up the temp file if anything goes wrong
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
