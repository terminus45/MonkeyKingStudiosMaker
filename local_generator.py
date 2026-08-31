"""On-device image generation via diffusers (Phase 2/3 of
design-specs/local-image-generation.md).

Never imported for its side effects: torch and diffusers are imported inside
functions, so this module is safe to import on a machine without the optional
extras in requirements-local.txt. `available()` reports which is the case.

Three rules from the design spec are load-bearing here:

  * **`.safetensors` only.** The deleted pre-9341b1d generator globbed
    `*.ckpt` too. Loading a `.ckpt` is a pickle deserialisation — arbitrary
    code execution — and /generate is unauthenticated.
  * **Ids, never paths.** Callers pass an opaque id that `discover_models()`
    minted. Nothing from a request body is ever joined onto a filesystem path.
  * **One at a time.** A GPU is not parallel-safe the way a network call is;
    `_GPU` serialises generation so concurrent requests queue instead of
    thrashing or OOMing.
"""
import os
import threading
from typing import Callable, Optional

from PIL import Image

from config import (
    LOCAL_DEVICE,
    LOCAL_GUIDANCE,
    LOCAL_HIRES_DENOISE,
    LOCAL_HIRES_MAX_PIXELS,
    LOCAL_HIRES_SCALE,
    LOCAL_MODELS_DIR,
    LOCAL_NEGATIVE_PROMPT,
    LOCAL_SAMPLER,
    LOCAL_STEPS,
    LOCAL_VAE_FP32,
)

# Accepted LOCAL_SAMPLER values → (diffusers scheduler class name, from_config kwargs).
# Resolved by name so this table needs no diffusers import at module load.
#
# The default matters: from_single_file() hands back PNDMScheduler, the legacy
# sampler, which produces visibly worse coherence than DPM++ 2M with Karras
# sigmas at the same step count — and unlike the modern samplers, it does not
# reward raising the step count.
SAMPLERS: dict[str, tuple[str, dict]] = {
    "dpm++2m_karras": ("DPMSolverMultistepScheduler",
                       {"use_karras_sigmas": True, "algorithm_type": "dpmsolver++"}),
    "dpm++2m":        ("DPMSolverMultistepScheduler", {"algorithm_type": "dpmsolver++"}),
    "euler_a":        ("EulerAncestralDiscreteScheduler", {}),
    "euler":          ("EulerDiscreteScheduler", {}),
    "unipc":          ("UniPCMultistepScheduler", {}),
    "ddim":           ("DDIMScheduler", {}),
    "pndm":           ("PNDMScheduler", {}),   # diffusers' default; kept for comparison
}

# Only one generation touches the accelerator at a time. Book-PDF jobs already
# queue behind _BOOK_PDF_SEM in main.py; this is the finer-grained guard that
# also covers Character Generator requests racing a book.
_GPU = threading.BoundedSemaphore(1)

# One resident pipeline. Loading costs tens of seconds and several GB, so it is
# cached — but only ever one, because two SDXL pipelines do not fit comfortably
# in 32 GB. Selecting a different model evicts the incumbent.
_pipe = None
_pipe_model_id: Optional[str] = None
_pipe_lock = threading.Lock()

# SDXL checkpoints are ~6 GB+; SD 1.5 ~2 GB. Used both to pick the pipeline
# class and to choose a sane native resolution.
_SDXL_MIN_BYTES = 4 * 1024 ** 3


# ── Per-model settings ───────────────────────────────────────────────────────
# Steps/guidance/sampler are MODEL properties, not app properties: a Turbo
# distill wants ~8 steps at guidance 2 and produces burned output at 35/7,
# while a photoreal fine-tune wants the opposite. Settings resolve in three
# tiers, highest first:
#   1. explicit per-call override (regeneration's stored recipe — untouchable)
#   2. per-model settings (this block)
#   3. env config (LOCAL_STEPS etc.)
#
# Sources, merged with the sidecar winning: a name heuristic (zero-config
# floor for anything with turbo/lightning/hyper in the filename) and an
# optional sidecar JSON next to the checkpoint (<stem>.json). Sidecars carry
# no paths and are validated/clamped; a malformed one is treated as absent —
# discovery must never break on a bad JSON file. Trust model: whoever can
# write ./models already controls what gets executed as a model.

