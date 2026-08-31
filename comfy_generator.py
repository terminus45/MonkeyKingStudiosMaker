"""Out-of-process image generation via a local ComfyUI server.

Route C of design-specs/lora-auto-pairing.md: models this machine cannot run
in-process (Krea 2's DiT needs a ~26 GB resident working set that wedges a
32 GB Mac under diffusers) run instead inside ComfyUI, which quantizes and
manages memory itself. This module speaks Comfy's HTTP API: submit an
API-format graph to /prompt, poll /history, fetch the PNG via /view.

Stdlib-only on purpose — importable everywhere, no new dependencies. When
ComfyUI isn't running, discovery returns nothing and the cloud/local paths
are untouched (same degrade-gracefully posture as local_generator).

The node graph mirrors ComfyUI's official Krea-2 Turbo template
(image_krea2_turbo_t2i.json): CLIPLoader type "krea2", KSampler at
8 steps / cfg 1.0 / euler / simple, ConditioningZeroOut as the negative.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable, Optional

# Comfy Desktop picks a port at launch (8000 default, but it yields when the
# app server holds 8000 — on this machine it lands on 8001). Probe order is
# configurable; first responder wins.
COMFY_URLS = [u.strip() for u in os.getenv(
    "COMFY_URLS", "http://127.0.0.1:8001,http://127.0.0.1:8188,http://127.0.0.1:8000"
).split(",") if u.strip()]

_PROBE_TTL_S = 20.0
_probe_cache: dict = {"at": 0.0, "url": None}

# The one model this backend currently offers, and the Comfy-side files it
# requires. Extending to more Comfy models means adding entries here (or,
# later, a sidecar-declared registry) — ids stay opaque, no request-supplied
# names ever reach Comfy's loaders.
KREA2_ID = "comfy:krea2-turbo"
# DiT variants in preference order — determined empirically on MPS:
#   bf16        works (Comfy's model manager streams what doesn't fit)
#   fp8_scaled  FAILS on MPS: "Trying to convert Float8_e4m3fn to the MPS
#               backend" — the dtype itself is unsupported there
#   int8        FAILS on MPS: aten::_int_mm has no MPS kernels
# The quantized variants stay listed for non-Mac hosts, after bf16.
_KREA2_DIT_CANDIDATES = [
    "krea2_turbo_bf16.safetensors",
    "krea2_turbo_fp8_scaled.safetensors",
    "krea2TurboOfficialComfy_krea2TurboInt8.safetensors",
]
_KREA2_FILES = {
    "text_encoders": "qwen3vl_4b_fp8_scaled.safetensors",
    "vae": "qwen_image_vae.safetensors",
}
_KREA2_DEFAULTS = {"steps": 8, "guidance": 1.0}

# Measured on the 32 GB M4: Krea 2 Turbo bf16 loads 24.4 GB and denoises at
# ~44–134 s/step (slowing as memory pressure builds) — a cold render is
# ~18 minutes. 900 s timed out a job Comfy went on to finish.
GENERATION_TIMEOUT_S = int(os.getenv("COMFY_TIMEOUT_S", "2400"))


def _get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def _post(url: str, payload: dict, timeout: float = 30.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def base_url() -> Optional[str]:
    """The reachable ComfyUI base URL, cached briefly so the registry (hit on
    every /models call and generate validation) doesn't hammer the probe."""
    now = time.time()
    if now - _probe_cache["at"] < _PROBE_TTL_S:
        return _probe_cache["url"]
    found = None
    for u in COMFY_URLS:
        try:
            _get(f"{u}/system_stats", timeout=1.5)
            found = u
            break
        except Exception:
            continue
    _probe_cache.update(at=now, url=found)
    return found


def available() -> tuple[bool, str]:
    url = base_url()
    if url is None:
        return False, "ComfyUI is not running"
    missing = _missing_files(url)
    if missing:
        return False, f"ComfyUI is running but missing model files: {', '.join(missing)}"
    return True, f"Ready via ComfyUI at {url}"


def _dit_file(url: str) -> Optional[str]:
    """Best available DiT variant on the Comfy side, or None."""
    try:
        listing = _get(f"{url}/models/diffusion_models", timeout=3) or []
    except Exception:
        listing = []
    for cand in _KREA2_DIT_CANDIDATES:
        if cand in listing:
            return cand
    return None


def _missing_files(url: str) -> list[str]:
    missing = []
    if _dit_file(url) is None:
        missing.append(f"diffusion_models/{_KREA2_DIT_CANDIDATES[0]}")
    for folder, fname in _KREA2_FILES.items():
        try:
            listing = _get(f"{url}/models/{folder}", timeout=3)
        except Exception:
            listing = []
        if fname not in (listing or []):
            missing.append(f"{folder}/{fname}")
    return missing


