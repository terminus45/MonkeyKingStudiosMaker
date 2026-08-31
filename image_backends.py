"""Backend-agnostic image generation.

One dispatcher sits in front of every image backend so the call sites in
main.py never branch on provider. Which backend runs is derived from the
model id alone — there is no separate `provider` field on the request, and
deliberately so: the pre-9341b1d design carried `provider: "sd" | "gemini"`
plus ~13 backend-specific fields on every request, and the two could
disagree. Here the id *is* the choice, and it already flows end-to-end
through localStorage['monkeyking_cg_draft'].model.

Phase 1 of design-specs/local-image-generation.md. The local backend module
does not exist yet; until it does, list_models() returns the cloud half and
every path behaves exactly as before.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from PIL import Image

import gemini_generator
from config import SAFETY_STYLE_SUFFIX

META_VERSION = 1


@dataclass
class GenerationResult:
    """What a generation produced, plus everything needed to reproduce it.

    `seed` is None for cloud backends — they expose no seed, and returning a
    fake number would imply a reproducibility that does not exist. The same
    honesty lives in meta["reproducible"], decided here once rather than
    re-inferred by every consumer.
    """
    image: Image.Image
    seed: Optional[int]
    meta: dict = field(default_factory=dict)


def _with_safety(style: str) -> str:
    """Append the child-safety guardrail to a style prompt (idempotent).

    Applied to **cloud backends only**. Local generation deliberately sends the
    style prompt unmodified — see the note in generate().

    Lives here rather than in the routes so the policy is decided in exactly
    one place, for all three generation call sites, from the one fact that
    determines it: which backend is about to run.
    """
    s = (style or "").strip()
    if SAFETY_STYLE_SUFFIX.strip().lower() in s.lower():
        return s
    return (s + SAFETY_STYLE_SUFFIX).strip()


class UnknownModelError(ValueError):
    """Requested model id is not in the allow-list.

    Distinct from a generation failure so the routes can answer 400 rather
    than 500 — an id that isn't offered is a bad request, not a server fault.
    """


def _local_module():
    """Return the local backend module, or None if it isn't available.

    Absent entirely until Phase 2. Once present it lazily imports torch and
    diffusers inside its own functions, so merely importing it here stays
    cheap and cannot fail on a machine without the optional ML extras.
    """
    try:
        import local_generator  # noqa: PLC0415 — optional, may not exist
        return local_generator
    except ImportError:
        return None


def list_models() -> list[dict]:
    """Every selectable model, cloud and local, each tagged with its backend.

    This is the allow-list. A model id that does not appear here cannot be
    generated with — see generate().
    """
    models = [dict(m, backend="gemini") for m in gemini_generator.GEMINI_MODELS]

    local = _local_module()
    if local is not None:
        try:
            models += [dict(m, backend="local") for m in local.discover_models()]
        except Exception:
            # A broken or half-installed local backend must never take the
            # cloud path down with it — the app's paid, working path wins.
            pass

    return models


def backend_for(model_id: str) -> Optional[str]:
    """Which backend owns this model id, or None if it is not in the allow-list."""
    for m in list_models():
        if m["id"] == model_id:
            return m["backend"]
    return None


def _versions() -> dict:
    v = {"meta_version": META_VERSION}
    for mod in ("torch", "diffusers"):
        try:
            v[mod] = __import__(mod).__version__
        except ImportError:
            pass
    return v


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
    api_key: Optional[str] = None,
    on_step: Optional[Callable[[int, int], None]] = None,
    local_overrides: Optional[dict] = None,
) -> GenerationResult:
    """Generate one image with whichever backend owns `model_id`.

    Signature mirrors gemini_generator.generate() so the call sites did not
    have to change shape, with one addition: `on_step(step, total)` is invoked
    per denoising step by backends that can report progress. Cloud calls are
    opaque and ignore it; the local backend will drive the real SSE progress
    bar in Phase 3.

    Raises ValueError if `model_id` is not in the allow-list. That is the
    point rather than a side effect: /generate is unauthenticated, so a model
    identifier out of the request body must never reach a loader as anything
    but a key looked up server-side (design-specs/local-image-generation.md,
    decision D3).

    **Safety suffix:** SAFETY_STYLE_SUFFIX is appended for cloud backends and
    NOT for local ones, by explicit choice. Callers pass the raw style prompt;
    this function decides. Note the consequence — the local path also has the
    diffusers NSFW checker disabled, so local generation applies no content
    guardrail of any kind and is governed entirely by the prompt and the
    checkpoint chosen.
    """
    if not model_id:
        raise UnknownModelError("No model selected.")

    backend = backend_for(model_id)
    if backend is None:
        raise UnknownModelError(f"Unknown model: {model_id!r}")

    created_at = datetime.now(timezone.utc).isoformat()

    if backend == "gemini":
        # Cloud generation is a single opaque call; report it as one step so
        # progress-aware callers see a consistent protocol either way.
        if on_step:
            on_step(0, 1)
        safe_style = _with_safety(style_prompt)
        image = gemini_generator.generate(
            content_prompt=content_prompt,
            style_prompt=safe_style,
            negative_prompt=negative_prompt,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            api_key=api_key,
        )
        # prompt_final mirrors gemini_generator's own composition rule.
        prompt_final = (
            f"{content_prompt}, {safe_style}" if safe_style else content_prompt
        )
        return GenerationResult(image=image, seed=None, meta={
            "backend": "gemini",
            "model_id": model_id,
            "seed": None,
            "aspect_ratio": aspect_ratio,
            "prompt_final": prompt_final,
            "negative_final": negative_prompt or None,
            "safety_suffix_applied": True,
            "reproducible": False,       # no seed exposed — a repeat is a new roll
            "versions": {"meta_version": META_VERSION},
            "created_at": created_at,
        })

    local = _local_module()
    if local is None:                        # pragma: no cover — Phase 2
        raise UnknownModelError(f"Local backend is unavailable for model {model_id!r}.")
    image, meta = local.generate(
        content_prompt=content_prompt,
        style_prompt=style_prompt,
        negative_prompt=negative_prompt,
        model_id=model_id,
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        seed=seed,
        on_step=on_step,
        **(local_overrides or {}),
    )
    return _finalize_local(image, meta, created_at)


def _finalize_local(image: Image.Image, meta: dict, created_at: str) -> GenerationResult:
    """Common local-backend meta composition (generate and refine)."""
    meta.setdefault("safety_suffix_applied", False)
    meta["versions"] = _versions()
    meta["created_at"] = created_at
    return GenerationResult(image=image, seed=meta.get("seed"), meta=meta)


def refine(
    *,
    source: Image.Image,
    prompt: str,
    instruction: str,
    parent_filename: str,
    model_id: str,
    strength: float = 0.45,
    seed: int = -1,
    on_step: Optional[Callable[[int, int], None]] = None,
) -> GenerationResult:
    """img2img refinement of an existing image — local backends only.

    The source may have been generated by any backend (cloud portraits fed
    through local img2img are a supported path); only the *refiner* must be
    local, because cloud APIs offer no img2img with these controls.
    """
    if backend_for(model_id) != "local":
        raise UnknownModelError(
            f"Refinement runs on-device; {model_id!r} is not a local model."
        )
    local = _local_module()
    if local is None:                        # pragma: no cover
        raise UnknownModelError("Local backend is unavailable.")

    image, meta = local.refine(
        source=source,
        prompt=prompt,
        model_id=model_id,
        strength=strength,
        seed=seed,
        on_step=on_step,
    )
    meta["parent_filename"] = parent_filename
    meta["refine"] = {
        "instruction": instruction,
        "strength": strength,
        "parent": parent_filename,
    }
    return _finalize_local(image, meta, datetime.now(timezone.utc).isoformat())


def save_image(image: Image.Image, filename: str, meta: Optional[dict] = None) -> str:
    """Write a generated PNG to IMAGES_DIR, embedding `meta` as a PNG chunk.

    Re-exported so callers do not reach into gemini_generator for something
    that is not Gemini-specific. The implementation stays there because that
    is where the IMAGES_DIR/OUTPUT_DIR resolution rules are documented.
    """
    return gemini_generator.save_image(image, filename, meta=meta)


def save_result(result: GenerationResult, filename: str) -> str:
    """Convenience: save a GenerationResult with its own metadata attached."""
    return save_image(result.image, filename, meta=result.meta)
