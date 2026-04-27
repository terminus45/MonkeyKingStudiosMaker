import os
import random
from pathlib import Path
from typing import Optional, Union

import torch
from diffusers import (
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
)
from PIL import Image

from config import MODEL_ID, MODEL_CACHE_DIR, LORA_DIR, DEVICE, OUTPUT_DIR

# SDXL safetensors are ~6+ GB; SD 1.5 are ~2 GB
_SDXL_SIZE_THRESHOLD_GB = 4.0


def discover_loras() -> list[dict]:
    """Scan LORA_DIR for .safetensors / .pt LoRA files."""
    base = Path(LORA_DIR)
    entries = []
    if base.exists():
        for ext in ("*.safetensors", "*.pt"):
            for f in sorted(base.glob(ext)):
                entries.append({"name": f.stem, "path": str(f)})
    for i, entry in enumerate(entries, 1):
        entry["num"] = i
    return entries


def discover_models() -> list[dict]:
    """
    Scan MODEL_CACHE_DIR for loadable models and return a numbered list.
    Covers:
      - .safetensors / .ckpt single-file models at the top level
      - HuggingFace hub cache directories (models--org--name)
    """
    base = Path(MODEL_CACHE_DIR)
    entries = []

    if base.exists():
        # Single-file models first
        for ext in ("*.safetensors", "*.ckpt"):
            for f in sorted(base.glob(ext)):
                entries.append({
                    "name": f.stem,
                    "path": str(f),
                    "type": "local",
                })

        # HuggingFace hub-cached models
        for d in sorted(base.iterdir()):
            if d.is_dir() and d.name.startswith("models--"):
                hub_id = d.name[len("models--"):].replace("--", "/", 1)
                entries.append({
                    "name": hub_id,
                    "path": hub_id,   # passed directly to from_pretrained
                    "type": "hub",
                })

    # Assign stable numeric IDs (1-based)
    for i, entry in enumerate(entries, 1):
        entry["id"] = i

    return entries


def _is_sdxl_file(path: Path) -> bool:
    size_gb = path.stat().st_size / (1024 ** 3)
    return size_gb >= _SDXL_SIZE_THRESHOLD_GB


def _load_pipeline(
    model_path: str, dtype: torch.dtype
) -> Union[StableDiffusionPipeline, StableDiffusionXLPipeline]:
    p = Path(model_path)
    if p.is_file() and p.suffix in (".safetensors", ".ckpt"):
        if _is_sdxl_file(p):
            pipe = StableDiffusionXLPipeline.from_single_file(
                model_path,
                torch_dtype=dtype,
            )
        else:
            pipe = StableDiffusionPipeline.from_single_file(
                model_path,
                torch_dtype=dtype,
            )
    else:
        pipe = StableDiffusionPipeline.from_pretrained(
            model_path,
            torch_dtype=dtype,
            cache_dir=MODEL_CACHE_DIR,
        )
    return pipe


class ImageGenerator:
    def __init__(self):
        self.pipeline: Optional[StableDiffusionPipeline] = None
        self.loaded_model_id: Optional[str] = None
        self._active_lora: Optional[str] = None  # path of currently-fused LoRA

    def load(self, model_id: str = MODEL_ID):
        if self.loaded_model_id == model_id and self.pipeline is not None:
            return

        dtype = torch.float16 if DEVICE in ("cuda", "mps") else torch.float32
        pipe = _load_pipeline(model_id, dtype)

        # Faster scheduler
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

        if DEVICE == "mps":
            pipe = pipe.to("mps")
        elif DEVICE == "cuda":
            pipe = pipe.to("cuda")
            pipe.enable_attention_slicing()
        else:
            pipe = pipe.to("cpu")

        self.pipeline = pipe
        self.loaded_model_id = model_id
        self._active_lora = None

    def load_by_number(self, num: int):
        models = discover_models()
        match = next((m for m in models if m["id"] == num), None)
        if match is None:
            raise ValueError(f"No model with id {num}. Run GET /models to see available models.")
        self.load(match["path"])
        return match

    def _apply_lora(self, lora_path: Optional[str]):
        """Load or unload a LoRA on the current pipeline as needed."""
        if lora_path == self._active_lora:
            return
        if self._active_lora is not None:
            self.pipeline.unload_lora_weights()
            self._active_lora = None
        if lora_path:
            try:
                self.pipeline.load_lora_weights(lora_path)
                self._active_lora = lora_path
            except Exception as e:
                # Leave pipeline in clean (no-LoRA) state and surface a clear error
                try:
                    self.pipeline.unload_lora_weights()
                except Exception:
                    pass
                self._active_lora = None
                lora_name = Path(lora_path).stem
                raise RuntimeError(
                    f"LoRA '{lora_name}' is incompatible with the loaded model "
                    f"(weight size mismatch). Use a LoRA trained on the same base model."
                ) from e

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        steps: int = 20,
        guidance_scale: float = 7.5,
        width: int = 512,
        height: int = 512,
        seed: int = -1,
        lora_path: Optional[str] = None,
        lora_scale: float = 1.0,
        step_callback=None,   # callable(step: int, total: int)
    ) -> tuple[Image.Image, int]:
        if self.pipeline is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        self._apply_lora(lora_path)

        actual_seed = seed if seed >= 0 else random.randint(0, 2**32 - 1)
        gen = torch.Generator(device=DEVICE).manual_seed(actual_seed)

        call_kwargs = dict(
            prompt=prompt,
            negative_prompt=negative_prompt or None,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            generator=gen,
        )
        if lora_path:
            call_kwargs["cross_attention_kwargs"] = {"scale": lora_scale}

        if step_callback is not None:
            def _cb(pipe, step_index, timestep, callback_kwargs):
                step_callback(step_index + 1, steps)
                return callback_kwargs
            call_kwargs["callback_on_step_end"] = _cb

        result = self.pipeline(**call_kwargs)
        return result.images[0], actual_seed

    def save(self, image: Image.Image, filename: str) -> str:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, filename)
        image.save(path)
        return path


generator = ImageGenerator()
