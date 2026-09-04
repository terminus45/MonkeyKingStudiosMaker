import asyncio
import base64
import io
import json
import os
import re
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    BOOK_PDF_DIR,
    FIGURES_DIR,
    IMAGES_DIR,
    OUTPUT_DIR,
    PRACTICE_DIR,
    SAFETY_STYLE_SUFFIX,
)
import book_pdf
import comfy_generator
import gemini_generator
import image_backends
import local_figure_generator
import upscaler
import meshy_generator
import refine_compat
import practice_sheet as practice_sheet_mod
import practice_sheet_local as practice_sheet_local_mod
import languages
import settings_store

# Load server-side key store once at import time
settings_store.load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure output directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(PRACTICE_DIR, exist_ok=True)
    os.makedirs(BOOK_PDF_DIR, exist_ok=True)
    yield


app = FastAPI(title="BookBuilderBot", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).parent / "frontend"

# The frontend is served same-origin from this app, so no CORS is needed by
# default. Opt in to cross-origin access by setting CORS_ALLOW_ORIGINS to a
# comma-separated origin list (never a bare "*" alongside the unauthenticated,
# credit-spending endpoints).
_cors_origins = [
    o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    style_prompt: str = ""
    negative_prompt: Optional[str] = ""
    provider: str = "gemini"       # always "gemini"; field kept for stale-client compat
    gemini_model: str = "imagen-4.0-fast-generate-001"
    gemini_aspect_ratio: Optional[str] = None
    gemini_key: Optional[str] = None   # per-request override (mobile clients)
    width: int = 1024
    height: int = 1024
    seed: int = -1                 # local backends only: -1 draws (and records) one
    return_base64: bool = False
    # Legacy SD fields are accepted but ignored (pydantic default = ignore unknown)


class GenerateResponse(BaseModel):
    filename: str
    # The seed actually used (local backends), or None — cloud models expose no
    # seed and a repeat is a new roll. Was hardcoded -1 for years; None is the
    # honest value and no frontend reads this field.
    seed: Optional[int] = None
    loaded_model: Optional[str] = None
    image_base64: Optional[str] = None


def _safe_style(style: Optional[str]) -> str:
    """Append the child-safety guardrail to a Style Prompt (idempotent)."""
    s = (style or "").strip()
    if SAFETY_STYLE_SUFFIX.strip().lower() in s.lower():
        return s
    return (s + SAFETY_STYLE_SUFFIX).strip()

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/home.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api.md")
def api_docs_markdown():
    """Serve the agent-facing API reference (API.md) as raw markdown.

    This is the stable URL to hand to other agents/workflows — they fetch it
    and get the full reference in one shot. The human-readable, rendered page
    is /api.html (which fetches this)."""
    path = Path(__file__).parent / "API.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="API.md not found.")
    return FileResponse(path, media_type="text/markdown; charset=utf-8")


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    # The safety suffix is applied inside image_backends.generate(), which
    # knows the backend — cloud gets it, local does not.
    try:
        result = image_backends.generate(
            content_prompt=req.prompt,
            style_prompt=req.style_prompt,
            negative_prompt=req.negative_prompt or "",
            model_id=req.gemini_model,
            aspect_ratio=req.gemini_aspect_ratio,
            width=req.width,
            height=req.height,
            seed=req.seed,
            api_key=req.gemini_key or settings_store.get_key("GEMINI_API_KEY"),
        )
        filename = f"{uuid.uuid4().hex}.png"
        image_backends.save_result(result, filename)
        b64 = None
        if req.return_base64:
            buf = io.BytesIO()
            result.image.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
        return GenerateResponse(
            filename=filename,
            seed=result.seed,
            loaded_model=req.gemini_model,
            image_base64=b64,
        )
    except image_backends.UnknownModelError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Image generation as a job ────────────────────────────────────────────────
# POST /generate holds one HTTP connection open for the whole render. That is
# fine for a 5 s cloud call and fragile for a 3 min local one: backgrounding the
# tab (iOS Safari especially) or any idle proxy timeout drops the connection,
# and the result is lost even though the worker finished and wrote the PNG.
#
# Same shape as _figure_jobs / _practice_jobs / _book_pdf_jobs: submit, poll,
# and let the client persist the job id so navigation is survivable.
_image_jobs: dict[str, dict] = {}
_image_jobs_lock = threading.Lock()
_IMAGE_JOB_TTL_S = 3600          # finished jobs are pruned after an hour


def _image_job_update(job_id: str, patch: dict) -> None:
    with _image_jobs_lock:
        if job_id in _image_jobs:
            _image_jobs[job_id].update(patch)


def _image_job_read(job_id: str) -> Optional[dict]:
    with _image_jobs_lock:
        rec = _image_jobs.get(job_id)
        return dict(rec) if rec else None


def _image_jobs_prune() -> None:
    """Drop finished jobs past their TTL so the store can't grow without bound."""
    now = time.time()
    with _image_jobs_lock:
        for jid in [
            j for j, r in _image_jobs.items()
            if r.get("stage") in ("done", "error")
            and now - r.get("finished_at", now) > _IMAGE_JOB_TTL_S
        ]:
            _image_jobs.pop(jid, None)


def _gallery_save_record(filename: str, prompt: str, model: str) -> None:
    """Server-side gallery save, for jobs whose page may be gone at completion.
    Best-effort — mirrors the client's fire-and-forget semantics. Upserts by
    filename, so a page that IS still around saving the same image is a merge,
    never a duplicate."""
    try:
        path = _resolve_image_path(filename)
        record = {
            "id": uuid.uuid4().hex[:8],
            "filename": filename,
            "prompt": prompt,
            "story": None,
            "style_prompt": None,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta = gemini_generator.read_image_metadata(path) if path else None
        if meta:
            record["meta"] = meta
        _manifest_upsert_image(record)
    except Exception:
        pass


def _run_image_job(job_id: str, req: "GenerateRequest", api_key: Optional[str],
                   overrides: Optional[dict] = None,
                   gallery_prompt: Optional[str] = None) -> None:
    """Worker: generate one image and record the outcome on the job.

    `overrides` are per-call local-backend parameter overrides (regeneration).
    `gallery_prompt`, when set, makes the worker gallery-save the result
    itself — used when no client page will be around to do it.
    """
    try:
        _image_job_update(job_id, {"stage": "generating"})

        def on_step(step: int, total: int) -> None:
            _image_job_update(job_id, {
                "step": step,
                "total": total,
                "progress": int(step / max(total, 1) * 100),
            })

        result = image_backends.generate(
            content_prompt=req.prompt,
            style_prompt=req.style_prompt,
            negative_prompt=req.negative_prompt or "",
            model_id=req.gemini_model,
            aspect_ratio=req.gemini_aspect_ratio,
            width=req.width,
            height=req.height,
            seed=req.seed,
            api_key=api_key,
            on_step=on_step,
            local_overrides=overrides,
        )
        filename = f"{uuid.uuid4().hex}.png"
        image_backends.save_result(result, filename)
        if gallery_prompt is not None:
            _gallery_save_record(filename, gallery_prompt, req.gemini_model)
        _image_job_update(job_id, {
            "stage": "done", "progress": 100,
            "filename": filename, "seed": result.seed,
            "finished_at": time.time(),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        _image_job_update(job_id, {
            "stage": "error", "error": str(e), "finished_at": time.time(),
        })


@app.post("/generate/job")
def generate_job(req: GenerateRequest):
    """Start a generation and return a job id immediately.

    Prefer this over POST /generate for anything that might run long — it is
    the only path that survives the client navigating away.
    """
    # Validate the model here so a bad id is a synchronous 400 rather than an
    # error the caller only discovers by polling.
    if image_backends.backend_for(req.gemini_model) is None:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.gemini_model!r}")

    _image_jobs_prune()
    job_id = uuid.uuid4().hex
    with _image_jobs_lock:
        _image_jobs[job_id] = {
            "job_id": job_id, "stage": "queued", "progress": 0,
            "step": 0, "total": 0, "filename": None, "error": None,
            "model": req.gemini_model, "started_at": time.time(),
        }

    key = req.gemini_key or settings_store.get_key("GEMINI_API_KEY")
    # The worker gallery-saves the result itself: a long render (Krea 2 is
    # ~15+ min) routinely outlives the page that started it, and the page's
    # own fire-and-forget save then never fires. Upsert-by-filename means a
    # page that does survive merges its richer story/style in on top.
    threading.Thread(target=_run_image_job, args=(job_id, req, key),
                     kwargs={"gallery_prompt": req.prompt}, daemon=True).start()
    return {"job_id": job_id}


class RegenerateRequest(BaseModel):
    filename: str


@app.post("/regenerate/job")
def regenerate_job(req: RegenerateRequest):
    """Re-render an image from its own embedded recipe.

    Only offered for local images (meta.reproducible) — cloud models expose no
    seed, so a 'regenerate' there would just be a new roll. The stored
    parameters override current config: reproduction uses what the image was
    MADE with, not today's .env. The worker gallery-saves the result itself,
    since the Gallery page does not poll jobs.
    """
    if not re.fullmatch(r"[a-f0-9]{32}\.png", req.filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    path = _resolve_image_path(req.filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    meta = gemini_generator.read_image_metadata(path)
    if not meta or not meta.get("reproducible"):
        raise HTTPException(
            status_code=400,
            detail="No reproducible recipe is recorded in this image.")
    model_id = meta.get("model_id") or ""
    if image_backends.backend_for(model_id) not in ("local", "comfy"):
        raise HTTPException(
            status_code=400,
            detail=f"The model this image was made with ({model_id}) is no longer available.")

    hires = meta.get("hires") or {}
    gen_req = GenerateRequest(
        prompt=meta.get("prompt_final") or "",
        style_prompt="",                       # prompt_final is already composed
        negative_prompt=meta.get("negative_final") or "",
        gemini_model=model_id,
        width=meta.get("width") or 1024,
        height=meta.get("height") or 1024,
        seed=meta.get("seed", -1),
    )
    overrides = {
        "steps": meta.get("steps"),
        "guidance": meta.get("guidance"),
        "sampler": meta.get("sampler"),
        "negative_raw": True,                  # negative_final is already composed
        "hires_scale": (hires.get("scale") if hires.get("ran") else 1.0),
        "hires_denoise": hires.get("denoise"),
    }

    _image_jobs_prune()
    job_id = uuid.uuid4().hex
    with _image_jobs_lock:
        _image_jobs[job_id] = {
            "job_id": job_id, "stage": "queued", "progress": 0,
            "step": 0, "total": 0, "filename": None, "error": None,
            "model": model_id, "kind": "regenerate",
            "source": req.filename, "started_at": time.time(),
        }
    threading.Thread(
        target=_run_image_job,
        args=(job_id, gen_req, None, overrides, meta.get("prompt_final") or ""),
        daemon=True).start()
    return {"job_id": job_id}


class RefineRequest(BaseModel):
    filename: str                     # source image (any backend's output)
    instruction: str                  # what to change
    strength: float = 0.45            # 0.25 tweak / 0.45 change / 0.70 reimagine
    model_id: str                     # must be a local model
    seed: int = -1


def _run_refine_job(job_id: str, path: str, src_filename: str, prompt: str,
                    instruction: str, strength: float, model_id: str, seed: int) -> None:
    try:
        _image_job_update(job_id, {"stage": "generating"})

        def on_step(step: int, total: int) -> None:
            _image_job_update(job_id, {
                "step": step, "total": total,
                "progress": int(step / max(total, 1) * 100),
            })

        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            source = im.convert("RGB")

        result = image_backends.refine(
            source=source,
            prompt=prompt,
            instruction=instruction,
            parent_filename=src_filename,
            model_id=model_id,
            strength=strength,
            seed=seed,
            on_step=on_step,
        )
        filename = f"{uuid.uuid4().hex}.png"
        image_backends.save_result(result, filename)
        _image_job_update(job_id, {
            "stage": "done", "progress": 100,
            "filename": filename, "seed": result.seed,
            "finished_at": time.time(),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        _image_job_update(job_id, {
            "stage": "error", "error": str(e), "finished_at": time.time(),
        })


@app.get("/image/{filename}/refine-options")
def refine_options(filename: str):
    """Ranked refine-compatible models for a saved image.

    Read by the refine panel's model dropdown. The ranking comes from the
    generated-and-saved compatibility table (models/.refine_compat.json) —
    same-model first, then same-family; cross-family pairs appear only via an
    `allow` override in that table. The server never picks; this is the menu.
    """
    if not re.fullmatch(r"[a-f0-9]{32}\.png", filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    path = _resolve_image_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    meta = gemini_generator.read_image_metadata(path) or {}
    source_model = meta.get("model_id") if meta.get("backend") == "local" else None
    source_kind = refine_compat.kind_for_image(meta, path)
    opts = refine_compat.candidates(source_model, source_kind)

    names = {m["id"]: m["name"] for m in image_backends.list_models()}
    return {
        "source_model": source_model,
        "source_kind": source_kind,
        "options": [
            {"model_id": c["model_id"], "tier": c["tier"],
             "name": names.get(c["model_id"], c["model_id"])}
            for c in opts if c["model_id"] in names
        ],
    }


@app.post("/refine/job")
def refine_job(req: RefineRequest):
    """img2img refinement of a saved image, as a poll-able job.

    The refine prompt = the source's stored prompt_final (anchor, keeps the
    subject) + the user's instruction. Falls back to the gallery record's
    prompt for legacy images with no embedded metadata — they stay refinable.

    model_id is required and must be compatible with the image per the saved
    table — the server validates the caller's explicit choice, it never picks.
    """
    if not re.fullmatch(r"[a-f0-9]{32}\.png", req.filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    instruction = (req.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Refinement instruction is empty.")
    if image_backends.backend_for(req.model_id) != "local":
        raise HTTPException(
            status_code=400,
            detail="Refinement runs on-device — select an 'On this Mac' model in Settings.")
    path = _resolve_image_path(req.filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    src_meta = gemini_generator.read_image_metadata(path) or {}
    source_model = src_meta.get("model_id") if src_meta.get("backend") == "local" else None
    source_kind = refine_compat.kind_for_image(src_meta, path)
    allowed = {c["model_id"] for c in refine_compat.candidates(source_model, source_kind)}
    if req.model_id not in allowed:
        src_desc = source_model or f"a {source_kind or 'unknown'}-class image"
        raise HTTPException(
            status_code=400,
            detail=(f"{req.model_id} is not refine-compatible with this image "
                    f"(source: {src_desc}). Compatible models are listed by "
                    f"GET /image/{{filename}}/refine-options; to permit this pair "
                    f"anyway, add it to `overrides.allow` in models/.refine_compat.json."))

    meta = gemini_generator.read_image_metadata(path) or {}
    anchor = meta.get("prompt_final")
    if not anchor:
        # Legacy image — the manifest may still know its prompt.
        rec = next((r for r in _manifest_read(_IMAGES_MANIFEST)
                    if r.get("filename") == req.filename), None)
        anchor = (rec or {}).get("prompt") or ""
    prompt = f"{anchor}, {instruction}" if anchor else instruction

    _image_jobs_prune()
    job_id = uuid.uuid4().hex
    with _image_jobs_lock:
        _image_jobs[job_id] = {
            "job_id": job_id, "stage": "queued", "progress": 0,
            "step": 0, "total": 0, "filename": None, "error": None,
            "model": req.model_id, "kind": "refine",
            "source": req.filename, "started_at": time.time(),
        }
    threading.Thread(
        target=_run_refine_job,
        args=(job_id, path, req.filename, prompt, instruction,
              req.strength, req.model_id, req.seed),
        daemon=True).start()
    return {"job_id": job_id}


@app.get("/generate/status/{job_id}")
def generate_job_status(job_id: str):
    rec = _image_job_read(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job id.")
    return rec


# ── Upscaling (design-specs/image-upscaler.md) ────────────────────────────────

class UpscaleRequest(BaseModel):
    filename: str
    factor: int = 4


@app.get("/upscale/status")
def upscale_status():
    """Engine readiness + models on disk — the CG upscale row's gating."""
    ok, reason = upscaler.available()
    return {
        "available": ok, "reason": reason,
        "models": [m["key"] for m in upscaler.discover_models()] if ok else [],
        "factors": list(upscaler.FACTORS),
        "max_output_pixels": upscaler.MAX_OUTPUT_PIXELS,
    }


def _run_upscale_job(job_id: str, path: str, src_filename: str, factor: int) -> None:
    try:
        _image_job_update(job_id, {"stage": "upscaling"})

        def on_step(step: int, total: int) -> None:
            _image_job_update(job_id, {
                "step": step, "total": total,
                "progress": int(step / max(total, 1) * 100),
            })

        source_meta = gemini_generator.read_image_metadata(path) or {}
        key, why = upscaler.choose_model(source_meta)

        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            source = im.convert("RGB")
        image, meta = upscaler.upscale(source, factor, key, on_step=on_step)

        meta["parent_filename"] = src_filename
        meta["upscaler_choice"] = {"model": key, "source": why}
        meta["versions"] = image_backends._versions()
        meta["created_at"] = datetime.now(timezone.utc).isoformat()

        filename = f"{uuid.uuid4().hex}.png"
        image_backends.save_image(image, filename, meta=meta)
        # Worker-side gallery save: an upscale outliving its page must not be
        # orphaned. The page's own save merges via the filename upsert.
        # Prompt: the source's recipe, else its gallery record — an upscale of
        # an upscale has no prompt_final of its own, but the chain's root does,
        # and a card labeled "—" is unfindable.
        prompt = source_meta.get("prompt_final")
        if not prompt:
            rec = next((r for r in _manifest_read(_IMAGES_MANIFEST)
                        if r.get("filename") == src_filename), None)
            prompt = (rec or {}).get("prompt") or ""
        _gallery_save_record(filename, prompt, f"upscale-{factor}x")
        _image_job_update(job_id, {
            "stage": "done", "progress": 100,
            "filename": filename, "seed": None,
            "finished_at": time.time(),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        _image_job_update(job_id, {
            "stage": "error", "error": str(e), "finished_at": time.time(),
        })


@app.post("/upscale/job")
def upscale_job(req: UpscaleRequest):
    """Super-resolve a saved image by 2x/4x/8x, as a poll-able job.

    The upscaler model is chosen server-side from the source's own embedded
    recipe (sidecar declaration > checkpoint-name heuristic > backend
    default) — the client picks a factor, never a model. Results are new
    files with parent_filename lineage, like refine.
    """
    if not re.fullmatch(r"[a-f0-9]{32}\.png", req.filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    if req.factor not in upscaler.FACTORS:
        raise HTTPException(
            status_code=400,
            detail=f"factor must be one of {list(upscaler.FACTORS)}.")
    ok, reason = upscaler.available()
    if not ok:
        raise HTTPException(status_code=503, detail=reason)
    path = _resolve_image_path(req.filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    # Synchronous ceiling check — a doomed job should fail at submit.
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    if w * h * req.factor ** 2 > upscaler.MAX_OUTPUT_PIXELS:
        raise HTTPException(
            status_code=400,
            detail=(f"{req.factor}x of {w}x{h} exceeds the "
                    f"{upscaler.MAX_OUTPUT_PIXELS // 1_000_000} MP output limit."))

    _image_jobs_prune()
    job_id = uuid.uuid4().hex
    with _image_jobs_lock:
        _image_jobs[job_id] = {
            "job_id": job_id, "stage": "queued", "progress": 0,
            "step": 0, "total": 0, "filename": None, "error": None,
            "model": f"upscale-{req.factor}x", "kind": "upscale",
            "source": req.filename, "started_at": time.time(),
        }
    threading.Thread(
        target=_run_upscale_job,
        args=(job_id, path, req.filename, req.factor),
        daemon=True).start()
    return {"job_id": job_id}


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    """SSE endpoint — emits step progress then a final done event with filename/seed."""
    # Safety suffix is applied per-backend inside image_backends.generate().
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def run():
        try:
            # Progress is reported by the backend rather than assumed here: a
            # cloud call emits a single 0/1 step (as before), while a local
            # pipeline can report each denoising step. Same protocol either way.
            def on_step(step: int, total: int) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, {"step": step, "total": total})

            result = image_backends.generate(
                content_prompt=req.prompt,
                style_prompt=req.style_prompt,
                negative_prompt=req.negative_prompt or "",
                model_id=req.gemini_model,
                aspect_ratio=req.gemini_aspect_ratio,
                width=req.width,
                height=req.height,
                seed=req.seed,
                api_key=req.gemini_key or settings_store.get_key("GEMINI_API_KEY"),
                on_step=on_step,
            )
            filename = f"{uuid.uuid4().hex}.png"
            image_backends.save_result(result, filename)
            loop.call_soon_threadsafe(queue.put_nowait, {
                "done": True,
                "filename": filename,
                "seed": result.seed,
                "loaded_model": req.gemini_model,
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(e)})

    threading.Thread(target=run, daemon=True).start()

    async def event_stream():
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("done") or data.get("error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/image/{filename}/meta")
def get_image_metadata(filename: str):
    """Generation metadata embedded in a saved PNG, or {} for images that
    predate metadata (they must render as 'nothing recorded', not error)."""
    path = _resolve_image_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    return gemini_generator.read_image_metadata(path) or {}


@app.get("/models")
def list_models():
    """Every selectable image model, cloud and local, each tagged with a
    `backend`. This is the allow-list /generate validates against."""
    return {"models": image_backends.list_models()}


@app.get("/models/local/status")
def local_models_status():
    """Whether on-device generation is usable, and why not if it isn't.

    Lets Settings distinguish "extras not installed" from "no checkpoints
    found" instead of just showing an empty section.
    """
    local = image_backends._local_module()
    out = {"available": False, "reason": "Local backend module not present", "models": []}
    if local is not None:
        try:
            ok, reason = local.available()
            out = {
                "available": ok,
                "reason": reason,
                "device": local._device() if ok else None,
                "models": local.discover_models() if ok else [],
            }
        except Exception as e:
            out = {"available": False, "reason": str(e), "models": []}
    # Out-of-process backend status rides along so Settings can explain the
    # ComfyUI-served entries (or their absence) in the same breath.
    try:
        c_ok, c_reason = comfy_generator.available()
        out["comfy"] = {"available": c_ok, "reason": c_reason}
    except Exception as e:
        out["comfy"] = {"available": False, "reason": str(e)}
    return out


@app.get("/gemini/models")
def list_gemini_models():
    """Cloud models only — unchanged, so existing clients keep working.
    New callers should prefer GET /models."""
    return {"models": gemini_generator.GEMINI_MODELS}


class DecomposeRequest(BaseModel):
    concept: Optional[str] = ""
    style_suffix: Optional[str] = ""
    character: Optional[str] = ""          # shared main-character description
    language: Optional[str] = "zh"
    page_count: Optional[int] = 11
    include_art: Optional[bool] = True    # False = text-only book, no images/image_prompt
    anthropic_key: Optional[str] = None   # per-request override (mobile clients)


class CharData(BaseModel):
    c: str
    p: str


class PageData(BaseModel):
    page: int
    en: str
    image_prompt: str
    characters: Optional[list[CharData]] = None
    # zh variant
    zh: Optional[str] = None
    pinyin: Optional[str] = None
    # ja variant
    ja: Optional[str] = None
    romaji: Optional[str] = None
    # ko variant
    ko: Optional[str] = None
    romanization: Optional[str] = None


class DecomposeResponse(BaseModel):
    book_title_en: str
    pages: list[PageData]
    language: Optional[str] = "zh"
    include_art: bool = True
    # zh variant
    book_title_zh: Optional[str] = None
    book_title_pinyin: Optional[str] = None
    # ja variant
    book_title_ja: Optional[str] = None
    book_title_romaji: Optional[str] = None
    # ko variant
    book_title_ko: Optional[str] = None
    book_title_romanization: Optional[str] = None
    # language-neutral per-character title ruby (mirrors page characters[])
    book_title_characters: Optional[list[CharData]] = None


@app.get("/languages")
def list_languages():
    """Frontend-facing language registry (without system prompts)."""
    return {"languages": languages.public_metadata(), "default": languages.DEFAULT_LANGUAGE}


def _decompose_tool(
    lang: dict,
    *,
    min_pages: int = 11,
    max_pages: int = 11,
    include_image_prompt: bool = True,
) -> dict:
    """Build a tool definition that constrains Claude's output to the storybook schema
    for the given language. Using a tool guarantees structurally valid JSON — the API
    validates the input against this schema before returning.

    Parameters
    ----------
    lang : dict
        Language registry entry.
    min_pages / max_pages : int
        Enforced array size for the pages array and the per-page page integer maximum.
        Default 11/11 — the default storybook length used by /decompose.
    include_image_prompt : bool
        When False, image_prompt is omitted from the page schema (used by
        /recheck-readings, which preserves image_prompt client-side).
    """
    native_f  = lang["native_field"]
    reading_f = lang["reading_field"]
    title_n_f = lang["title_native_field"]
    title_r_f = lang["title_reading_field"]
    name = lang["english_name"]
    reading_label = lang["reading_label"]

    page_required = ["page", native_f, reading_f, "en", "characters"]
    page_properties: dict = {
        "page":     {"type": "integer", "minimum": 1, "maximum": max_pages},
        native_f:   {"type": "string", "description": f"Page sentence in {name}"},
        reading_f:  {"type": "string", "description": reading_label},
        "en":       {"type": "string", "description": "English translation"},
        "characters": {
            "type": "array",
            "description": "Per-character (or per-token) entries with reading annotations.",
            "items": {
                "type": "object",
                "properties": {
                    "c": {"type": "string"},
                    "p": {"type": "string"},
                },
                "required": ["c", "p"],
                "additionalProperties": False,
            },
        },
    }
    if include_image_prompt:
        page_properties["image_prompt"] = {"type": "string"}
        page_required.append("image_prompt")

    return {
        "name": "submit_storybook",
        "description": f"Submit the decomposed {max_pages}-page {name}-English storybook.",
        "input_schema": {
            "type": "object",
            "properties": {
                title_n_f:       {"type": "string", "description": f"Book title in {name}"},
                title_r_f:       {"type": "string", "description": f"Book title {reading_label.lower()}"},
                "book_title_en": {"type": "string", "description": "Book title in English"},
                "book_title_characters": {
                    "type": "array",
                    "description": "Per-character reading annotations for the book title (same alignment as page characters).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "c": {"type": "string"},
                            "p": {"type": "string"},
                        },
                        "required": ["c", "p"],
                        "additionalProperties": False,
                    },
                },
                "pages": {
                    "type": "array",
                    "minItems": min_pages,
                    "maxItems": max_pages,
                    "items": {
                        "type": "object",
                        "properties": page_properties,
                        "required": page_required,
                    },
                },
            },
            "required": [title_n_f, title_r_f, "book_title_en", "pages"],
        },
    }


def run_decompose(
    concept: Optional[str],
    style_suffix: Optional[str],
    character: Optional[str],
    language: Optional[str],
    page_count: Optional[int],
    api_key: str,
    include_art: bool = True,
) -> dict:
    """Core /decompose pipeline (Claude call + forced-tool schema). Extracted
    from decompose() (behavior-preserving) so the /book-pdf worker can reuse
    it without going through the HTTP layer. Everything here runs AFTER the
    caller has already resolved the API key and validated concept/character
    aren't both empty.

    include_art : bool
        True (default) = illustrated book — page_count is silently clamped to
        {11, 15, 19} and image_prompt is required in the schema, exactly
        today's behavior. False = text-only book — page_count is defensively
        clamped to 1..30 (the route is expected to have already strictly
        validated this range) and image_prompt is omitted from the schema.
    """
    lang = languages.get(language)
    # Clamp page_count to the allowed set early — must be defined before invention
    # instruction and tool build reference it.
    if include_art:
        page_count = page_count if page_count in (11, 15, 19) else 11
    else:
        page_count = page_count if page_count and 1 <= page_count <= 30 else 11
    client = anthropic.Anthropic(api_key=api_key)

    concept_text = (concept or "").strip()
    character_text = (character or "").strip()

    if concept_text:
        # Concept provided — use it directly as the story seed
        user_content = concept_text
    else:
        # No concept — invent a plot from the character description alone
        user_content = (
            f"Create an original, warm, age-appropriate {page_count}-page picture-book story "
            "for ages 4–8 with a clear beginning, middle, and end, and a fitting title. "
            "Invent a simple plot that suits the following main character."
        )

    if character_text:
        user_content += (
            f"\n\nThe protagonist is: {character_text}. "
            "This same character must appear on every page and be described "
            "CONSISTENTLY (same appearance, outfit, colors) in every image_prompt, "
            "using visual description only — never the character's name."
        )
    safe_style = _safe_style(style_suffix)
    user_content += f"\n\nApply this visual style to every image_prompt: {safe_style}"
    # Unconditional count instruction — applies to both the concept and character-only paths.
    user_content += f"\n\nDecompose this into exactly {page_count} pages, numbered 1 to {page_count}."

    tool = _decompose_tool(lang, min_pages=page_count, max_pages=page_count, include_image_prompt=include_art)

    # Scale output-token budget with page count — a 30-page text-only book's
    # JSON payload can exceed the flat 16384 default used for the 11/15/19 art path.
    max_tokens = max(16384, page_count * 700)

    try:
        with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": lang["prompt"],
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user_content}],
            timeout=180,
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    # Prefer the tool_use block (structurally validated). Fall back to text parsing
    # only if the model somehow ignored the forced tool_choice.
    data = None
    for block in msg.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            data = block.input
            break

    if data is None:
        raw = ""
        for block in msg.content:
            if block.type == "text":
                raw = block.text
                break
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
        raw = re.sub(r"\n?```$", "", raw.strip())
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Claude did not return a tool call and text was unparseable: {e}\n\nRaw output:\n{raw}",
            )

    data["language"] = lang["code"]
    data["include_art"] = include_art
    return data


@app.post("/decompose", response_model=DecomposeResponse)
def decompose(req: DecomposeRequest):
    api_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    if not (req.concept or "").strip() and not (req.character or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Provide a Character Description or a Story Prompt.",
        )

    if not req.include_art and not (1 <= (req.page_count or 0) <= 30):
        raise HTTPException(
            status_code=400,
            detail="page_count must be between 1 and 30 for text-only books.",
        )

    data = run_decompose(
        concept=req.concept,
        style_suffix=req.style_suffix,
        character=req.character,
        language=req.language,
        page_count=req.page_count,
        api_key=api_key,
        include_art=req.include_art,
    )
    if not req.include_art:
        # Bypass response_model so image_prompt is genuinely absent (not null) —
        # mirrors /recheck-readings's existing no-response_model precedent.
        return JSONResponse(content=data)
    return data


# ── Re-check readings ──────────────────────────────────────────────────────

class RecheckRequest(BaseModel):
    language: Optional[str] = "zh"
    pages: list[PageData]
    anthropic_key: Optional[str] = None
    # language-neutral title keys for re-aligning book_title_characters
    book_title_native: Optional[str] = None
    book_title_reading: Optional[str] = None
    book_title_characters: Optional[list[CharData]] = None


def run_recheck(
    language: Optional[str],
    pages: list,
    api_key: str,
    book_title_native: Optional[str] = None,
    book_title_reading: Optional[str] = None,
    book_title_characters: Optional[list] = None,
) -> dict:
    """Core /recheck-readings pipeline. Extracted from recheck_readings()
    (behavior-preserving) so the /book-pdf worker can reuse it directly.

    `pages` accepts either PageData pydantic instances (as the HTTP route
    receives them) or plain dicts (as the /book-pdf worker holds them,
    straight out of run_decompose's Claude response) — each entry is
    normalized via model_dump()/dict() before use. Same for the entries of
    each page's `characters` list and of `book_title_characters`.
    """
    lang = languages.get(language)
    client = anthropic.Anthropic(api_key=api_key)

    n = len(pages)
    tool = _decompose_tool(lang, min_pages=n, max_pages=n, include_image_prompt=False)

    def _as_dict(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return dict(obj)

    # Build a lean user message: strip image_prompt to save output tokens.
    native_f  = lang["native_field"]
    reading_f = lang["reading_field"]
    stripped_pages = []
    for pg in pages:
        pg_d = _as_dict(pg)
        entry: dict = {
            "page": pg_d["page"],
            native_f:  pg_d.get(native_f)  or "",
            reading_f: pg_d.get(reading_f) or "",
            "en": pg_d["en"],
        }
        chars = pg_d.get("characters")
        if chars:
            entry["characters"] = [
                {"c": _as_dict(ch)["c"], "p": _as_dict(ch)["p"]} for ch in chars
            ]
        stripped_pages.append(entry)

    # Build the payload — inject title when present (B3: omit entirely if title is blank)
    payload: dict = {"pages": stripped_pages}
    if book_title_native and book_title_native.strip():
        title_native_f  = lang["title_native_field"]
        title_reading_f = lang["title_reading_field"]
        title_obj: dict = {
            title_native_f:  book_title_native,
            title_reading_f: book_title_reading or "",
            "book_title_characters": (
                [_as_dict(c) for c in book_title_characters]
                if book_title_characters else []
            ),
        }
        payload["book_title"] = title_obj

    user_content = (
        "Here is the existing storybook. "
        "Correct any reading/tone-mark errors and re-align the characters[] arrays. "
        "Do NOT change meaning, vocabulary, or page count. "
        "You do NOT need to return image_prompt.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )

    try:
        with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=16384,
            system=[
                {
                    "type": "text",
                    "text": languages.correction_prompt(lang),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user_content}],
            timeout=180,
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    # Extract tool_use block (same fallback as /decompose)
    data = None
    for block in msg.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            data = block.input
            break

    if data is None:
        raw = ""
        for block in msg.content:
            if block.type == "text":
                raw = block.text
                break
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
        raw = re.sub(r"\n?```$", "", raw.strip())
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Claude did not return a tool call and text was unparseable: {e}\n\nRaw output:\n{raw}",
            )

    data["language"] = lang["code"]
    # Return plain dict — image_prompt absent so we don't force DecomposeResponse validation
    return data


@app.post("/recheck-readings")
def recheck_readings(req: RecheckRequest):
    """Re-run Claude over an existing story to correct tone marks / romanization
    and re-align characters[].  Returns the same page array (native, reading,
    characters, en) with corrections applied.  image_prompt is NOT returned —
    the frontend preserves the existing value client-side."""
    api_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    return run_recheck(
        language=req.language,
        pages=req.pages,
        api_key=api_key,
        book_title_native=req.book_title_native,
        book_title_reading=req.book_title_reading,
        book_title_characters=req.book_title_characters,
    )


# Accept HEAD as well as GET — the Book Builder restore flow probes each saved
# page image with a HEAD request before displaying it. (Starlette no longer
# auto-adds HEAD to GET routes, so it must be declared explicitly.)
def _resolve_image_path(filename: str) -> Optional[str]:
    """Return the on-disk path of an image, or None if it isn't found.

    Generated/uploaded images now live in IMAGES_DIR; older images and any
    recovered originals live at the top level of OUTPUT_DIR. Callers pass a
    filename that has already been validated against the [a-f0-9]{32}.png
    allow-list, so joining either directory is traversal-safe.
    """
    for base in (IMAGES_DIR, OUTPUT_DIR):
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return path
    return None


@app.api_route("/image/{filename}", methods=["GET", "HEAD"])
def get_image(filename: str):
    if not re.fullmatch(r"[a-f0-9]{32}\.png", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _resolve_image_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Accept an uploaded image file, save it to IMAGES_DIR, return the filename."""
    data = await file.read()
    # Re-encode through Pillow to normalise format and strip metadata
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
    filename = f"{uuid.uuid4().hex}.png"
    os.makedirs(IMAGES_DIR, exist_ok=True)
    img.save(os.path.join(IMAGES_DIR, filename))
    return {"filename": filename}


# ── Settings / key store ─────────────────────────────────────────────────────

class KeysUpdateRequest(BaseModel):
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    MESHY_API_KEY: Optional[str] = None


@app.get("/settings/keys")
def get_settings_keys():
    """Return masked status for all managed API keys."""
    return settings_store.status()


@app.post("/settings/keys")
def post_settings_keys(req: KeysUpdateRequest):
    """Update one or more API keys. Empty string clears the stored value."""
    updates = {}
    if req.ANTHROPIC_API_KEY is not None:
        updates["ANTHROPIC_API_KEY"] = req.ANTHROPIC_API_KEY
    if req.GEMINI_API_KEY is not None:
        updates["GEMINI_API_KEY"] = req.GEMINI_API_KEY
    if req.MESHY_API_KEY is not None:
        updates["MESHY_API_KEY"] = req.MESHY_API_KEY
    if updates:
        settings_store.set_keys(updates)
    return settings_store.status()


# ── Gallery ───────────────────────────────────────────────────────────────────

GALLERY_DIR = Path(__file__).parent / "gallery"
GALLERY_DIR.mkdir(exist_ok=True)

_SAFE_ID = re.compile(r'^[a-z0-9_-]+$')

# Names of manifest files that must not be treated as book JSON by the glob
_MANIFEST_NAMES = {"images.json", "models.json"}

# Paths to the two manifests
_IMAGES_MANIFEST = GALLERY_DIR / "images.json"
_MODELS_MANIFEST = GALLERY_DIR / "models.json"

# Single lock protecting both manifests
_manifest_lock = threading.Lock()


def _manifest_read(path: Path) -> list:
    """Return list from a JSON manifest, or [] if missing or corrupt."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _manifest_append(path: Path, record: dict) -> None:
    """Append *record* to *path* atomically under _manifest_lock."""
    with _manifest_lock:
        items = _manifest_read(path)
        items.append(record)
        _manifest_write(path, items)


def _manifest_delete(path: Path, item_id: str) -> bool:
    """Remove the item with matching 'id' from *path*. Returns True if removed."""
    with _manifest_lock:
        items = _manifest_read(path)
        new_items = [r for r in items if r.get("id") != item_id]
        if len(new_items) == len(items):
            return False
        _manifest_write(path, new_items)
        return True


def _manifest_upsert_image(record: dict) -> dict:
    """Append to the images manifest, or merge into the record already holding
    this filename.

    A generation job is gallery-saved from two places on purpose: the worker
    (so a render that outlives its page — a 15-minute Krea 2 job, a closed
    tab — is never orphaned) and the polling page (which knows story/style
    the server doesn't). Filename is the identity; the merge fills only the
    fields the existing record lacks, so whichever save lands second adds
    information instead of a duplicate card."""
    with _manifest_lock:
        items = _manifest_read(_IMAGES_MANIFEST)
        for existing in items:
            if existing.get("filename") == record.get("filename"):
                for k, v in record.items():
                    if k not in ("id", "created_at") and v and not existing.get(k):
                        existing[k] = v
                _manifest_write(_IMAGES_MANIFEST, items)
                return existing
        items.append(record)
        _manifest_write(_IMAGES_MANIFEST, items)
        return record


def _manifest_write(path: Path, items: list) -> None:
    """Write *items* to *path* atomically (temp + os.replace). Caller holds _manifest_lock."""
    dir_path = str(path.parent)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_gallery_meta(path: Path) -> dict:
    data   = json.loads(path.read_text(encoding="utf-8"))
    story  = data.get("story", {})
    images = data.get("generated_images", {})
    # Language is stored on the story (or on the project root for older saves).
    # Fall back to "zh" for legacy books written before multi-language support.
    lang_code = story.get("language") or data.get("language") or "zh"
    lang = languages.get(lang_code)
    return {
        "id":               path.stem,
        "language":         lang["code"],
        "title_native":     story.get(lang["title_native_field"], ""),
        "title_reading":    story.get(lang["title_reading_field"], ""),
        "title_en":         story.get("book_title_en", "Untitled"),
        "saved_at":         data.get("saved_at", ""),
        "page_count":       len(story.get("pages", [])),
        "images_generated": len(images),
        "cover_image":      images.get("1") or images.get(1),
        "include_art":      story.get("include_art", True),
    }


@app.get("/gallery")
def list_gallery():
    books = []
    for p in sorted(GALLERY_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        if p.name in _MANIFEST_NAMES:
            continue
        try:
            books.append(_read_gallery_meta(p))
        except Exception:
            continue
    return {"books": books}


@app.post("/gallery")
async def save_to_gallery(request: Request):
    project = await request.json()
    story   = project.get("story", {})
    title   = story.get("book_title_en", "untitled")
    slug    = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')[:40]
    book_id = f"{slug}_{uuid.uuid4().hex[:8]}"

    project.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
    (GALLERY_DIR / f"{book_id}.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"id": book_id, "saved": True}


# ── Gallery images manifest (declare BEFORE /gallery/{book_id}) ───────────────

class GalleryImageRequest(BaseModel):
    filename: str
    prompt: Optional[str] = None
    story: Optional[str] = None
    style_prompt: Optional[str] = None
    model: Optional[str] = None


@app.post("/gallery/image")
def gallery_image_add(req: GalleryImageRequest):
    """Register a generated image in the images manifest."""
    if not re.fullmatch(r"[a-f0-9]{32}\.png", req.filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    path = _resolve_image_path(req.filename)
    if path is None:
        raise HTTPException(status_code=400, detail="Image file not found in output directory.")
    record = {
        "id": uuid.uuid4().hex[:8],
        "filename": req.filename,
        "prompt": req.prompt,
        "story": req.story,
        "style_prompt": req.style_prompt,
        "model": req.model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Enrich from the PNG's own embedded metadata rather than trusting (or
    # requiring) the client to echo it back — the file is the source of truth,
    # and older images without a chunk simply don't get a meta key.
    meta = gemini_generator.read_image_metadata(path)
    if meta:
        record["meta"] = meta
    return _manifest_upsert_image(record)


@app.get("/gallery/images")
def gallery_images_list():
    """List all saved images, newest first."""
    items = _manifest_read(_IMAGES_MANIFEST)
    return {"images": list(reversed(items))}


@app.delete("/gallery/image/{item_id}")
def gallery_image_delete(item_id: str):
    """Remove an image entry from the manifest (does not delete the PNG file)."""
    if not re.fullmatch(r"[a-f0-9]{8}", item_id):
        raise HTTPException(status_code=400, detail="Invalid image id format.")
    removed = _manifest_delete(_IMAGES_MANIFEST, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Image entry not found.")
    return {"deleted": True}


# ── Gallery models manifest (declare BEFORE /gallery/{book_id}) ───────────────

@app.get("/gallery/models")
def gallery_models_list():
    """List all saved 3D models, newest first."""
    items = _manifest_read(_MODELS_MANIFEST)
    return {"models": list(reversed(items))}


@app.delete("/gallery/model/{item_id}")
def gallery_model_delete(item_id: str):
    """Remove a model entry from the manifest."""
    if not re.fullmatch(r"[a-f0-9]{8}", item_id):
        raise HTTPException(status_code=400, detail="Invalid model id format.")
    removed = _manifest_delete(_MODELS_MANIFEST, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Model entry not found.")
    return {"deleted": True}


@app.get("/gallery/{book_id}")
def get_gallery_book(book_id: str):
    if not _SAFE_ID.match(book_id):
        raise HTTPException(status_code=400, detail="Invalid book ID.")
    path = GALLERY_DIR / f"{book_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Book not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.delete("/gallery/{book_id}")
def delete_gallery_book(book_id: str):
    if not _SAFE_ID.match(book_id):
        raise HTTPException(status_code=400, detail="Invalid book ID.")
    path = GALLERY_DIR / f"{book_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Book not found.")
    path.unlink()
    return {"deleted": True}


# ── Figure Maker ──────────────────────────────────────────────────────────────

# In-memory job store keyed by job_id
_figure_jobs: dict[str, dict] = {}
_figure_jobs_lock = threading.Lock()


def _job_create(job_id: str) -> dict:
    record = {
        "job_id": job_id,
        "stage": "prompting",
        "progress": 0,
        "enhanced_prompt": None,
        "glb_filename": None,
        "report": None,
        "filament": None,
        "error": None,
    }
    with _figure_jobs_lock:
        _figure_jobs[job_id] = record
    return record


def _job_update(job_id: str, patch: dict) -> None:
    with _figure_jobs_lock:
        if job_id in _figure_jobs:
            _figure_jobs[job_id].update(patch)


def _job_read(job_id: str) -> Optional[dict]:
    with _figure_jobs_lock:
        rec = _figure_jobs.get(job_id)
        return dict(rec) if rec else None


# ── Claude helpers for figure maker ──────────────────────────────────────────

_ENHANCE_SYSTEM = (
    "You are a 3D prompt engineer for a kid-friendly 3D figure generator. "
    "Your job is to rewrite a child's idea into a strong Meshy.AI text-to-3D prompt. "
    "Rules you MUST follow:\n"
    "1. The enhanced prompt MUST begin with the child's own words "
    "(fix obvious spelling mistakes, then naturally expand the idea).\n"
    "2. Add vivid but child-appropriate details: surface texture, colors, key features.\n"
    "3. The enhanced prompt MUST end EXACTLY with: "
    "\"under 6 inches / 152 mm tall, compact and chunky proportions\"\n"
    "4. Keep the prompt under 200 words. Be creative but stay true to the child's concept."
)

_REPORT_SYSTEM = (
    "You are a friendly print-report assistant for a kid's 3D model generator. "
    "Given a description of a 3D model, write a short, encouraging print report "
    "for the child and their parent. "
    "Focus on fun aspects: what it will look like when printed, any interesting features, "
    "and a simple printing tip. Keep it warm and accessible — no jargon."
)


def _enhance_figure_prompt(child_prompt: str, api_key: str,
                           style: str = "", story: str = "") -> str:
    """Call Claude to rewrite child_prompt into a strong Meshy prompt.

    style/story are optional shared inputs woven into the user content as
    additional guidance; the size constraint stays enforced by _ENHANCE_SYSTEM.
    """
    tool = {
        "name": "submit_prompt",
        "description": "Submit the enhanced 3D print prompt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "enhanced_prompt": {
                    "type": "string",
                    "description": (
                        "The enhanced Meshy prompt. Must start with the child's words "
                        "and end with 'under 6 inches / 152 mm tall, compact and chunky proportions'. "
                        "Keep it concise — under 700 characters total."
                    ),
                }
            },
            "required": ["enhanced_prompt"],
            "additionalProperties": False,
        },
    }
    parts = [child_prompt.strip()]
    if style and style.strip():
        parts.append(f"Visual style: {style.strip()}.")
    if story and story.strip():
        parts.append(f"Context / pose / accessories: {story.strip()}.")
    user_msg = "\n".join(parts)

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_ENHANCE_SYSTEM,
        tools=[tool],
        tool_choice={"type": "tool", "name": "submit_prompt"},
        messages=[{"role": "user", "content": user_msg}],
        timeout=30,
    )
    for block in msg.content:
        if block.type == "tool_use" and block.name == "submit_prompt":
            return block.input["enhanced_prompt"]
    raise RuntimeError("Claude did not return a tool_use block for prompt enhancement.")


def _make_print_report(enhanced_prompt: str, api_key: str) -> dict:
    """Call Claude to generate a kid/parent-friendly print report. Degrades gracefully."""
    tool = {
        "name": "submit_report",
        "description": "Submit the print report fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "2-3 sentences, kid and parent friendly, about printing this model.",
                },
                "filament": {
                    "type": "string",
                    "description": "Short filament suggestion, e.g. 'PLA · Bright Orange'.",
                },
            },
            "required": ["report", "filament"],
            "additionalProperties": False,
        },
    }
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_REPORT_SYSTEM,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_report"},
            messages=[{"role": "user", "content": enhanced_prompt}],
            timeout=30,
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == "submit_report":
                return {
                    "report": block.input.get("report", "Your model is ready to print!"),
                    "filament": block.input.get("filament", "PLA"),
                }
    except Exception:
        pass  # degrade gracefully
    return {"report": "Your model is ready to print!", "filament": "PLA"}


# ── Figure job worker ─────────────────────────────────────────────────────────

_POLL_INTERVAL = 4       # seconds between Meshy status polls
_MAX_POLL_PER_STAGE = 150  # ~10 min per stage (150 × 4 s = 600 s)


def _poll_until_done(task_id: str, job_id: str, meshy_key: str,
                     progress_start: int, progress_end: int,
                     getter=meshy_generator.get_task) -> dict:
    """Poll a Meshy task until SUCCEEDED. Map progress into [progress_start, progress_end].
    Raises RuntimeError on FAILED/CANCELED or timeout.
    getter is the function used to fetch task state — defaults to get_task (text-to-3D).
    Pass meshy_generator.get_image_to_3d_task for image-to-3D jobs."""
    import time

    for attempt in range(_MAX_POLL_PER_STAGE):
        time.sleep(_POLL_INTERVAL)
        task = getter(task_id, api_key=meshy_key)
        status = task.get("status", "")
        raw_pct = task.get("progress", 0)  # 0–100 from Meshy

        # Map raw_pct to our band
        mapped = progress_start + int(raw_pct * (progress_end - progress_start) / 100)
        _job_update(job_id, {"progress": mapped})

        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED"):
            err_msg = ""
            task_error = task.get("task_error")
            if task_error:
                err_msg = task_error.get("message", "")
            raise RuntimeError(
                f"Meshy task {task_id} {status.lower()}: {err_msg or 'no details'}"
            )
        # PENDING or IN_PROGRESS — keep polling

    raise RuntimeError(
        f"Generation timed out waiting for task {task_id} after "
        f"~{_MAX_POLL_PER_STAGE * _POLL_INTERVAL // 60} minutes."
    )


def _run_figure_job(job_id: str, child_prompt: str,
                    anthropic_key: str, meshy_key: str,
                    style: str = "", story: str = "") -> None:
    """Background worker: full pipeline from prompt → GLB → report."""
    import time

    try:
        # Stage: prompting
        _job_update(job_id, {"stage": "prompting", "progress": 2})
        enhanced = _enhance_figure_prompt(child_prompt, anthropic_key, style, story)
        _job_update(job_id, {"enhanced_prompt": enhanced, "progress": 8})

        # Stage: preview
        _job_update(job_id, {"stage": "preview", "progress": 10})
        preview_id = meshy_generator.create_preview_task(enhanced, api_key=meshy_key)
        _poll_until_done(preview_id, job_id, meshy_key,
                         progress_start=10, progress_end=50)

        # Stage: refine
        _job_update(job_id, {"stage": "refine", "progress": 50})
        refine_id = meshy_generator.create_refine_task(preview_id, api_key=meshy_key)
        refine_task = _poll_until_done(refine_id, job_id, meshy_key,
                                       progress_start=50, progress_end=90)

        # Extract GLB URL
        model_urls = refine_task.get("model_urls") or {}
        glb_url = model_urls.get("glb")
        if not glb_url:
            raise RuntimeError(
                "Meshy refine succeeded but returned no GLB URL. "
                f"model_urls: {model_urls}"
            )

        # Stage: downloading
        _job_update(job_id, {"stage": "downloading", "progress": 92})
        glb_filename = f"{job_id}.glb"
        dest_path = os.path.join(FIGURES_DIR, glb_filename)
        os.makedirs(FIGURES_DIR, exist_ok=True)
        meshy_generator.download_model(glb_url, dest_path)
        _job_update(job_id, {"glb_filename": glb_filename, "progress": 94})

        # Stage: analyzing (Claude print report)
        _job_update(job_id, {"stage": "analyzing", "progress": 96})
        report_data = _make_print_report(enhanced, anthropic_key)
        _job_update(job_id, {
            "report": report_data["report"],
            "filament": report_data["filament"],
            "progress": 99,
        })

        # Auto-save: download thumbnail + append to gallery/models.json
        # Thumbnails go to IMAGES_DIR like every other image the app writes —
        # they are served through /image/{filename}, and keeping them out of the
        # top level of OUTPUT_DIR is what saved the two that survived the
        # `rm -f output/*.png` incident.
        thumbnail_url = refine_task.get("thumbnail_url")
        thumbnail_filename = None
        try:
            if thumbnail_url:
                thumbnail_filename = f"{uuid.uuid4().hex}.png"
                thumb_dest = os.path.join(IMAGES_DIR, thumbnail_filename)
                os.makedirs(IMAGES_DIR, exist_ok=True)
                meshy_generator.download_model(thumbnail_url, thumb_dest)
        except Exception:
            thumbnail_filename = None  # thumbnail failure is non-fatal

        try:
            model_record = {
                "id": uuid.uuid4().hex[:8],
                "glb_filename": glb_filename,
                "prompt": child_prompt,
                "enhanced_prompt": enhanced,
                "report": report_data["report"],
                "filament": report_data["filament"],
                "thumbnail_filename": thumbnail_filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _manifest_append(_MODELS_MANIFEST, model_record)
        except Exception:
            pass  # manifest failure is non-fatal

        # Done
        _job_update(job_id, {"stage": "done", "progress": 100})

    except Exception as exc:
        _job_update(job_id, {"stage": "error", "error": str(exc)})


# ── Figure request/response models ───────────────────────────────────────────

class FigureGenerateRequest(BaseModel):
    prompt: str
    style: Optional[str] = ""              # shared style prompt (shapes the look)
    story: Optional[str] = ""             # shared story prompt (context/pose)
    anthropic_key: Optional[str] = None
    meshy_key: Optional[str] = None
    # Figure engine from Settings ("meshy" | "local-hunyuan3d"). None = meshy.
    # Validated against server-side availability — a name, never a trust.
    engine: Optional[str] = None
    # Local text→figure chains through image generation first; this is the
    # image model id for that step (the Settings image model). Allow-listed
    # by image_backends like any other generation.
    image_model: Optional[str] = None


class FigureFromImageRequest(BaseModel):
    filename: str                          # portrait filename from OUTPUT_DIR
    prompt: Optional[str] = ""            # character description — used only for print report
    style: Optional[str] = ""
    story: Optional[str] = ""
    anthropic_key: Optional[str] = None
    meshy_key: Optional[str] = None
    engine: Optional[str] = None           # see FigureGenerateRequest.engine


# ── Image-to-3D figure worker ─────────────────────────────────────────────────

def _run_figure_image_job(job_id: str, filename: str, prompt: str,
                          anthropic_key: Optional[str], meshy_key: str) -> None:
    """Background worker: portrait image → image-to-3D GLB → report → gallery."""
    from PIL import Image as PilImage

    try:
        # Stage: prompting (brief — prepare image)
        _job_update(job_id, {"stage": "prompting", "progress": 2})

        # Read and re-encode the portrait with Pillow (resize, JPEG, base64).
        # This keeps the upload payload small and strips any EXIF / alpha channel.
        img_path = _resolve_image_path(filename)
        if img_path is None:
            raise RuntimeError("Portrait image file not found.")
        with PilImage.open(img_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
        b64 = base64.b64encode(buf.getvalue()).decode()
        data_uri = "data:image/jpeg;base64," + b64

        # Stage: preview (Meshy image-to-3D — single task, not preview→refine)
        _job_update(job_id, {"stage": "preview", "progress": 10})
        task_id = meshy_generator.create_image_to_3d_task(data_uri, api_key=meshy_key)
        task = _poll_until_done(
            task_id, job_id, meshy_key,
            progress_start=10, progress_end=90,
            getter=meshy_generator.get_image_to_3d_task,
        )

        # Extract GLB URL
        glb_url = (task.get("model_urls") or {}).get("glb")
        if not glb_url:
            raise RuntimeError(
                "Meshy image-to-3D succeeded but returned no GLB URL. "
                f"model_urls: {task.get('model_urls')}"
            )

        # Stage: downloading
        _job_update(job_id, {"stage": "downloading", "progress": 92})
        glb_filename = f"{job_id}.glb"
        dest_path = os.path.join(FIGURES_DIR, glb_filename)
        os.makedirs(FIGURES_DIR, exist_ok=True)
        meshy_generator.download_model(glb_url, dest_path)
        _job_update(job_id, {"glb_filename": glb_filename, "progress": 94})

        # Stage: analyzing (Claude print report — degrades if no key)
        _job_update(job_id, {"stage": "analyzing", "progress": 96})
        report_data = _make_print_report(prompt or "a 3D character figure", anthropic_key)
        _job_update(job_id, {
            "report": report_data["report"],
            "filament": report_data["filament"],
            "progress": 99,
        })

        # Auto-save to gallery — best-effort; failure is non-fatal
        # Thumbnails go to IMAGES_DIR (see the matching note in the text-to-3D worker).
        thumbnail_url = task.get("thumbnail_url")
        thumbnail_filename = None
        try:
            if thumbnail_url:
                thumbnail_filename = f"{uuid.uuid4().hex}.png"
                thumb_dest = os.path.join(IMAGES_DIR, thumbnail_filename)
                os.makedirs(IMAGES_DIR, exist_ok=True)
                meshy_generator.download_model(thumbnail_url, thumb_dest)
        except Exception:
            thumbnail_filename = None

        try:
            model_record = {
                "id": uuid.uuid4().hex[:8],
                "glb_filename": glb_filename,
                "prompt": prompt or "(from image)",
                "enhanced_prompt": None,       # not applicable for image-to-3D
                "source": "image",
                "report": report_data["report"],
                "filament": report_data["filament"],
                "thumbnail_filename": thumbnail_filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _manifest_append(_MODELS_MANIFEST, model_record)
        except Exception:
            pass  # manifest failure is non-fatal

        # Done
        _job_update(job_id, {"stage": "done", "progress": 100})

    except Exception as exc:
        _job_update(job_id, {"stage": "error", "error": str(exc)})


def _run_local_figure_job(job_id: str, filename: Optional[str], prompt: str,
                          style: str, image_model: Optional[str],
                          anthropic_key: Optional[str],
                          gemini_key: Optional[str]) -> None:
    """Background worker: on-device figure via Hunyuan3D-2.1 shape stage.

    With `filename`, meshes an existing portrait. Without one (text mode),
    it first generates the portrait through image_backends with
    `image_model` — the local text→figure chain. Output is an untextured,
    print-ready GLB; the viewer's IBL lighting renders it as clean gray.
    """
    from PIL import Image as PilImage
    try:
        if filename is None:
            # Text mode: make the portrait first, with the user's image model.
            _job_update(job_id, {"stage": "illustrating", "progress": 3})
            result = image_backends.generate(
                content_prompt=prompt, style_prompt=style or "",
                model_id=image_model, aspect_ratio="1:1",
                api_key=gemini_key)
            filename = f"{uuid.uuid4().hex}.png"
            image_backends.save_result(result, filename)
            _gallery_save_record(filename, prompt, image_model)
            _job_update(job_id, {"portrait_filename": filename})

        img_path = _resolve_image_path(filename)
        if img_path is None:
            raise RuntimeError("Portrait image file not found.")
        with PilImage.open(img_path) as img:
            portrait = img.convert("RGB")

        def on_progress(stage: str, pct: int) -> None:
            # Map the module's 5..90 onto 10..88 so 'analyzing' has room.
            _job_update(job_id, {"stage": stage,
                                 "progress": 10 + int(pct * 0.85)})

        glb_filename = f"{job_id}.glb"
        os.makedirs(FIGURES_DIR, exist_ok=True)
        stats = local_figure_generator.generate_figure(
            portrait, os.path.join(FIGURES_DIR, glb_filename),
            on_progress=on_progress)
        _job_update(job_id, {"glb_filename": glb_filename, "progress": 94})

        _job_update(job_id, {"stage": "analyzing", "progress": 96})
        report_data = _make_print_report(prompt or "a 3D character figure",
                                         anthropic_key)
        _job_update(job_id, {"report": report_data["report"],
                             "filament": report_data["filament"],
                             "progress": 99})

        try:
            _manifest_append(_MODELS_MANIFEST, {
                "id": uuid.uuid4().hex[:8],
                "glb_filename": glb_filename,
                "prompt": prompt or "(from image)",
                "enhanced_prompt": None,
                "source": "local-hunyuan3d",
                "report": report_data["report"],
                "filament": report_data["filament"],
                # The portrait doubles as the thumbnail — same IMAGES_DIR
                # serving path as Meshy thumbnails.
                "thumbnail_filename": filename,
                "mesh_stats": stats,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass  # manifest failure is non-fatal

        _job_update(job_id, {"stage": "done", "progress": 100})
    except Exception as exc:
        import traceback; traceback.print_exc()
        _job_update(job_id, {"stage": "error", "error": str(exc)})


# ── Figure routes ─────────────────────────────────────────────────────────────

@app.get("/figure/backends")
def figure_backends():
    """Selectable figure engines — the Settings picker's source of truth.

    Mirrors the image-model contract: an engine appears only when it can
    actually run (honest discovery), and requests naming an absent engine
    are 400s at submit.
    """
    engines = []
    if settings_store.get_key("MESHY_API_KEY"):
        engines.append({"id": "meshy",
                        "name": "Meshy.AI — cloud, textured",
                        "backend": "cloud"})
    ok, reason = local_figure_generator.available()
    if ok:
        engines.append({"id": "local-hunyuan3d",
                        "name": "Hunyuan3D on this Mac — $0.00, print-ready, very slow (~10–20 min)",
                        "backend": "local"})
    return {"engines": engines,
            "local": {"available": ok, "reason": reason}}

@app.post("/figure/generate")
def figure_generate(req: FigureGenerateRequest):
    """Start a figure generation job. Returns {job_id}."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    if req.engine == "local-hunyuan3d":
        ok, reason = local_figure_generator.available()
        if not ok:
            raise HTTPException(status_code=503, detail=reason)
        # Text mode chains through image generation — the image model must
        # be in the allow-list like any other generation.
        if not req.image_model or image_backends.backend_for(req.image_model) is None:
            raise HTTPException(
                status_code=400,
                detail="Local figures need a valid image model (pick one in Settings).")
        job_id = uuid.uuid4().hex
        _job_create(job_id)
        threading.Thread(
            target=_run_local_figure_job,
            args=(job_id, None, req.prompt.strip(), _safe_style(req.style),
                  req.image_model,
                  req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY"),
                  settings_store.get_key("GEMINI_API_KEY")),
            daemon=True).start()
        return {"job_id": job_id}

    resolved_meshy_key = req.meshy_key or settings_store.get_key("MESHY_API_KEY")
    if not resolved_meshy_key:
        raise HTTPException(
            status_code=503,
            detail="MESHY_API_KEY not set on server.",
        )

    resolved_anthropic_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if not resolved_anthropic_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not set on server.",
        )

    job_id = uuid.uuid4().hex
    _job_create(job_id)

    thread = threading.Thread(
        target=_run_figure_job,
        args=(job_id, req.prompt.strip(), resolved_anthropic_key, resolved_meshy_key,
              _safe_style(req.style), (req.story or "").strip()),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.post("/figure/generate-from-image")
def figure_generate_from_image(req: FigureFromImageRequest):
    """Start an image-to-3D figure job from an existing portrait. Returns {job_id}."""
    # Validate filename — same guard as get_image
    if not re.fullmatch(r"[a-f0-9]{32}\.png", req.filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")

    if _resolve_image_path(req.filename) is None:
        raise HTTPException(status_code=404, detail="Couldn't find that portrait.")

    if req.engine == "local-hunyuan3d":
        ok, reason = local_figure_generator.available()
        if not ok:
            raise HTTPException(status_code=503, detail=reason)
        job_id = uuid.uuid4().hex
        _job_create(job_id)
        threading.Thread(
            target=_run_local_figure_job,
            args=(job_id, req.filename, (req.prompt or "").strip(), "", None,
                  req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY"),
                  None),
            daemon=True).start()
        return {"job_id": job_id}

    resolved_meshy_key = req.meshy_key or settings_store.get_key("MESHY_API_KEY")
    if not resolved_meshy_key:
        raise HTTPException(
            status_code=503,
            detail="MESHY_API_KEY not set on server.",
        )

    # Anthropic key is optional — print report degrades gracefully if absent
    resolved_anthropic_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")

    job_id = uuid.uuid4().hex
    _job_create(job_id)

    threading.Thread(
        target=_run_figure_image_job,
        args=(job_id, req.filename, (req.prompt or "").strip(),
              resolved_anthropic_key, resolved_meshy_key),
        daemon=True,
    ).start()

    return {"job_id": job_id}


@app.get("/figure/status/{job_id}")
def figure_status(job_id: str):
    """Poll the status of a figure generation job."""
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")
    record = _job_read(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return record


@app.get("/figure/model/{filename}")
def figure_model(filename: str):
    """Serve a generated GLB file."""
    if not re.fullmatch(r"[a-f0-9]{32}\.glb", filename):
        raise HTTPException(status_code=400, detail="Invalid filename format.")
    path = os.path.join(FIGURES_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Model file not found.")
    return FileResponse(path, media_type="model/gltf-binary")


# ── Practice Sheet ────────────────────────────────────────────────────────────
# Chinese-only feature: Claude's code-execution sandbox runs ReportLab + WQY font
# to produce a 田字格 (tian zi ge) writing-practice PDF, retrieved via the Files API.
# Async job pattern mirrors the Figure Maker job store.

_practice_jobs: dict[str, dict] = {}
_practice_jobs_lock = threading.Lock()


def _practice_job_create(job_id: str, title_en: str = "") -> dict:
    record = {
        "job_id": job_id,
        "stage": "prompting",
        "error": None,
        "pdf_filename": None,
        "title_en": title_en,
    }
    with _practice_jobs_lock:
        _practice_jobs[job_id] = record
    return record


def _practice_job_update(job_id: str, patch: dict) -> None:
    with _practice_jobs_lock:
        if job_id in _practice_jobs:
            _practice_jobs[job_id].update(patch)


def _practice_job_read(job_id: str) -> Optional[dict]:
    with _practice_jobs_lock:
        rec = _practice_jobs.get(job_id)
        return dict(rec) if rec else None


class PracticeSheetRequest(BaseModel):
    language: Optional[str] = "zh"
    book_title_en: str
    book_title_zh: str
    book_title_pinyin: str
    zh_text: str
    anthropic_key: Optional[str] = None


def _run_practice_job(
    job_id: str,
    title_en: str,
    title_zh: str,
    title_pinyin: str,
    zh_text: str,
    api_key: str,
) -> None:
    """Background worker: call Claude code-execution to generate the practice PDF."""
    try:
        _practice_job_update(job_id, {"stage": "executing"})
        pdf_bytes = practice_sheet_mod.generate_practice_pdf_bytes(
            title_en=title_en,
            title_zh=title_zh,
            title_pinyin=title_pinyin,
            zh_text=zh_text,
            api_key=api_key,
        )
        os.makedirs(PRACTICE_DIR, exist_ok=True)
        pdf_path = os.path.join(PRACTICE_DIR, f"{job_id}.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(pdf_bytes)
        _practice_job_update(job_id, {
            "stage": "done",
            "pdf_filename": f"{job_id}.pdf",
        })
    except anthropic.APIError as exc:
        _practice_job_update(job_id, {
            "stage": "error",
            "error": f"Anthropic API error: {exc}",
        })
    except Exception as exc:
        _practice_job_update(job_id, {
            "stage": "error",
            "error": str(exc),
        })


@app.post("/practice-sheet")
def practice_sheet_generate(req: PracticeSheetRequest):
    """Start a practice-sheet generation job. Returns {job_id}. Chinese-only."""
    if (req.language or "zh") != "zh":
        raise HTTPException(status_code=400, detail="Practice sheets are Chinese-only.")

    resolved_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not set on server.",
        )

    job_id = uuid.uuid4().hex
    _practice_job_create(job_id, title_en=req.book_title_en)

    thread = threading.Thread(
        target=_run_practice_job,
        args=(
            job_id,
            req.book_title_en,
            req.book_title_zh,
            req.book_title_pinyin,
            req.zh_text,
            resolved_key,
        ),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/practice-sheet/status/{job_id}")
def practice_sheet_status(job_id: str):
    """Poll the status of a practice-sheet generation job."""
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")
    record = _practice_job_read(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return record


@app.get("/practice-sheet/download/{job_id}")
def practice_sheet_download(job_id: str):
    """Download the generated practice PDF. Returns 409 if job is not done yet."""
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")
    record = _practice_job_read(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if record["stage"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done yet (stage: {record['stage']}).",
        )
    pdf_path = os.path.join(PRACTICE_DIR, record["pdf_filename"])
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on server.")
    # Derive a human-friendly filename from the book's English title (slug style)
    raw_title = record.get("title_en", "") or ""
    slug = re.sub(r"[^a-z0-9]+", "_", raw_title.lower()).strip("_") or job_id
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{slug}_practice.pdf",
    )


class LocalPracticeRequest(BaseModel):
    language: Optional[str] = "zh"
    book_title_zh: Optional[str] = ""
    book_title_en: Optional[str] = ""
    pages: list[PageData] = []


@app.post("/practice-sheet/local")
def practice_sheet_local(req: LocalPracticeRequest):
    """Generate a Chinese word writing-practice PDF in-process (no Claude).

    Segments the story into words (bundled CC-CEDICT), picks the most frequent,
    and renders a US-Letter sheet showing each word + pinyin + English translation
    with 田字格 practice boxes (the word traced faded once, then repeated blank).
    Synchronous — returns the PDF.
    """
    if (req.language or "zh") != "zh":
        raise HTTPException(status_code=400, detail="Practice sheets are Chinese-only.")
    pages = [p.model_dump() for p in req.pages]
    try:
        words = practice_sheet_local_mod.top_words(pages, n=8)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not words:
        raise HTTPException(status_code=400, detail="No Chinese words found in this story.")
    try:
        pdf = practice_sheet_local_mod.render_pdf_bytes(
            req.book_title_zh or "", req.book_title_en or "", words,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    slug = re.sub(r"[^a-z0-9]+", "_", (req.book_title_en or "practice").lower()).strip("_") or "practice"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}_practice.pdf"'},
    )


# ── Book PDF (prompt/existing → printable PDF) ────────────────────────────────
# Async job pattern mirrors the Figure Maker / Practice Sheet job stores. Runs
# the full storybook pipeline (decompose → readings check → per-page image
# generation → HTML render → PDF via headless Chromium → Chinese practice-sheet
# append → merge) and hands back one downloadable PDF. See
# design-specs/book-pdf-endpoint.md for the full design rationale.

_book_pdf_jobs: dict[str, dict] = {}
_book_pdf_jobs_lock = threading.Lock()

# Bounds concurrent book-pdf jobs — the most expensive endpoint in the app
# (up to 2 opus calls + up to 19 Gemini image calls per job, no confirmation
# gate). Not a substitute for real rate limiting/auth (tracked in
# design-specs/security-architecture-backlog.md); just a interim guardrail so
# a burst of requests can't pile up unboundedly many daemon worker threads.
_BOOK_PDF_SEM = threading.BoundedSemaphore(2)


def _book_pdf_job_create(job_id: str) -> dict:
    record = {
        "job_id": job_id,
        "stage": "decomposing",
        "progress": 0,
        "current_page": None,
        "total_pages": None,
        "pages_generated": 0,
        "pages_reused": 0,
        "practice_sheet_included": None,
        "book_title_en": None,
        "pdf_filename": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _book_pdf_jobs_lock:
        _book_pdf_jobs[job_id] = record
    return record


def _book_pdf_job_update(job_id: str, patch: dict) -> None:
    with _book_pdf_jobs_lock:
        if job_id in _book_pdf_jobs:
            _book_pdf_jobs[job_id].update(patch)


def _book_pdf_job_read(job_id: str) -> Optional[dict]:
    with _book_pdf_jobs_lock:
        rec = _book_pdf_jobs.get(job_id)
        return dict(rec) if rec else None


class BookPDFRequest(BaseModel):
    mode: Literal["prompt", "existing"] = "prompt"
    # prompt-mode fields
    concept: Optional[str] = ""
    character: Optional[str] = ""
    style_suffix: Optional[str] = ""
    language: Optional[str] = "zh"
    page_count: Optional[int] = 11
    # existing-mode fields
    story: Optional[dict] = None
    generated_images: Optional[dict[str, str]] = None
    # both modes
    recheck_readings: Optional[bool] = None
    include_art: Optional[bool] = True    # False = text-only book (no images, no Gemini)
    anthropic_key: Optional[str] = None
    gemini_key: Optional[str] = None
    gemini_model: Optional[str] = "imagen-4.0-fast-generate-001"


def _resolve_book_pdf_recheck(mode: str, recheck_readings: Optional[bool]) -> bool:
    """recheck_readings=None resolves per-mode: locked True (non-overridable)
    for mode="prompt", default False (overridable) for mode="existing"."""
    if mode == "prompt":
        return True
    return recheck_readings if recheck_readings is not None else False


def _book_pdf_needs_gemini(page_numbers: list, generated_images: dict) -> bool:
    """True if at least one of page_numbers lacks a reusable image on disk."""
    generated_images = generated_images or {}
    for pnum in page_numbers:
        fname = generated_images.get(str(pnum)) or generated_images.get(pnum)
        if not (fname and _resolve_image_path(fname)):
            return True
    return False


def _overlay_recheck_onto_story(story: dict, recheck_data: dict, lang: dict) -> None:
    """Overlay corrected native text / reading / en / characters[] from a
    /recheck-readings-shaped response onto `story`'s pages IN PLACE, matched
    by page number — mirrors book_builder.js's client-side applyCheckReadings
    merge. Each page's `image_prompt` (absent from recheck_data) and the
    story's own title fields are preserved untouched; only
    book_title_characters is overlaid, same as the client."""
    native_f  = lang["native_field"]
    reading_f = lang["reading_field"]
    returned_by_page = {rp.get("page"): rp for rp in (recheck_data.get("pages") or [])}
    for pg in story.get("pages", []):
        rp = returned_by_page.get(pg.get("page"))
        if not rp:
            continue
        pg[native_f]  = rp.get(native_f, pg.get(native_f))
        pg[reading_f] = rp.get(reading_f, pg.get(reading_f))
        pg["en"] = rp.get("en", pg.get("en"))
        if rp.get("characters"):
            pg["characters"] = rp["characters"]
        # image_prompt intentionally left untouched — recheck_data never carries it.
    if recheck_data.get("book_title_characters"):
        story["book_title_characters"] = recheck_data["book_title_characters"]


def _generate_book_pdf_page_image(pg: dict, gemini_model: str, style_suffix: str, gemini_key: str) -> str:
    """Generate one page's illustration via Gemini, one retry on failure.
    Raises RuntimeError naming the page on repeated failure — this endpoint's
    contract is a finished, printable PDF, so a caller polling to `done`
    should never discover a silently-blank page (see design-specs/
    book-pdf-endpoint.md Section 6)."""
    prompt = pg.get("image_prompt") or ""
    last_err: Optional[Exception] = None
    for _attempt in range(2):
        try:
            result = image_backends.generate(
                content_prompt=prompt,
                style_prompt=style_suffix,
                negative_prompt="",
                model_id=gemini_model,
                aspect_ratio=None,
                width=1024,
                height=1024,
                api_key=gemini_key,
            )
            filename = f"{uuid.uuid4().hex}.png"
            image_backends.save_result(result, filename)
            return filename
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Image generation failed for page {pg.get('page')}: {last_err}")


def _run_book_pdf_job(job_id: str, req_data: dict, anthropic_key: Optional[str], gemini_key: Optional[str]) -> None:
    """Background worker: prompt/existing → decompose → readings check →
    per-page illustration → HTML render → PDF → practice-sheet merge.
    Stage/progress bands mirror design-specs/book-pdf-endpoint.md Section 1."""
    try:
        mode = req_data.get("mode", "prompt")
        language = req_data.get("language") or languages.DEFAULT_LANGUAGE
        lang = languages.get(language)

        # ── decomposing (0-8) — skipped (jumps straight through) for mode="existing" ──
        _book_pdf_job_update(job_id, {"stage": "decomposing", "progress": 0})
        if mode == "prompt":
            story = run_decompose(
                concept=req_data.get("concept") or "",
                style_suffix=req_data.get("style_suffix") or "",
                character=req_data.get("character") or "",
                language=language,
                page_count=req_data.get("page_count") or 11,
                api_key=anthropic_key,
                include_art=req_data.get("include_art", True),
            )
        else:
            story = dict(req_data.get("story") or {})
            story.setdefault("language", language)
        _book_pdf_job_update(job_id, {"progress": 8, "book_title_en": story.get("book_title_en")})

        # ── checking-readings (8-18) ──
        recheck = _resolve_book_pdf_recheck(mode, req_data.get("recheck_readings"))
        _book_pdf_job_update(job_id, {"stage": "checking-readings", "progress": 8})
        if recheck:
            title_native_f  = lang["title_native_field"]
            title_reading_f = lang["title_reading_field"]
            recheck_data = run_recheck(
                language=language,
                pages=story.get("pages", []),
                api_key=anthropic_key,
                book_title_native=story.get(title_native_f),
                book_title_reading=story.get(title_reading_f),
                book_title_characters=story.get("book_title_characters"),
            )
            _overlay_recheck_onto_story(story, recheck_data, lang)
        _book_pdf_job_update(job_id, {"progress": 18})

        pages = story.get("pages") or []
        # undefined/true -> illustrated (backward-compat); only explicit False is text-only.
        illustrated = story.get("include_art", True) is not False

        image_uris: dict = {}
        if illustrated:
            # ── illustrating (18-78) ──
            _book_pdf_job_update(job_id, {"stage": "illustrating", "progress": 18})
            generated_images = req_data.get("generated_images") or {}
            gemini_model = req_data.get("gemini_model") or "imagen-4.0-fast-generate-001"
            # Raw: image_backends.generate() adds the safety suffix for cloud
            # backends only.
            style_suffix = (req_data.get("style_suffix") or "").strip()

            def _reusable_filename(pnum) -> Optional[str]:
                fname = generated_images.get(str(pnum)) or generated_images.get(pnum)
                return fname if (fname and _resolve_image_path(fname)) else None

            n_needed = sum(1 for pg in pages if not _reusable_filename(pg.get("page")))
            _book_pdf_job_update(job_id, {"total_pages": n_needed})

            pages_generated = 0
            pages_reused = 0
            idx = 0
            for pg in pages:
                pnum = pg.get("page")
                reused = _reusable_filename(pnum)
                if reused:
                    use_fname = reused
                    pages_reused += 1
                else:
                    idx += 1
                    _book_pdf_job_update(job_id, {
                        "current_page": idx,
                        "progress": 18 + int((idx - 1) * (78 - 18) / max(n_needed, 1)),
                    })
                    use_fname = _generate_book_pdf_page_image(pg, gemini_model, style_suffix, gemini_key)
                    pages_generated += 1

                src_path = _resolve_image_path(use_fname)
                if src_path is None:
                    raise RuntimeError(f"Page image not found on disk: {use_fname}")
                with open(src_path, "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode()
                image_uris[pnum] = f"data:image/png;base64,{b64}"

            _book_pdf_job_update(job_id, {
                "progress": 78,
                "pages_generated": pages_generated,
                "pages_reused": pages_reused,
            })
        else:
            # Text-only: no images at all — skip the whole illustrating stage.
            _book_pdf_job_update(job_id, {
                "progress": 78, "pages_generated": 0, "pages_reused": 0, "total_pages": 0,
            })

        # ── rendering (78-90) ──
        _book_pdf_job_update(job_id, {"stage": "rendering", "progress": 80})
        html = book_pdf.build_storybook_html(story, image_uris)
        book_bytes = book_pdf.render_pdf(html)
        _book_pdf_job_update(job_id, {"progress": 90})

        # ── practice-sheet (90-96) — zh only, skipped if no words found ──
        practice_bytes = None
        practice_included = False
        if (story.get("language") or language) == "zh":
            _book_pdf_job_update(job_id, {"stage": "practice-sheet", "progress": 92})
            words = practice_sheet_local_mod.top_words(pages, n=8)
            if words:
                practice_bytes = practice_sheet_local_mod.render_pdf_bytes(
                    story.get("book_title_zh", "") or "",
                    story.get("book_title_en", "") or "",
                    words,
                )
                practice_included = True
        _book_pdf_job_update(job_id, {"progress": 96, "practice_sheet_included": practice_included})

        # ── merging (96-99) ──
        _book_pdf_job_update(job_id, {"stage": "merging", "progress": 97})
        final_bytes = book_pdf.merge_pdfs(book_bytes, practice_bytes) if practice_bytes else book_bytes

        os.makedirs(BOOK_PDF_DIR, exist_ok=True)
        pdf_path = os.path.join(BOOK_PDF_DIR, f"{job_id}.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(final_bytes)

        _book_pdf_job_update(job_id, {
            "stage": "done",
            "progress": 100,
            "pdf_filename": f"{job_id}.pdf",
            "book_title_en": story.get("book_title_en"),
        })

    except HTTPException as exc:
        _book_pdf_job_update(job_id, {"stage": "error", "error": str(exc.detail)})
    except Exception as exc:
        _book_pdf_job_update(job_id, {"stage": "error", "error": str(exc)})
    finally:
        _BOOK_PDF_SEM.release()


@app.post("/book-pdf")
def book_pdf_start(req: BookPDFRequest):
    """Start a prompt/existing → printable-PDF job. Returns {job_id}."""
    language = req.language or languages.DEFAULT_LANGUAGE
    if language not in languages.LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unknown language: {language}")

    # SECURITY: the worker reads and base64-embeds every generated_images value
    # from OUTPUT_DIR in ALL modes, so validate the allow-list unconditionally —
    # NOT only in the existing-mode branch. Without this, a mode="prompt" caller
    # could pass an absolute/traversal path (e.g. "config.json", "/etc/passwd")
    # and exfiltrate it inside the downloadable PDF. See figure/get_image guards.
    for fname in (req.generated_images or {}).values():
        if not re.fullmatch(r"[a-f0-9]{32}\.png", fname):
            raise HTTPException(status_code=400, detail=f"Invalid generated_images filename: {fname!r}")

    if req.mode == "prompt":
        if not (req.concept or "").strip() and not (req.character or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Provide a Character Description or a Story Prompt.",
            )
        # Text-only allows 1-30 pages (cheap, Claude-only); illustrated keeps the
        # 11/15/19 cap since each page is a paid image generation.
        if req.include_art:
            if req.page_count not in (11, 15, 19):
                raise HTTPException(status_code=400, detail="page_count must be one of 11, 15, 19.")
        elif not (1 <= (req.page_count or 0) <= 30):
            raise HTTPException(status_code=400, detail="page_count must be between 1 and 30 for text-only books.")
        page_numbers = list(range(1, req.page_count + 1))
        text_only = req.include_art is False
    else:
        story = req.story
        if not story or not story.get("pages"):
            raise HTTPException(
                status_code=400,
                detail='mode="existing" requires a non-empty story with pages.',
            )
        story_lang = story.get("language")
        if story_lang and story_lang != language:
            raise HTTPException(
                status_code=400,
                detail=f"language ({language}) does not match story.language ({story_lang}).",
            )
        page_numbers = [pg.get("page") for pg in story.get("pages", [])]
        # For an existing story the story's own flag is authoritative.
        text_only = story.get("include_art", True) is False

    recheck = _resolve_book_pdf_recheck(req.mode, req.recheck_readings)
    needs_anthropic = (req.mode == "prompt") or recheck
    # Text-only books never generate images, so they never need a Gemini key.
    needs_gemini = (not text_only) and _book_pdf_needs_gemini(page_numbers, req.generated_images)

    anthropic_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if needs_anthropic and not anthropic_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    gemini_key = req.gemini_key or settings_store.get_key("GEMINI_API_KEY")
    if needs_gemini and not gemini_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not set on server.")

    if not _BOOK_PDF_SEM.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Server busy — try again shortly.")

    # The worker releases the permit in its finally. If we fail to spawn it
    # (job-store or thread-start error), the finally never runs — release here
    # so a spawn failure can't permanently leak a BoundedSemaphore permit.
    try:
        job_id = uuid.uuid4().hex
        _book_pdf_job_create(job_id)

        req_data = req.model_dump(exclude={"anthropic_key", "gemini_key"})
        thread = threading.Thread(
            target=_run_book_pdf_job,
            args=(job_id, req_data, anthropic_key, gemini_key),
            daemon=True,
        )
        thread.start()
    except BaseException:
        _BOOK_PDF_SEM.release()
        raise

    return {"job_id": job_id}


@app.get("/book-pdf/status/{job_id}")
def book_pdf_status(job_id: str):
    """Poll the status of a book-pdf generation job."""
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")
    record = _book_pdf_job_read(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return record


@app.get("/book-pdf/download/{job_id}")
def book_pdf_download(job_id: str):
    """Download the generated book PDF. Returns 409 if the job is not done yet."""
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")
    record = _book_pdf_job_read(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if record["stage"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done yet (stage: {record['stage']}).",
        )
    # Path built ONLY from job_id (never a client-supplied field) + the fixed dir.
    pdf_path = os.path.join(BOOK_PDF_DIR, f"{job_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on server.")
    raw_title = record.get("book_title_en", "") or ""
    slug = re.sub(r"[^a-z0-9]+", "_", raw_title.lower()).strip("_") or job_id
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{slug}.pdf",
    )


class RevalidatingStaticFiles(StaticFiles):
    """Serve the frontend with `Cache-Control: no-cache`.

    There is no build step here, so asset filenames carry no content hash. A
    browser that caches settings.js or style.css from memory will keep serving
    a stale copy after an edit, with no way to bust it short of a hard reload
    — which has already cost real debugging time once.

    `no-cache` does not mean "do not store": it means "revalidate before
    reusing". StaticFiles already emits an ETag and Last-Modified, so each
    check is a conditional request that answers 304 with an empty body when
    nothing changed. The cost is one round trip per asset, which is the right
    trade for a same-origin app whose static files are local anyway.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        # setdefault: never clobber a more specific policy set upstream.
        response.headers.setdefault("Cache-Control", "no-cache")
        return response


# ── Frontend static files (must be last — catches everything not matched above) ──
app.mount("/", RevalidatingStaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
