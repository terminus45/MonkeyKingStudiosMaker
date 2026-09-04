"""Real-ESRGAN super-resolution — 2x / 4x / 8x over saved images.

design-specs/image-upscaler.md. Same posture as local_generator: torch and
spandrel are imported inside functions, so this module is safe to import on
a machine without the ML extras; available() reports why when it isn't.
Weights live in models/upscalers/ (gitignored — re-downloadable, not user
content) and are addressed by opaque keys, never request-supplied paths.

The 4x models are the workhorses. 2x is one pass Lanczos-halved; 8x is
pass -> half -> pass, so no pass ever runs on more than 2x the source pixels
(a naive 4x-of-4x would synthesize 4x the pixels only to throw them away).
Everything runs tiled with feathered overlap blending — plain convolutions,
so no attention-slicing hazard, but a 16 MP tensor still has no business on
MPS in one piece. Deterministic: same input + model + factor -> same output.
"""
import os
import threading
from typing import Callable, Optional

import numpy as np
from PIL import Image

from config import LOCAL_MODELS_DIR

UPSCALERS_DIR = os.getenv(
    "UPSCALER_MODELS_DIR", os.path.join(LOCAL_MODELS_DIR, "upscalers"))

# key -> weight file. Opaque ids; extending means adding a line here.
_MODEL_FILES = {
    "general": "RealESRGAN_x4plus.pth",          # photographic texture
    "anime":   "RealESRGAN_x4plus_anime_6B.pth",  # flat-shaded illustration
}

FACTORS = (2, 4, 8)
TILE = 512
OVERLAP = 32
# Server-side ceiling on synthesized output (the client warns at 40 MP;
# this is the hard stop that protects the process itself).
MAX_OUTPUT_PIXELS = 80_000_000

# One resident model, one GPU. Serialised for the same reason
# local_generator._GPU exists; a separate lock because an upscale and an SD
# render contend for memory, not correctness — and an 8x pass sharing the
# machine with a 90 s SDXL render is a choice the user makes by clicking.
_GPU = threading.BoundedSemaphore(1)
_resident: dict = {"key": None, "model": None, "scale": None}
_resident_lock = threading.Lock()

# Checkpoint-name fragments that mark an illustration-trained source model.
_ANIME_HINTS = ("anime", "animagine", "pony", "toon", "waifu", "illustrious")


def _torch():
    import torch
    return torch


def _device() -> str:
    torch = _torch()
    return "mps" if torch.backends.mps.is_available() else "cpu"


def available() -> tuple[bool, str]:
    try:
        import spandrel  # noqa: F401
        import torch     # noqa: F401
    except ImportError:
        return False, "Upscaling needs the local extras (pip install -r requirements-local.txt)"
    if not discover_models():
        return False, f"No upscaler weights found in {UPSCALERS_DIR}"
    return True, "Ready"


def discover_models() -> list[dict]:
    """Upscaler models actually on disk, by opaque key."""
    out = []
    for key, fname in _MODEL_FILES.items():
        if os.path.isfile(os.path.join(UPSCALERS_DIR, fname)):
            out.append({"key": key, "file": fname})
    return out


def choose_model(source_meta: Optional[dict]) -> tuple[str, str]:
    """Pick the upscaler from the source image's own generation recipe.

    Returns (key, why) with why in {"sidecar", "heuristic", "default"}.
    Precedence: the checkpoint's sidecar declaration, then a name heuristic
    on the recorded checkpoint, then backend/kind defaults. Photographic
    sources (Imagen/Gemini, Krea 2, photoreal checkpoints) get "general" —
    the anime model flattens their texture. See the design spec.
    """
    present = {m["key"] for m in discover_models()}

    def pick(key: str, why: str) -> tuple[str, str]:
        if key in present:
            return key, why
        if "general" in present:
            return "general", "default"
        return next(iter(present)), "default"   # whatever we have

    if not present:
        raise RuntimeError("No upscaler models on disk.")
    if not source_meta:
        return pick("general", "default")

    ckpt = ((source_meta.get("model_file") or {}).get("name") or "")
    stem = ckpt[:-len(".safetensors")] if ckpt.endswith(".safetensors") else ckpt

    # 1. The checkpoint's own sidecar ("upscaler": "anime"|"general").
    if stem:
        try:
            import local_generator
            declared = local_generator._model_settings(f"local:{stem}").get("upscaler")
            if declared:
                return pick(declared, "sidecar")
        except Exception:
            pass

    # 2. Name heuristic on the recorded checkpoint.
    if any(h in stem.lower() for h in _ANIME_HINTS):
        return pick("anime", "heuristic")

    # 3. Backend/kind defaults — photographic output upscales as "general".
    return pick("general", "default")


def suggested_factor(width: int, height: int) -> int:
    """Smallest factor that reaches print quality (~3300 px long edge)."""
    long_edge = max(width, height)
    for f in FACTORS:
        if long_edge * f >= 3300:
            return f
    return FACTORS[-1]


def _tiles(length: int, tile: int = TILE, overlap: int = OVERLAP) -> list[tuple[int, int]]:
    """Tile spans covering [0, length), stepping tile-overlap, last one
    aligned to the end so no sliver tile ever goes to the model."""
    if length <= tile:
        return [(0, length)]
    step = tile - overlap
    starts = list(range(0, length - tile, step)) + [length - tile]
    return [(s, s + tile) for s in starts]


