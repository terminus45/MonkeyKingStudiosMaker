import asyncio
import base64
import io
import json
import os
import re
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    FIGURES_DIR,
    OUTPUT_DIR,
    PRACTICE_DIR,
    SAFETY_STYLE_SUFFIX,
)
import gemini_generator
import meshy_generator
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
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(PRACTICE_DIR, exist_ok=True)
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
    provider: str = "gemini"       # always "gemini"; field kept for stale-client compat
    gemini_model: str = "imagen-4.0-fast-generate-001"
    gemini_aspect_ratio: Optional[str] = None
    gemini_key: Optional[str] = None   # per-request override (mobile clients)
    width: int = 1024
    height: int = 1024
    return_base64: bool = False
    # Legacy SD fields are accepted but ignored (pydantic default = ignore unknown)


class GenerateResponse(BaseModel):
    filename: str
    seed: int
    loaded_model: Optional[str] = None
    image_base64: Optional[str] = None


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


def _safe_style(style: Optional[str]) -> str:
    """Append the child-safety guardrail to a Style Prompt (idempotent)."""
    s = (style or "").strip()
    if SAFETY_STYLE_SUFFIX.strip().lower() in s.lower():
        return s
    return (s + SAFETY_STYLE_SUFFIX).strip()

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/book_builder.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def generation_status():
    with _gen_status_lock:
        return dict(_gen_status)



@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    req.style_prompt = _safe_style(req.style_prompt)
    try:
        if not req.gemini_model:
            raise ValueError("No Gemini model selected.")
        image = gemini_generator.generate(
            content_prompt=req.prompt,
            style_prompt=req.style_prompt,
            negative_prompt=req.negative_prompt or "",
            model_id=req.gemini_model,
            aspect_ratio=req.gemini_aspect_ratio,
            width=req.width,
            height=req.height,
            api_key=req.gemini_key or settings_store.get_key("GEMINI_API_KEY"),
        )
        filename = f"{uuid.uuid4().hex}.png"
        gemini_generator.save_image(image, filename)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    """SSE endpoint — emits step progress then a final done event with filename/seed."""
    req.style_prompt = _safe_style(req.style_prompt)
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def run():
        _status_update({"generating": True, "step": 0, "total": 1,
                        "last_filename": None, "last_seed": None, "last_model": None})
        try:
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
                api_key=req.gemini_key or settings_store.get_key("GEMINI_API_KEY"),
            )
            filename = f"{uuid.uuid4().hex}.png"
            gemini_generator.save_image(image, filename)
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
    concept: Optional[str] = ""
    style_suffix: Optional[str] = ""
    character: Optional[str] = ""          # shared main-character description
    language: Optional[str] = "zh"
    page_count: Optional[int] = 11
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

    lang = languages.get(req.language)
    # Clamp page_count to the allowed set early — must be defined before invention
    # instruction and tool build reference it.
    page_count = req.page_count if req.page_count in (11, 15, 19) else 11
    client = anthropic.Anthropic(api_key=api_key)

    concept_text = (req.concept or "").strip()
    character_text = (req.character or "").strip()

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
    safe_style = _safe_style(req.style_suffix)
    user_content += f"\n\nApply this visual style to every image_prompt: {safe_style}"
    # Unconditional count instruction — applies to both the concept and character-only paths.
    user_content += f"\n\nDecompose this into exactly {page_count} pages, numbered 1 to {page_count}."

    tool = _decompose_tool(lang, min_pages=page_count, max_pages=page_count)

    try:
        with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=16384,
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


# ── Re-check readings ──────────────────────────────────────────────────────

class RecheckRequest(BaseModel):
    language: Optional[str] = "zh"
    pages: list[PageData]
    anthropic_key: Optional[str] = None
    # language-neutral title keys for re-aligning book_title_characters
    book_title_native: Optional[str] = None
    book_title_reading: Optional[str] = None
    book_title_characters: Optional[list[CharData]] = None


