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
from fastapi import FastAPI, HTTPException, Request
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
    negative_prompt: Optional[str] = ""
    model_id: Optional[str] = None
    model_num: Optional[int] = None
    lora_num: Optional[int] = None
    lora_path: Optional[str] = None
    lora_scale: float = Field(1.0, ge=0.0, le=2.0)
    steps: int = Field(DEFAULT_STEPS, ge=1, le=150)
    guidance_scale: float = Field(DEFAULT_GUIDANCE_SCALE, ge=1.0, le=30.0)
    width: int = Field(DEFAULT_WIDTH, ge=64, le=2048)
    height: int = Field(DEFAULT_HEIGHT, ge=64, le=2048)
    seed: int = Field(DEFAULT_SEED, ge=-1)
    return_base64: bool = False


class GenerateResponse(BaseModel):
    filename: str
    seed: int
    loaded_model: Optional[str] = None
    image_base64: Optional[str] = None


class LoadRequest(BaseModel):
    model_id: Optional[str] = None
    model_num: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "loaded_model": generator.loaded_model_id}


@app.get("/loras")
def list_loras():
    """List all LoRA files in the LORAs folder."""
    loras = discover_loras()
    active = generator._active_lora
    for l in loras:
        l["loaded"] = (l["path"] == active)
    return {"loras": loras, "active_lora": active}


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


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    try:
        # Hot-swap model if requested
        if req.model_num is not None:
            generator.load_by_number(req.model_num)
        elif req.model_id and req.model_id != generator.loaded_model_id:
            generator.load(req.model_id)

        # Resolve LoRA path
        lora_path = None
        if req.lora_num is not None:
            loras = discover_loras()
            match = next((l for l in loras if l["num"] == req.lora_num), None)
            if match is None:
                raise HTTPException(status_code=404, detail=f"No LoRA with num {req.lora_num}.")
            lora_path = match["path"]
        elif req.lora_path:
            lora_path = req.lora_path

        image, used_seed = generator.generate(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            steps=req.steps,
            guidance_scale=req.guidance_scale,
            width=req.width,
            height=req.height,
            seed=req.seed,
            lora_path=lora_path,
            lora_scale=req.lora_scale,
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
        try:
            if req.model_num is not None:
                generator.load_by_number(req.model_num)
            elif req.model_id and req.model_id != generator.loaded_model_id:
                generator.load(req.model_id)

            lora_path = None
            if req.lora_num is not None:
                loras = discover_loras()
                match = next((l for l in loras if l["num"] == req.lora_num), None)
                if match:
                    lora_path = match["path"]
            elif req.lora_path:
                lora_path = req.lora_path

            def on_step(step: int, total: int):
                loop.call_soon_threadsafe(queue.put_nowait, {"step": step, "total": total})

            image, used_seed = generator.generate(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                steps=req.steps,
                guidance_scale=req.guidance_scale,
                width=req.width,
                height=req.height,
                seed=req.seed,
                lora_path=lora_path,
                lora_scale=req.lora_scale,
                step_callback=on_step,
            )

            filename = f"{uuid.uuid4().hex}.png"
            generator.save(image, filename)
            loop.call_soon_threadsafe(queue.put_nowait, {
                "done": True,
                "filename": filename,
                "seed": used_seed,
                "loaded_model": generator.loaded_model_id,
            })
        except Exception as e:
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


_DECOMPOSE_SYSTEM = """\
You are a bilingual children's storybook author specialising in Chinese-English picture books \
for learners aged 4–8. When given a book concept, you decompose it into exactly 10 pages.

Return ONLY a valid JSON object — no markdown fences, no prose before or after — with this shape:
{
  "book_title_zh": "...",
  "book_title_pinyin": "...",
  "book_title_en": "...",
  "pages": [
    {
      "page": 1,
      "zh": "Simplified Chinese sentence (10–18 characters)",
      "pinyin": "Full pinyin string with tone marks for every syllable",
      "en": "Natural English translation (1–2 short sentences)",
      "image_prompt": "Detailed Stable Diffusion image prompt in English (25–45 words, \
no character names, describe visual scene only)",
      "characters": [
        {"c": "汉", "p": "hàn"},
        {"c": "字", "p": "zì"},
        {"c": "。", "p": ""}
      ]
    }
    // … pages 2–10
  ]
}

Rules:
- zh must be Simplified Chinese only, 10–18 characters per page
- pinyin must have tone marks on every vowel
- en must be natural children's-book English
- image_prompt must be purely visual, evocative, and self-contained — \
describe lighting, mood, setting, characters' appearance and action
- characters must contain exactly one entry per character in zh (including punctuation)
- each entry: "c" is the single character, "p" is its pinyin syllable with tone marks
- punctuation (，。！？、…—""''（）) must have "p": "" (empty string)
- neutral-tone syllables (e.g. 子 zi, 的 de) should have no tone mark\
"""


class DecomposeRequest(BaseModel):
    concept: str
    style_suffix: Optional[str] = ""


class CharData(BaseModel):
    c: str
    p: str

class PageData(BaseModel):
    page: int
    zh: str
    pinyin: str
    en: str
    image_prompt: str
    characters: Optional[list[CharData]] = None


class DecomposeResponse(BaseModel):
    book_title_zh: str
    book_title_pinyin: str
    book_title_en: str
    pages: list[PageData]


@app.post("/decompose", response_model=DecomposeResponse)
def decompose(req: DecomposeRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    client = anthropic.Anthropic(api_key=api_key)

    user_content = req.concept.strip()
    if req.style_suffix:
        user_content += f"\n\nApply this visual style to every image_prompt: {req.style_suffix}"

    try:
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": _DECOMPOSE_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    raw = ""
    for block in msg.content:
        if block.type == "text":
            raw = block.text
            break

    # Strip markdown fences if Claude wrapped anyway
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise HTTPException(status_code=500, detail="Claude returned non-JSON output.")
        data = json.loads(m.group(0))

    return data


@app.get("/image/{filename}")
def get_image(filename: str):
    from config import OUTPUT_DIR
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


# ── Gallery ───────────────────────────────────────────────────────────────────

GALLERY_DIR = Path(__file__).parent / "gallery"
GALLERY_DIR.mkdir(exist_ok=True)

_SAFE_ID = re.compile(r'^[a-z0-9_-]+$')


def _read_gallery_meta(path: Path) -> dict:
    data   = json.loads(path.read_text(encoding="utf-8"))
    story  = data.get("story", {})
    images = data.get("generated_images", {})
    return {
        "id":               path.stem,
        "title_zh":         story.get("book_title_zh", ""),
        "title_pinyin":     story.get("book_title_pinyin", ""),
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