def _feather_mask(h: int, w: int, scale: int) -> np.ndarray:
    """Per-tile blend weights: linear ramps over the (scaled) overlap margin
    on all four edges, floored above zero. Overlapping tiles are averaged by
    total weight, so edge tiles at the image boundary — where only one tile
    contributes — come out unchanged regardless of the ramp."""
    m = OVERLAP * scale
    ramp = np.minimum(np.arange(1, m + 1) / m, 1.0)
    wx = np.ones(w, np.float32)
    wy = np.ones(h, np.float32)
    wx[:m] = np.minimum(wx[:m], ramp)
    wx[-m:] = np.minimum(wx[-m:], ramp[::-1])
    wy[:m] = np.minimum(wy[:m], ramp)
    wy[-m:] = np.minimum(wy[-m:], ramp[::-1])
    mask = np.outer(wy, wx).astype(np.float32)
    return np.maximum(mask, 1e-3)[..., None]


def _plan(factor: int) -> list[str]:
    """Pass plan per factor: 'sr' = one 4x model pass, 'half' = Lanczos 0.5x."""
    return {2: ["sr", "half"], 4: ["sr"], 8: ["sr", "half", "sr"]}[factor]


def _count_tiles(w: int, h: int, plan: list[str], scale: int) -> int:
    total = 0
    for op in plan:
        if op == "sr":
            total += len(_tiles(w)) * len(_tiles(h))
            w, h = w * scale, h * scale
        else:
            w, h = w // 2, h // 2
    return total


def _load(key: str):
    """Load (or return the resident) model. Loads are seconds, not minutes —
    but evicting on switch still matters on a machine this full."""
    with _resident_lock:
        if _resident["key"] == key:
            return _resident["model"], _resident["scale"]
        from spandrel import ImageModelDescriptor, ModelLoader
        path = os.path.join(UPSCALERS_DIR, _MODEL_FILES[key])
        desc = ModelLoader().load_from_file(path)
        if not isinstance(desc, ImageModelDescriptor):
            raise RuntimeError(f"{_MODEL_FILES[key]} is not an image->image model.")
        model = desc.model.eval().to(_device())
        _resident.update(key=key, model=model, scale=int(desc.scale))
        return model, int(desc.scale)


def _run_pass(model, scale: int, arr: np.ndarray, on_tile: Callable[[], None]) -> np.ndarray:
    """One tiled SR pass. arr is float32 HWC in [0,1]; accumulation happens
    on CPU — the assembled output of a big pass has no business on MPS."""
    torch = _torch()
    dev = _device()
    h, w = arr.shape[:2]
    out = np.zeros((h * scale, w * scale, 3), np.float32)
    wsum = np.zeros((h * scale, w * scale, 1), np.float32)
    for y0, y1 in _tiles(h):
        for x0, x1 in _tiles(w):
            tile = arr[y0:y1, x0:x1]
            t = torch.from_numpy(tile).permute(2, 0, 1)[None].to(dev)
            with torch.no_grad():
                o = model(t)
            o = o[0].permute(1, 2, 0).clamp(0, 1).float().cpu().numpy()
            mask = _feather_mask(o.shape[0], o.shape[1], scale)
            out[y0 * scale:y1 * scale, x0 * scale:x1 * scale] += o * mask
            wsum[y0 * scale:y1 * scale, x0 * scale:x1 * scale] += mask
            on_tile()
    return out / wsum


def upscale(
    image: Image.Image,
    factor: int,
    model_key: str,
    on_step: Optional[Callable[[int, int], None]] = None,
) -> tuple[Image.Image, dict]:
    """Upscale `image` by `factor`. Returns (PIL.Image, meta dict)."""
    if factor not in FACTORS:
        raise ValueError(f"factor must be one of {FACTORS}")
    if model_key not in _MODEL_FILES:
        raise ValueError(f"Unknown upscaler model: {model_key!r}")
    src_w, src_h = image.size
    if src_w * src_h * factor * factor > MAX_OUTPUT_PIXELS:
        raise ValueError(
            f"{factor}x of {src_w}x{src_h} exceeds the "
            f"{MAX_OUTPUT_PIXELS // 1_000_000} MP output ceiling.")

    with _GPU:
        model, scale = _load(model_key)
        plan = _plan(factor)
        total = _count_tiles(src_w, src_h, plan, scale)
        done = 0

        def on_tile() -> None:
            nonlocal done
            done += 1
            if on_step:
                on_step(done, total)

        arr = np.asarray(image.convert("RGB"), np.float32) / 255.0
        for op in plan:
            if op == "sr":
                arr = _run_pass(model, scale, arr, on_tile)
            else:
                h, w = arr.shape[:2]
                im = Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8))
                arr = np.asarray(
                    im.resize((w // 2, h // 2), Image.LANCZOS), np.float32) / 255.0

    result = Image.fromarray((np.clip(arr, 0, 1) * 255.0 + 0.5).astype(np.uint8))
    meta = {
        "backend": "upscaler",
        "model_file": {"name": _MODEL_FILES[model_key], "sha256": None},
        "upscale": {
            "factor": factor,
            "model": model_key,
            "tile": TILE,
            "overlap": OVERLAP,
            "source_size": [src_w, src_h],
            "output_size": list(result.size),
            "passes": plan,
        },
        # Deterministic, but not a *generation* recipe — Regenerate means
        # "re-run the recipe that made this," which an upscale is not.
        "reproducible": False,
    }
    return result, meta