def discover_models() -> list[dict]:
    """Offered only when ComfyUI is up AND holds every required file —
    offering a model that cannot run just relocates the failure."""
    url = base_url()
    if url is None or _missing_files(url):
        return []
    return [{
        "id": KREA2_ID,
        "name": "Krea 2 Turbo — via ComfyUI, $0.00 · very slow (~15+ min)",
        "type": "krea2",
    }]


def _build_graph(prompt: str, seed: int, steps: int, cfg: float,
                 width: int, height: int, dit_file: str) -> dict:
    return {
        "u": {"class_type": "UNETLoader",
              "inputs": {"unet_name": dit_file,
                         "weight_dtype": "default"}},
        "c": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": _KREA2_FILES["text_encoders"],
                         "type": "krea2", "device": "default"}},
        "v": {"class_type": "VAELoader",
              "inputs": {"vae_name": _KREA2_FILES["vae"]}},
        "tp": {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["c", 0], "text": prompt}},
        "tn": {"class_type": "ConditioningZeroOut",
               "inputs": {"conditioning": ["tp", 0]}},
        "l": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "k": {"class_type": "KSampler",
              "inputs": {"model": ["u", 0], "positive": ["tp", 0],
                         "negative": ["tn", 0], "latent_image": ["l", 0],
                         "seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "d": {"class_type": "VAEDecode",
              "inputs": {"samples": ["k", 0], "vae": ["v", 0]}},
        "s": {"class_type": "SaveImage",
              "inputs": {"images": ["d", 0], "filename_prefix": "monkeyking"}},
    }


def generate(
    *,
    content_prompt: str,
    style_prompt: str = "",
    negative_prompt: str = "",       # accepted; inert at cfg 1.0
    model_id: str,
    aspect_ratio: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    seed: int = -1,
    steps: Optional[int] = None,
    guidance: Optional[float] = None,
    on_step: Optional[Callable[[int, int], None]] = None,
    **_ignored,
):
    """Generate one image through ComfyUI. Returns (PIL.Image, meta dict).

    Progress granularity is coarse for now (queued → done); Comfy's websocket
    would give per-step events — noted follow-up, not v1.
    """
    if model_id != KREA2_ID:
        raise ValueError(f"Unknown Comfy model: {model_id!r}")
    url = base_url()
    if url is None:
        raise RuntimeError("ComfyUI is not running — start Comfy Desktop and retry.")
    dit = _dit_file(url)
    if dit is None:
        raise RuntimeError("ComfyUI has no usable Krea 2 diffusion model file.")

    import random as _random
    if seed is None or seed < 0:
        seed = _random.randint(0, 2**32 - 1)

    # Krea 2 native area is ~1MP; reuse the local backend's area-preserving
    # dimension mapping so aspect ratios behave identically across backends.
    import local_generator
    w, h = local_generator._dimensions("krea2", aspect_ratio, width, height)

    steps = steps or _KREA2_DEFAULTS["steps"]
    cfg = _KREA2_DEFAULTS["guidance"] if guidance is None else guidance
    prompt = f"{content_prompt}, {style_prompt}" if style_prompt else content_prompt

    meta = {
        "backend": "comfy",
        "kind": "krea2",
        "model_id": model_id,
        "model_file": {"name": dit, "sha256": None},
        "seed": seed,
        "sampler": "euler_simple",
        "steps": steps,
        "guidance": cfg,
        "width": w,
        "height": h,
        "prompt_final": prompt,
        "negative_final": None,
        "hires": {"ran": False},
        "reproducible": True,
    }

    if on_step:
        on_step(0, 1)

    r = _post(f"{url}/prompt",
              {"prompt": _build_graph(prompt, seed, steps, cfg, w, h, dit),
               "client_id": uuid.uuid4().hex})
    pid = r["prompt_id"]

    t0 = time.time()
    while True:
        time.sleep(2)
        if time.time() - t0 > GENERATION_TIMEOUT_S:
            raise RuntimeError(f"ComfyUI generation timed out after {GENERATION_TIMEOUT_S}s.")
        try:
            hist = _get(f"{url}/history/{pid}", timeout=10)
        except Exception:
            continue                       # transient blip — keep polling
        entry = hist.get(pid)
        if not entry:
            continue
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            msgs = json.dumps(status.get("messages", []))[:400]
            raise RuntimeError(f"ComfyUI reported an error: {msgs}")
        outputs = entry.get("outputs", {})
        images = [im for o in outputs.values() for im in o.get("images", [])]
        if status.get("completed") or images:
            break

    if not images:
        raise RuntimeError("ComfyUI finished without producing an image.")

    q = urllib.parse.urlencode(images[0])
    with urllib.request.urlopen(f"{url}/view?{q}", timeout=60) as resp:
        data = resp.read()

    import io
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert("RGB")
    if on_step:
        on_step(1, 1)
    return image, meta
