import asyncio
import base64
import io
import json
import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_HEIGHT,
    DEFAULT_SEED,
    DEFAULT_STEPS,
    DEFAULT_WIDTH,
    MODEL_ID,
)
from generator import generator, discover_models, discover_loras
import gemini_generator
import languages


@asynccontextmanager
async def lifespan(app: FastAPI):
    generator.load()
    yield


app = FastAPI(title="BookBuilderBot", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    style_prompt: str = ""
    negative_prompt: Optional[str] = ""
    provider: str = "sd"          # "sd" | "gemini"
    gemini_model: str = "imagen-4.0-generate-001"
    gemini_aspect_ratio: Optional[str] = None
    model_id: Optional[str] = None
    model_num: Optional[int] = None
    lora_num: Optional[int] = None
    lora_path: Optional[str] = None
    lora_scale: float = Field(1.0, ge=0.0, le=2.0)
    lora_num_2: Optional[int] = None
    lora_path_2: Optional[str] = None
    lora_scale_2: float = Field(1.0, ge=0.0, le=2.0)
    steps: int = Field(DEFAULT_STEPS, ge=1, le=150)
    guidance_scale: float = Field(DEFAULT_GUIDANCE_SCALE, ge=1.0, le=30.0)
    width: int = Field(DEFAULT_WIDTH, ge=64, le=2048)
    height: int = Field(DEFAULT_HEIGHT, ge=64, le=2048)
    seed: int = Field(DEFAULT_SEED, ge=-1)
    sampler: Optional[str] = None
    clip_skip: int = Field(1, ge=1, le=12)
    return_base64: bool = False


class GenerateResponse(BaseModel):
    filename: str
    seed: int
    loaded_model: Optional[str] = None
    image_base64: Optional[str] = None


class LoadRequest(BaseModel):
    model_id: Optional[str] = None
    model_num: Optional[int] = None


# ── Generation status (shared across requests) ────────────────────────────────

_gen_status: dict = {
    "generating": False,
    "step": 0,
    "total": 0,
    "last_filename": None,
    "last_seed": None,
    "last_model": None,
}
_gen_status_lock = threading.Lock()


def _status_update(patch: dict):
    with _gen_status_lock:
        _gen_status.update(patch)

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "loaded_model": generator.loaded_model_id}


@app.get("/status")
def generation_status():
    with _gen_status_lock:
        return dict(_gen_status)


@app.get("/loras")
def list_loras():
    """List all LoRA files in the LORAs folder."""
    loras = discover_loras()
    active_paths = {l["path"] for l in generator._active_loras}
    for l in loras:
        l["loaded"] = l["path"] in active_paths
    return {"loras": loras, "active_loras": [l["path"] for l in generator._active_loras]}


@app.get("/models")
def list_models():
    """List all models available in the models folder with their numeric IDs."""
    models = discover_models()
    current = generator.loaded_model_id
    for m in models:
        m["loaded"] = (m["path"] == current or m["name"] == current)
    return {"models": models, "loaded_model": current}


