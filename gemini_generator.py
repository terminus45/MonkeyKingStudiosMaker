"""Gemini / Imagen image generation — shared library for Image Studio and Book Builder."""

import io
import os
from typing import Optional

from PIL import Image

GEMINI_MODELS = [
    {"id": "imagen-3.0-generate-002",      "name": "Imagen 3",         "type": "imagen"},
    {"id": "imagen-3.0-fast-generate-001", "name": "Imagen 3 Fast",    "type": "imagen"},
    {"id": "gemini-2.0-flash-exp",         "name": "Gemini 2.0 Flash", "type": "gemini"},
]

ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9"]


def _client():
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai package is not installed. Run: pip install google-genai"
        )
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment")
    return genai.Client(api_key=key)


def _fit_aspect_ratio(width: int, height: int) -> str:
    r = width / height
    return min(
        ASPECT_RATIOS,
        key=lambda ar: abs(int(ar.split(":")[0]) / int(ar.split(":")[1]) - r),
    )


def generate(
    content_prompt: str,
    style_prompt: str = "",
    negative_prompt: str = "",
    model_id: str = "imagen-3.0-generate-002",
    aspect_ratio: Optional[str] = None,
    width: int = 512,
    height: int = 512,
) -> Image.Image:
    from google.genai import types as gt

    client = _client()
    full_prompt = f"{content_prompt}, {style_prompt}" if style_prompt else content_prompt
    ar = aspect_ratio if aspect_ratio in ASPECT_RATIOS else _fit_aspect_ratio(width, height)
    model_type = next((m["type"] for m in GEMINI_MODELS if m["id"] == model_id), "imagen")

    if model_type == "imagen":
        result = client.models.generate_images(
            model=model_id,
            prompt=full_prompt,
            config=gt.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=ar,
                negative_prompt=negative_prompt or None,
            ),
        )
        if not result.generated_images:
            raise RuntimeError("Imagen returned no images — content may have been blocked.")
        return Image.open(io.BytesIO(result.generated_images[0].image.image_bytes))

    # Gemini multimodal generation (e.g. gemini-2.0-flash-exp)
    response = client.models.generate_content(
        model=model_id,
        contents=full_prompt,
        config=gt.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return Image.open(io.BytesIO(part.inline_data.data))
    raise RuntimeError("Gemini returned no image — try a different prompt.")