_TURBO_HINTS = ("turbo", "lightning", "hyper")

# key -> (validator, clamp) — anything else in a sidecar is ignored.
_SIDECAR_KEYS = {
    "steps":         lambda v: int(v) if isinstance(v, (int, float)) and 1 <= v <= 150 else None,
    "guidance":      lambda v: float(v) if isinstance(v, (int, float)) and 0 <= v <= 30 else None,
    "sampler":       lambda v: v if isinstance(v, str) and v.strip().lower() in SAMPLERS else None,
    "hires_scale":   lambda v: float(v) if isinstance(v, (int, float)) and 0 <= v <= 4 else None,
    "hires_denoise": lambda v: float(v) if isinstance(v, (int, float)) and 0 <= v <= 1 else None,
    "label":         lambda v: v.strip() if isinstance(v, str) and v.strip() else None,
    "negative":      lambda v: v.strip() if isinstance(v, str) and v.strip() else None,
    "cache_unsafe":  lambda v: bool(v) if isinstance(v, bool) else None,
}


def _model_settings(model_id: str) -> dict:
    """Effective per-model settings: name heuristic, overlaid by sidecar JSON."""
    settings: dict = {}
    try:
        path, _kind = _resolve(model_id)
    except ValueError:
        return settings

    stem = os.path.basename(path)[:-len(".safetensors")]
    if any(h in stem.lower() for h in _TURBO_HINTS):
        settings.update({"steps": 8, "guidance": 2.0})

    sidecar = os.path.join(LOCAL_MODELS_DIR, stem + ".json")
    try:
        import json
        with open(sidecar, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for key, validate in _SIDECAR_KEYS.items():
                if key in raw:
                    v = validate(raw[key])
                    if v is not None:
                        settings[key] = v
    except FileNotFoundError:
        pass
    except Exception:
        pass  # malformed sidecar == no sidecar

    return settings


# Models that have NaN-poisoned a cached run. Isolation testing showed the
# corruption survives scheduler replacement AND torch.mps.empty_cache() — only
# a full reload clears it. So after the first poisoning, a model is loaded
# fresh for every generation: the first failure pays one wasted render, every
# later generation pays only the ~12 s reload instead of a ~3 min black render
# plus retry.
_CACHE_UNSAFE: set[str] = set()


def _evict_pipeline() -> None:
    """Drop the cached pipeline so the next _load() starts clean."""
    global _pipe, _pipe_model_id
    with _pipe_lock:
        _pipe = None
        _pipe_model_id = None
    import gc
    gc.collect()
    try:
        _torch().mps.empty_cache()
    except Exception:
        pass


def _looks_poisoned(img: Image.Image) -> bool:
    """True when an output is the black frame NaN poisoning produces.

    fp16 NaN anywhere in the UNet/VAE ends as `(NaN * 255).astype(uint8)` → an
    image of exact zeros. A *legitimate* all-black render is next to impossible
    for this app's subject matter, and the false-positive cost is only one
    retried generation — while the false-negative cost is silently shipping
    black images, which is how this bug lived long enough to be user-reported.
    """
    # Per-channel extrema, not grayscale — luminance rounds (1,0,0) to 0 and
    # would flag a legitimately near-black render.
    bands = img.convert("RGB").getextrema()
    return all(mx == 0 for _, mx in bands)


def _torch():
    try:
        import torch
        return torch
    except ImportError as e:
        raise RuntimeError(
            "Local generation needs the optional extras. Run:\n"
            "    pip install -r requirements-local.txt"
        ) from e


def _device() -> str:
    """Resolve the accelerator, honouring an explicit LOCAL_DEVICE override."""
    if LOCAL_DEVICE and LOCAL_DEVICE != "auto":
        return LOCAL_DEVICE
    torch = _torch()
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _runtime_ready() -> bool:
    """Are the optional extras importable? Cheap: no model is loaded."""
    try:
        import torch  # noqa: F401
        import diffusers  # noqa: F401
        return True
    except ImportError:
        return False


def available() -> tuple[bool, str]:
    """(usable, human-readable reason). Drives the Settings status line."""
    if not _runtime_ready():
        return False, "Optional extras not installed (pip install -r requirements-local.txt)"
    if not os.path.isdir(LOCAL_MODELS_DIR):
        return False, f"No models directory at {LOCAL_MODELS_DIR}"
    if not discover_models():
        return False, f"No .safetensors checkpoints found in {LOCAL_MODELS_DIR}"
    return True, f"Ready on {_device()}"


def _checkpoints() -> list[tuple[str, str, int]]:
    """(id, filename, size_bytes) for every usable checkpoint. Non-recursive:
    LoRAs and hub caches live in subdirectories and are not base models."""
    out = []
    if not os.path.isdir(LOCAL_MODELS_DIR):
        return out
    for name in sorted(os.listdir(LOCAL_MODELS_DIR)):
        if not name.endswith(".safetensors"):
            continue                       # .ckpt is never loaded — see module docstring
        path = os.path.join(LOCAL_MODELS_DIR, name)
        if not os.path.isfile(path):
            continue
        out.append((f"local:{name[:-len('.safetensors')]}", name, os.path.getsize(path)))
    return out


def discover_models() -> list[dict]:
    """The local half of the model allow-list.

    Ids are prefixed `local:` so they cannot collide with a cloud model id and
    are obvious in logs and saved drafts.

    Returns nothing when the optional extras are missing. Scanning the
    directory would still succeed — it is pure filesystem work — but offering
    a model that cannot be loaded just moves the failure from the Settings
    picker to the middle of a generation the user is waiting on.
    """
    if not _runtime_ready():
        return []

    models = []
    for model_id, filename, size in _checkpoints():
        kind = "sdxl" if size >= _SDXL_MIN_BYTES else "sd15"
        ms = _model_settings(model_id)

        # A sidecar can pre-declare a model cache-unsafe (e.g. a checkpoint
        # known to NaN-poison reused pipelines), sparing the runtime guard its
        # one wasted render after every restart. Union only — never removes a
        # runtime-learned entry.
        if ms.get("cache_unsafe"):
            _CACHE_UNSAFE.add(model_id)

        label = ms.get("label") or model_id.split(":", 1)[1].replace("_", " ")
        hint = ""
        if ms.get("steps"):
            hint = f" · ~{ms['steps']} steps" + (" · fast" if ms["steps"] <= 12 else "")
        models.append({
            "id":   model_id,
            "name": f"{label} — on this Mac, $0.00{hint}",
            "type": kind,
        })
    return models


def _resolve(model_id: str) -> tuple[str, str]:
    """Map an opaque id back to (path, kind) via the discovered allow-list.

    The request never supplies a path; this is the only place one is built,
    and only from a filename this module itself enumerated.
    """
    for candidate, filename, size in _checkpoints():
        if candidate == model_id:
            kind = "sdxl" if size >= _SDXL_MIN_BYTES else "sd15"
            return os.path.join(LOCAL_MODELS_DIR, filename), kind
    raise ValueError(f"Unknown local model: {model_id!r}")


def _apply_sampler(pipe, name: Optional[str] = None) -> str:
    """Replace the pipeline's scheduler with the configured (or given) one.

    Built with `from_config(pipe.scheduler.config, ...)` so the checkpoint's
    own training parameters (beta schedule, timestep spacing, prediction type)
    carry over — only the sampling algorithm changes. An unknown or unusable
    sampler falls back to whatever the pipeline currently has rather than
    failing the generation. Returns the scheduler name in effect.

    `name` overrides LOCAL_SAMPLER for this call — regeneration needs the
    sampler an image was *made* with, not whatever the config says today.
    """
    name = (name or LOCAL_SAMPLER or "").strip().lower()
    entry = SAMPLERS.get(name)
    if entry is None:
        return type(pipe.scheduler).__name__

    cls_name, kwargs = entry
    try:
        import diffusers
        cls = getattr(diffusers, cls_name)
        pipe.scheduler = cls.from_config(pipe.scheduler.config, **kwargs)
    except Exception:
        # A scheduler mismatch must not cost the user their generation.
        pass
    return type(pipe.scheduler).__name__


def _negative_prompt(caller: str, model_negative: Optional[str] = None) -> Optional[str]:
    """Combine the caller's negatives with per-model and quality-floor defaults.

    The defaults are boilerplate about rendering artefacts, not subject matter,
    so they compose with a caller's negatives rather than being replaced by
    them. Set LOCAL_NEGATIVE_PROMPT="" to opt out entirely.

    Order: caller → per-model → global floor. CLIP truncates the encoded
    prompt at 77 tokens and the floor already spends ~60 of them — whatever
    exceeds the budget must be boilerplate's tail, never something the user
    explicitly asked to avoid.
    """
    parts = [p.strip() for p in (caller, model_negative, LOCAL_NEGATIVE_PROMPT)
             if p and p.strip()]
    return ", ".join(parts) or None


def _hires_target(w: int, h: int, scale: Optional[float] = None) -> Optional[tuple[int, int]]:
    """Upscaled dimensions for the second pass, or None if it should be skipped.

    Skipped when the scale is <= 1, or when the base render is already at or
    above the pixel ceiling — that is what keeps SDXL from being dragged into
    a 1536² second pass it does not need.
    """
    scale = LOCAL_HIRES_SCALE if scale is None else scale
    if scale <= 1.0:
        return None

    tw, th = w * scale, h * scale
    area = tw * th
    if area > LOCAL_HIRES_MAX_PIXELS:
        shrink = (LOCAL_HIRES_MAX_PIXELS / area) ** 0.5
        tw, th = tw * shrink, th * shrink

    snap = lambda v: max(256, int(round(v / 64)) * 64)
    tw, th = snap(tw), snap(th)

    # Not worth a whole extra pass for a marginal size bump.
    if tw * th <= w * h * 1.1:
        return None
    return tw, th


def _img2img_pipe(pipe):
    """An img2img pipeline sharing the loaded pipeline's weights.

    `from_pipe` reuses the same UNet/VAE/text encoders, so this costs no
    additional model load and no additional memory.
    """
    from diffusers import AutoPipelineForImage2Image
    p = AutoPipelineForImage2Image.from_pipe(pipe)
    p.set_progress_bar_config(disable=True)
    return p


def _load(model_id: str):
    """Return a ready pipeline for `model_id`, reusing the cached one if it matches."""
    global _pipe, _pipe_model_id

    with _pipe_lock:
        if _pipe is not None and _pipe_model_id == model_id:
            return _pipe

        torch = _torch()
        from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline

        path, kind = _resolve(model_id)

        # Evict first so the old pipeline's memory is released before the new
        # one is allocated — on a 32 GB machine, holding both can swap.
        if _pipe is not None:
            _pipe = None
            _pipe_model_id = None
            import gc
            gc.collect()

        cls = StableDiffusionXLPipeline if kind == "sdxl" else StableDiffusionPipeline
        pipe = cls.from_single_file(path, torch_dtype=torch.float16, use_safetensors=True)
        pipe = pipe.to(_device())
        pipe.set_progress_bar_config(disable=True)
        _apply_sampler(pipe)

        # SDXL's VAE overflows in fp16, so the decode must happen in fp32.
        # diffusers already does this: the SDXL pipeline checks
        # `vae.dtype == float16 and vae.config.force_upcast` and upcasts for
        # the decode itself. All that is needed is to ensure the flag is set.
        #
        # Do NOT cast the VAE with `.to(torch.float32)` here. Measured on MPS:
        # doing so makes that check False, disabling the pipeline's own upcast
        # path, and every SDXL image comes back pure black (NaN through the
        # decode). Leave the dtype alone and let diffusers handle it.
        #
        # SD 1.5 is excluded for a different reason: its pipeline does no dtype
        # reconciliation before vae.decode(), and its VAE is numerically fine
        # in fp16 anyway, so there is nothing to fix.
        if LOCAL_VAE_FP32 and kind == "sdxl" and hasattr(pipe, "vae"):
            try:
                pipe.vae.config.force_upcast = True
            except Exception:
                pass

        # Keep peak memory down so the hires pass has headroom at 768²+.
        for opt in ("enable_attention_slicing", "enable_vae_slicing", "enable_vae_tiling"):
            try:
                getattr(pipe, opt)()
            except Exception:
                pass
        # No NSFW black-image substitution: the checker frequently
        # false-positives on illustration. Note that SAFETY_STYLE_SUFFIX is
        # also NOT appended on this path (see image_backends.generate), so
        # local output carries no content guardrail — it is governed entirely
        # by the prompt and the checkpoint selected.
        if hasattr(pipe, "safety_checker"):
            pipe.safety_checker = None

        _pipe, _pipe_model_id = pipe, model_id
        return _pipe


def _dimensions(kind: str, aspect_ratio: Optional[str], width: int, height: int) -> tuple[int, int]:
    """Cloud models take an aspect-ratio string; a local pipeline takes pixels.

    Holds the *total pixel count* near the model's native area (1024² for SDXL,
    512² for SD 1.5) while matching the requested ratio, then snaps each edge
    to a multiple of 64 as the UNet requires.

    Preserving area rather than the long edge is the point. Clamping the long
    edge to `base` — the obvious implementation, and what this function did
    first — starves anything non-square: 9:16 on SD 1.5 came out 256×512, half
    the native pixel budget, which is well below what the model was trained on
    and looks like it. Matching area gives 384×640 instead.
    """
    base = 1024 if kind == "sdxl" else 512
    target_area = base * base

    ratio = 1.0
    if aspect_ratio and ":" in aspect_ratio:
        try:
            w_r, h_r = (float(v) for v in aspect_ratio.split(":", 1))
            if w_r > 0 and h_r > 0:
                ratio = w_r / h_r
        except ValueError:
            ratio = 1.0
    elif width and height:
        ratio = width / height

    w = (target_area * ratio) ** 0.5
    h = (target_area / ratio) ** 0.5

    # Multiples of 64, floored at 256 (below that SD output degrades badly) and
    # capped at 2x base so an extreme ratio cannot request a huge, slow render.
    def snap(v: float) -> int:
        return max(256, min(base * 2, int(round(v / 64)) * 64))

    return snap(w), snap(h)


def generate(
    *,
    content_prompt: str,
    style_prompt: str = "",
    negative_prompt: str = "",
    model_id: str,
    aspect_ratio: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    seed: int = -1,
    on_step: Optional[Callable[[int, int], None]] = None,
    # Per-call overrides (None = use config). These exist for regeneration:
    # reproducing an image needs the parameters it was MADE with, which the
    # metadata records and the current .env may no longer match.
    steps: Optional[int] = None,
    guidance: Optional[float] = None,
    sampler: Optional[str] = None,
    negative_raw: bool = False,      # True: caller's negative verbatim, no composition
    hires_scale: Optional[float] = None,
    hires_denoise: Optional[float] = None,
    **_ignored,
) -> tuple[Image.Image, dict]:
    """Generate one image locally. Returns (image, metadata).

    `api_key` is accepted and ignored via **_ignored — a local pipeline has no
    credential, and the dispatcher should not have to special-case that.

    Runs a base pass at the model's native resolution, then optionally a hires
    pass: upscale and re-diffuse at low denoise. Progress is reported across
    both passes as a single 0..N sequence so the UI shows one continuous bar.

    Seed: -1 draws a fresh one, and the drawn value is recorded in the
    metadata — an unrecorded random seed is the same as no seed. The hires
    pass consumes randomness too, so it gets its own generator derived
    deterministically from the base seed (seed + 1); a two-pass render
    reproduces as a whole. Generators are created on CPU: that is the
    deterministic choice diffusers documents, and it makes the recorded seed
    meaningful across devices.
    """
    import random as _random

    # Tier 2 of the settings chain: explicit argument → per-model → env config.
    ms = _model_settings(model_id)
    steps = max(1, steps if steps else ms.get("steps", LOCAL_STEPS))
    guidance = ms.get("guidance", LOCAL_GUIDANCE) if guidance is None else guidance
    sampler = sampler or ms.get("sampler")
    denoise = ms.get("hires_denoise", LOCAL_HIRES_DENOISE) if hires_denoise is None else hires_denoise
    if hires_scale is None:
        hires_scale = ms.get("hires_scale")   # None still falls through to env

    prompt = f"{content_prompt}, {style_prompt}" if style_prompt else content_prompt
    negative = ((negative_prompt or None) if negative_raw
                else _negative_prompt(negative_prompt, ms.get("negative")))

    if seed is None or seed < 0:
        seed = _random.randint(0, 2**32 - 1)

    def _attempt() -> tuple[Image.Image, dict]:
        torch = _torch()
        pipe = _load(model_id)
        _apply_sampler(pipe, sampler)
        path, kind = _resolve(model_id)
        w, h = _dimensions(kind, aspect_ratio, width, height)

        hires = _hires_target(w, h, hires_scale)
        # img2img runs int(steps * strength) actual steps, so the progress
        # total has to account for the strength, not the requested count.
        hires_steps = int(steps * denoise) if hires else 0
        total = steps + hires_steps

        # Everything needed to reproduce this render, recorded up front so the
        # dict describes what was *requested* even if the hires pass degrades.
        import model_digest
        meta = {
            "backend": "local",
            "model_id": model_id,
            "model_file": model_digest.identity(path),
            "seed": seed,
            "sampler": (sampler or LOCAL_SAMPLER or "").strip().lower(),
            "steps": steps,
            "guidance": guidance,
            "width": w,
            "height": h,
            "prompt_final": prompt,
            "negative_final": negative,
            "hires": {"ran": False},
            "reproducible": True,
        }

        def _cb_factory(offset: int):
            def _cb(pipe_ref, step_index, timestep, kwargs):
                if on_step:
                    on_step(min(offset + step_index + 1, total), total)
                return kwargs
            return _cb

        if on_step:
            on_step(0, total)

        image = pipe(
            prompt=prompt,
            negative_prompt=negative,
            num_inference_steps=steps,
            guidance_scale=guidance,
            width=w,
            height=h,
            generator=torch.Generator("cpu").manual_seed(seed),
            callback_on_step_end=_cb_factory(0),
        ).images[0]

        if not hires:
            return image, meta

        # ── Hires pass ──────────────────────────────────────────────────────
        # Lanczos gives the second pass a clean starting point; the diffusion
        # is what actually adds detail, the resample just sets the canvas.
        tw, th = hires
        try:
            upscaled = image.resize((tw, th), Image.LANCZOS)
            refiner = _img2img_pipe(pipe)
            refined = refiner(
                prompt=prompt,
                negative_prompt=negative,
                image=upscaled,
                strength=denoise,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=torch.Generator("cpu").manual_seed(seed + 1),
                callback_on_step_end=_cb_factory(steps),
            ).images[0]
            meta["hires"] = {
                "ran": True,
                "scale": LOCAL_HIRES_SCALE if hires_scale is None else hires_scale,
                "denoise": denoise,
                "width": tw, "height": th, "seed": seed + 1,
            }
            return refined, meta
        except Exception:
            # A failed refinement must not lose a good base image.
            if on_step:
                on_step(total, total)
            return image, meta

    with _GPU:                                  # one generation at a time
        # NaN-poisoning guard. Reusing a cached SDXL pipeline can poison the
        # render with fp16 NaNs (reproduced: fresh pipeline clean, cached one
        # black, same seed/params — cyberrealisticPony at 35 steps; survives
        # scheduler replacement and empty_cache, only reload clears it). The
        # result decodes to an exact-black frame. Detect it, evict the cached
        # pipeline, retry ONCE from a clean load — same seed, so a successful
        # retry is the image the caller asked for — and remember the model as
        # cache-unsafe so future generations reload instead of wasting a
        # render. The progress bar restarts on retry; honest, if slightly ugly.
        if model_id in _CACHE_UNSAFE:
            _evict_pipeline()
        image, meta = _attempt()
        if _looks_poisoned(image):
            _CACHE_UNSAFE.add(model_id)
            _evict_pipeline()
            image, meta = _attempt()
        if _looks_poisoned(image):
            raise RuntimeError(
                "Generation produced an invalid (all-black) image twice, even "
                "from a freshly loaded pipeline. This checkpoint may be "
                "numerically unstable in fp16 — try fewer steps or a different "
                "model."
            )
        if model_id in _CACHE_UNSAFE:
            _evict_pipeline()   # don't leave a poisoned-on-reuse pipe cached
        return image, meta


def refine(
    *,
    source: Image.Image,
    prompt: str,
    negative_prompt: str = "",
    model_id: str,
    strength: float = 0.45,
    seed: int = -1,
    on_step: Optional[Callable[[int, int], None]] = None,
) -> tuple[Image.Image, dict]:
    """img2img over an existing image. Returns (image, metadata).

    `prompt` arrives fully composed by the caller (the original image's
    prompt_final anchoring the subject, plus the user's instruction) — this
    function does not compose, it renders.

    The source may come from ANY backend: a cloud portrait fed through local
    img2img is a supported path, not an accident. The source is resampled to
    the target model's native area first — refining a 1024² Imagen image
    through SD 1.5 at full size would be slow and off-native for no benefit.
    """
    import random as _random

    strength = min(0.9, max(0.1, float(strength)))
    # Per-model settings apply here too — refining through a turbo model at 35
    # env steps would be exactly the mistuning this feature exists to fix.
    ms = _model_settings(model_id)
    steps = max(1, ms.get("steps", LOCAL_STEPS))
    guidance = ms.get("guidance", LOCAL_GUIDANCE)
    sampler = ms.get("sampler")
    # img2img actually runs int(steps * strength) denoising steps.
    actual = max(1, int(steps * strength))

    if seed is None or seed < 0:
        seed = _random.randint(0, 2**32 - 1)

    def _attempt() -> tuple[Image.Image, dict]:
        torch = _torch()
        pipe = _load(model_id)
        _apply_sampler(pipe, sampler)
        path, kind = _resolve(model_id)

        w, h = _dimensions(kind, None, source.width, source.height)
        canvas = source.convert("RGB").resize((w, h), Image.LANCZOS)

        import model_digest
        meta = {
            "backend": "local",
            "model_id": model_id,
            "model_file": model_digest.identity(path),
            "seed": seed,
            "sampler": (sampler or LOCAL_SAMPLER or "").strip().lower(),
            "steps": steps,
            "guidance": guidance,
            "width": w,
            "height": h,
            "prompt_final": prompt,
            "negative_final": _negative_prompt(negative_prompt, ms.get("negative")),
            "hires": {"ran": False},
            # Reproducing a refinement needs the parent file too; the caller
            # records parent_filename and the refine block alongside this.
            "reproducible": True,
        }

        def _cb(pipe_ref, step_index, timestep, kwargs):
            if on_step:
                on_step(min(step_index + 1, actual), actual)
            return kwargs

        if on_step:
            on_step(0, actual)

        refiner = _img2img_pipe(pipe)
        image = refiner(
            prompt=prompt,
            negative_prompt=meta["negative_final"],
            image=canvas,
            strength=strength,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=torch.Generator("cpu").manual_seed(seed),
            callback_on_step_end=_cb,
        ).images[0]
        return image, meta

    with _GPU:
        # Same NaN-poisoning guard as generate() — see the comment there.
        if model_id in _CACHE_UNSAFE:
            _evict_pipeline()
        image, meta = _attempt()
        if _looks_poisoned(image):
            _CACHE_UNSAFE.add(model_id)
            _evict_pipeline()
            image, meta = _attempt()
        if _looks_poisoned(image):
            raise RuntimeError(
                "Refinement produced an invalid (all-black) image twice, even "
                "from a freshly loaded pipeline. Try fewer steps or a "
                "different model."
            )
        if model_id in _CACHE_UNSAFE:
            _evict_pipeline()
        return image, meta