@app.post("/load")
def load_model(req: LoadRequest):
    """
    Load a model by path/hub-id (model_id) or by numeric id from /models (model_num).
    """
    try:
        if req.model_num is not None:
            info = generator.load_by_number(req.model_num)
            return {"status": "loaded", "model_id": info["path"], "name": info["name"]}
        elif req.model_id:
            generator.load(req.model_id)
            return {"status": "loaded", "model_id": req.model_id}
        else:
            raise HTTPException(status_code=422, detail="Provide either model_id or model_num.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_loras(req: GenerateRequest) -> list[dict]:
    """Build the loras list from request fields (supports up to 2 LoRAs)."""
    all_loras = None  # lazy-loaded
    result = []
    for num_field, path_field, scale_field in [
        (req.lora_num,   req.lora_path,   req.lora_scale),
        (req.lora_num_2, req.lora_path_2, req.lora_scale_2),
    ]:
        if num_field is not None:
            if all_loras is None:
                all_loras = discover_loras()
            match = next((l for l in all_loras if l["num"] == num_field), None)
            if match is None:
                raise HTTPException(status_code=404, detail=f"No LoRA with num {num_field}.")
            result.append({"path": match["path"], "scale": scale_field})
        elif path_field:
            result.append({"path": path_field, "scale": scale_field})
    return result


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    try:
        if req.provider == "gemini":
            image = gemini_generator.generate(
                content_prompt=req.prompt,
                style_prompt=req.style_prompt,
                negative_prompt=req.negative_prompt or "",
                model_id=req.gemini_model,
                aspect_ratio=req.gemini_aspect_ratio,
                width=req.width,
                height=req.height,
            )
            filename = f"{uuid.uuid4().hex}.png"
            generator.save(image, filename)
            b64 = None
            if req.return_base64:
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
            return GenerateResponse(
                filename=filename,
                seed=-1,
                loaded_model=req.gemini_model,
                image_base64=b64,
            )

        # SD path
        if req.model_num is not None:
            generator.load_by_number(req.model_num)
        elif req.model_id and req.model_id != generator.loaded_model_id:
            generator.load(req.model_id)

        loras = _resolve_loras(req)
        full_prompt = f"{req.prompt}, {req.style_prompt}" if req.style_prompt else req.prompt

        image, used_seed = generator.generate(
            prompt=full_prompt,
            negative_prompt=req.negative_prompt,
            steps=req.steps,
            guidance_scale=req.guidance_scale,
            width=req.width,
            height=req.height,
            seed=req.seed,
            loras=loras,
            sampler=req.sampler,
            clip_skip=req.clip_skip,
        )

        filename = f"{uuid.uuid4().hex}.png"
        generator.save(image, filename)

        b64 = None
        if req.return_base64:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

        return GenerateResponse(
            filename=filename,
            seed=used_seed,
            loaded_model=generator.loaded_model_id,
            image_base64=b64,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    """SSE endpoint — emits step progress then a final done event with filename/seed."""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def run():
        total_steps = 1 if req.provider == "gemini" else req.steps
        _status_update({"generating": True, "step": 0, "total": total_steps,
                        "last_filename": None, "last_seed": None, "last_model": None})
        try:
            if req.provider == "gemini":
                if not req.gemini_model:
                    raise ValueError("No Gemini model selected.")
                loop.call_soon_threadsafe(queue.put_nowait, {"step": 0, "total": 1})
                image = gemini_generator.generate(
                    content_prompt=req.prompt,
                    style_prompt=req.style_prompt,
                    negative_prompt=req.negative_prompt or "",
                    model_id=req.gemini_model,
                    aspect_ratio=req.gemini_aspect_ratio,
                    width=req.width,
                    height=req.height,
                )
                filename = f"{uuid.uuid4().hex}.png"
                generator.save(image, filename)
                _status_update({
                    "generating": False,
                    "last_filename": filename,
                    "last_seed": -1,
                    "last_model": req.gemini_model,
                })
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "done": True,
                    "filename": filename,
                    "seed": -1,
                    "loaded_model": req.gemini_model,
                })
            else:
                if req.model_num is not None:
                    generator.load_by_number(req.model_num)
                elif req.model_id and req.model_id != generator.loaded_model_id:
                    generator.load(req.model_id)

                try:
                    loras = _resolve_loras(req)
                except HTTPException as e:
                    loop.call_soon_threadsafe(queue.put_nowait, {"error": e.detail})
                    _status_update({"generating": False})
                    return

                full_prompt = f"{req.prompt}, {req.style_prompt}" if req.style_prompt else req.prompt

                def on_step(step: int, total: int):
                    try:
                        _status_update({"step": step, "total": total})
                        loop.call_soon_threadsafe(queue.put_nowait, {"step": step, "total": total})
                    except Exception:
                        pass

                image, used_seed = generator.generate(
                    prompt=full_prompt,
                    negative_prompt=req.negative_prompt,
                    steps=req.steps,
                    guidance_scale=req.guidance_scale,
                    width=req.width,
                    height=req.height,
                    seed=req.seed,
                    loras=loras,
                    step_callback=on_step,
                    sampler=req.sampler,
                    clip_skip=req.clip_skip,
                )

                filename = f"{uuid.uuid4().hex}.png"
                generator.save(image, filename)
                _status_update({
                    "generating": False,
                    "last_filename": filename,
                    "last_seed": used_seed,
                    "last_model": generator.loaded_model_id,
                })
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "done": True,
                    "filename": filename,
                    "seed": used_seed,
                    "loaded_model": generator.loaded_model_id,
                })
        except Exception as e:
            import traceback; traceback.print_exc()
            _status_update({"generating": False})
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


