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
        self._active_loras: list[dict] = []  # [{path, scale}, ...]
        self._fused: bool = False             # True when a LoRA has been fused into weights

    def load(self, model_id: str = MODEL_ID):
        if self.loaded_model_id == model_id and self.pipeline is not None and not self._fused:
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
        self._active_loras = []
        self._fused = False

    def load_by_number(self, num: int):
        models = discover_models()
        match = next((m for m in models if m["id"] == num), None)
        if match is None:
            raise ValueError(f"No model with id {num}. Run GET /models to see available models.")
        self.load(match["path"])
        return match

    def _load_one_lora(self, lora: dict):
        """Load a single LoRA without adapter_name (avoids PEFT/CLIPTextModel issues)."""
        try:
            self.pipeline.load_lora_weights(lora["path"])
        except Exception as e:
            try:
                self.pipeline.unload_lora_weights()
            except Exception:
                pass
            raise RuntimeError(
                f"LoRA '{Path(lora['path']).stem}' is incompatible with the loaded model. "
                f"Use a LoRA trained on the same base model."
            ) from e

    def _apply_loras(self, loras: list[dict]):
        """Apply up to 2 LoRAs.
        - 0 LoRAs: unload any active LoRA.
        - 1 LoRA:  load normally; scale applied via cross_attention_kwargs.
        - 2 LoRAs: fuse the first into model weights, load the second normally.
          Fusing permanently modifies base weights, so we force a reload next time
          the LoRA set changes (tracked via self._fused).
        """
        paths = [l["path"] for l in loras]
        prev_paths = [l["path"] for l in self._active_loras]

        if paths == prev_paths:
            # Paths unchanged — just update scales in place (used in generate via call_kwargs).
            self._active_loras = loras
            return

        # If base weights are contaminated by a fused LoRA, must reload from scratch.
        if self._fused:
            self.load(self.loaded_model_id)  # resets _fused + _active_loras
        elif self._active_loras:
            try:
                self.pipeline.unload_lora_weights()
            except Exception:
                pass
            self._active_loras = []

        if not loras:
            return

        if len(loras) == 1:
            self._load_one_lora(loras[0])
        else:
            # Fuse first LoRA permanently into the base weights, then load second on top.
            self._load_one_lora(loras[0])
            self.pipeline.fuse_lora(lora_scale=loras[0]["scale"])
            self.pipeline.unload_lora_weights()
            self._fused = True
            self._load_one_lora(loras[1])

        self._active_loras = loras

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        steps: int = 20,
        guidance_scale: float = 7.5,
        width: int = 512,
        height: int = 512,
        seed: int = -1,
        loras: Optional[list] = None,   # [{"path": str, "scale": float}, ...]
        step_callback=None,             # callable(step: int, total: int)
    ) -> tuple[Image.Image, int]:
        if self.pipeline is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        loras = [l for l in (loras or []) if l.get("path")]
        self._apply_loras(loras)

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

        # Apply scale for the last (unfused) active LoRA via cross_attention_kwargs.
        if self._active_loras:
            call_kwargs["cross_attention_kwargs"] = {"scale": self._active_loras[-1]["scale"]}

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
