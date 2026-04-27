# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start the server (activates venv, loads .env, starts with --reload)
./start.sh

# Or manually
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Install dependencies into the venv
pip install -r requirements.txt
```

Environment variables are loaded from `.env` at startup via `start.sh`. Copy `.env.example` to `.env` and set values — at minimum `ANTHROPIC_API_KEY` for the `/decompose` endpoint and `DEVICE` for GPU acceleration (`cuda`, `mps`, or `cpu`).

## Architecture

**Single-process FastAPI server** (`main.py`) that serves both the REST API and the static frontend. There are no separate processes, no database, and no build step for the frontend.

### Backend layers

- **`config.py`** — all configuration via `os.getenv`. All other modules import from here; changing a default means changing it here.
- **`generator.py`** — `ImageGenerator` singleton (`generator`) wraps a `diffusers` pipeline. It loads lazily on first request (or at startup via lifespan), hot-swaps models via `load()`/`load_by_number()`, and manages a single active LoRA. Model type (SD 1.5 vs SDXL) is auto-detected by file size (≥4 GB → SDXL). The singleton is imported and used directly in `main.py`.
- **`main.py`** — FastAPI app with two concerns: image generation endpoints and storybook/gallery endpoints. The static frontend is mounted last at `/` to avoid shadowing API routes.

### Key data flows

**Image generation** (`POST /generate/stream`): The SSE endpoint runs generation in a background thread (because `diffusers` is synchronous), bridges results to an `asyncio.Queue`, and streams `{"step": N, "total": N}` progress events followed by `{"done": true, "filename": "...", "seed": N}`.

**Story decomposition** (`POST /decompose`): Calls Claude claude-opus-4-7 with `thinking: {type: "adaptive"}` and the `_DECOMPOSE_SYSTEM` prompt (defined inline in `main.py`). Returns a structured 10-page bilingual storybook JSON. The system prompt is cached with `cache_control: ephemeral`.

**Gallery persistence**: Books are stored as JSON files in `./gallery/` named `{slug}_{8-hex}.json`. Images live in `./output/` as UUIDs. Gallery JSON embeds image filenames (not full paths); the frontend reconstructs URLs via `GET /image/{filename}`.

### Frontend pages

Three separate HTML pages, each self-contained with its own JS:

| File | JS | Purpose |
|---|---|---|
| `index.html` | `app.js` | Single-image generator playground |
| `book_builder.html` | `book_builder.js` | Full storybook workflow (decompose → edit → generate → export) |
| `gallery.html` | `gallery.js` | Browse and reopen saved books |

**Book builder state** is persisted to `localStorage` (key `monkeyking_bb_state`) on every image generation and project save. On load, it checks for a `?gallery_id=` query param (linking from gallery) and falls back to restoring localStorage. The project JSON schema (`version: 1`) has `concept`, `style_prompt`, `story` (DecomposeResponse shape), and `generated_images` (page number → filename map).

### Models and LoRAs

- Models: placed as `.safetensors`/`.ckpt` files or HuggingFace hub-cached directories under `./models/`. `discover_models()` scans and assigns stable 1-based numeric IDs used by the frontend selects.
- LoRAs: `.safetensors`/`.pt` files under `./models/LORAs/`. Only one LoRA can be active at a time; switching calls `unload_lora_weights()` then `load_lora_weights()`. LoRA must be compatible with the loaded base model (same architecture) or generation raises a descriptive RuntimeError.

### Export

`storybook_print.js` (shared by both print and HTML export flows) fetches each page's image, converts to base64, and assembles a self-contained HTML document with inline styles and images — no server round-trips at read time.