@app.post("/recheck-readings")
def recheck_readings(req: RecheckRequest):
    """Re-run Claude over an existing story to correct tone marks / romanization
    and re-align characters[].  Returns the same page array (native, reading,
    characters, en) with corrections applied.  image_prompt is NOT returned —
    the frontend preserves the existing value client-side."""
    api_key = req.anthropic_key or settings_store.get_key("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set on server.")

    lang = languages.get(req.language)
    client = anthropic.Anthropic(api_key=api_key)

    n = len(req.pages)
    tool = _decompose_tool(lang, min_pages=n, max_pages=n, include_image_prompt=False)

    # Build a lean user message: strip image_prompt to save output tokens.
    native_f  = lang["native_field"]
    reading_f = lang["reading_field"]
    stripped_pages = []
    for pg in req.pages:
        entry: dict = {
            "page": pg.page,
            native_f:  getattr(pg, native_f)  or "",
            reading_f: getattr(pg, reading_f) or "",
            "en": pg.en,
        }
        if pg.characters:
            entry["characters"] = [{"c": ch.c, "p": ch.p} for ch in pg.characters]
        stripped_pages.append(entry)

    # Build the payload — inject title when present (B3: omit entirely if title is blank)
    payload: dict = {"pages": stripped_pages}
    if req.book_title_native and req.book_title_native.strip():
        title_native_f  = lang["title_native_field"]
        title_reading_f = lang["title_reading_field"]
        title_obj: dict = {
            title_native_f:  req.book_title_native,
            title_reading_f: req.book_title_reading or "",
            "book_title_characters": (
                [c.model_dump() for c in req.book_title_characters]
                if req.book_title_characters else []
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


# Accept HEAD as well as GET — the Book Builder restore flow probes each saved
# page image with a HEAD request before displaying it. (Starlette no longer
# auto-adds HEAD to GET routes, so it must be declared explicitly.)
@app.api_route("/image/{filename}", methods=["GET", "HEAD"])
def get_image(filename: str):
    if not re.fullmatch(r"[a-f0-9]{32}\.png", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Accept an uploaded image file, save it to OUTPUT_DIR, return the filename."""
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
    img_path = os.path.join(OUTPUT_DIR, req.filename)
    if not os.path.exists(img_path):
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
    _manifest_append(_IMAGES_MANIFEST, record)
    return record


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
        thumbnail_url = refine_task.get("thumbnail_url")
        thumbnail_filename = None
        try:
            if thumbnail_url:
                thumbnail_filename = f"{uuid.uuid4().hex}.png"
                thumb_dest = os.path.join(OUTPUT_DIR, thumbnail_filename)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
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


class FigureFromImageRequest(BaseModel):
    filename: str                          # portrait filename from OUTPUT_DIR
    prompt: Optional[str] = ""            # character description — used only for print report
    style: Optional[str] = ""
    story: Optional[str] = ""
    anthropic_key: Optional[str] = None
    meshy_key: Optional[str] = None


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
        img_path = os.path.join(OUTPUT_DIR, filename)
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
        thumbnail_url = task.get("thumbnail_url")
        thumbnail_filename = None
        try:
            if thumbnail_url:
                thumbnail_filename = f"{uuid.uuid4().hex}.png"
                thumb_dest = os.path.join(OUTPUT_DIR, thumbnail_filename)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
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


# ── Figure routes ─────────────────────────────────────────────────────────────

@app.post("/figure/generate")
def figure_generate(req: FigureGenerateRequest):
    """Start a figure generation job. Returns {job_id}."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

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

    img_path = os.path.join(OUTPUT_DIR, req.filename)
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Couldn't find that portrait.")

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
    """Generate a Chinese character writing-practice PDF in-process (no Claude).

    Frequency-counts the story's hanzi, picks the 10 most frequent, and renders
    a US-Letter sheet with 8 田字格 practice boxes per character (box 1 a faded
    trace) showing the character + its pinyin. Synchronous — returns the PDF.
    """
    if (req.language or "zh") != "zh":
        raise HTTPException(status_code=400, detail="Practice sheets are Chinese-only.")
    pages = [p.model_dump() for p in req.pages]
    chars = practice_sheet_local_mod.top_characters(pages, n=10)
    if not chars:
        raise HTTPException(status_code=400, detail="No Chinese characters found in this story.")
    try:
        pdf = practice_sheet_local_mod.render_pdf_bytes(
            req.book_title_zh or "", req.book_title_en or "", chars, boxes=8,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    slug = re.sub(r"[^a-z0-9]+", "_", (req.book_title_en or "practice").lower()).strip("_") or "practice"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}_practice.pdf"'},
    )


# ── Frontend static files (must be last — catches everything not matched above) ──
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