@app.get("/gemini/models")
def list_gemini_models():
    return {"models": gemini_generator.GEMINI_MODELS}


class DecomposeRequest(BaseModel):
    concept: str
    style_suffix: Optional[str] = ""
    language: Optional[str] = "zh"


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
    # zh variant
    book_title_zh: Optional[str] = None
    book_title_pinyin: Optional[str] = None
    # ja variant
    book_title_ja: Optional[str] = None
    book_title_romaji: Optional[str] = None
    # ko variant
    book_title_ko: Optional[str] = None
    book_title_romanization: Optional[str] = None


@app.get("/languages")
def list_languages():
    """Frontend-facing language registry (without system prompts)."""
    return {"languages": languages.public_metadata(), "default": languages.DEFAULT_LANGUAGE}


def _decompose_tool(lang: dict) -> dict:
    """Build a tool definition that constrains Claude's output to the storybook schema
    for the given language. Using a tool guarantees structurally valid JSON — the API
    validates the input against this schema before returning."""
    native_f  = lang["native_field"]
    reading_f = lang["reading_field"]
    title_n_f = lang["title_native_field"]
    title_r_f = lang["title_reading_field"]
    name = lang["english_name"]
    reading_label = lang["reading_label"]
    return {
        "name": "submit_storybook",
        "description": f"Submit the decomposed 10-page {name}-English storybook.",
        "input_schema": {
            "type": "object",
            "properties": {
                title_n_f:       {"type": "string", "description": f"Book title in {name}"},
                title_r_f:       {"type": "string", "description": f"Book title {reading_label.lower()}"},
                "book_title_en": {"type": "string", "description": "Book title in English"},
                "pages": {
                    "type": "array",
                    "minItems": 10,
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "page":         {"type": "integer", "minimum": 1, "maximum": 10},
                            native_f:       {"type": "string", "description": f"Page sentence in {name}"},
                            reading_f:      {"type": "string", "description": reading_label},
                            "en":           {"type": "string", "description": "English translation"},
                            "image_prompt": {"type": "string"},
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
                        },
                        "required": ["page", native_f, reading_f, "en", "image_prompt", "characters"],
                    },
                },
            },
            "required": [title_n_f, title_r_f, "book_title_en", "pages"],
        },
    }


@app.post("/decompose", response_model=DecomposeResponse)
def decompose(req: DecomposeRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    lang = languages.get(req.language)
    client = anthropic.Anthropic(api_key=api_key)

    user_content = req.concept.strip()
    if req.style_suffix:
        user_content += f"\n\nApply this visual style to every image_prompt: {req.style_suffix}"

    tool = _decompose_tool(lang)

    try:
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=8192,
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
    return data


@app.get("/image/{filename}")
def get_image(filename: str):
    from config import OUTPUT_DIR
    if not re.fullmatch(r"[a-f0-9]{32}\.png", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Accept an uploaded image file, save it to OUTPUT_DIR, return the filename."""
    from config import OUTPUT_DIR
    data = await file.read()
    # Re-encode through Pillow to normalise format and strip metadata
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
    filename = f"{uuid.uuid4().hex}.png"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    img.save(os.path.join(OUTPUT_DIR, filename))
    return {"filename": filename}


# ── Gallery ───────────────────────────────────────────────────────────────────

GALLERY_DIR = Path(__file__).parent / "gallery"
GALLERY_DIR.mkdir(exist_ok=True)

_SAFE_ID = re.compile(r'^[a-z0-9_-]+$')


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
    }


@app.get("/gallery")
def list_gallery():
    books = []
    for p in sorted(GALLERY_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
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


# ── Frontend static files (must be last — catches everything not matched above) ──
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
