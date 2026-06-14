# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start the server (activates venv, loads .env, starts with --reload)
./start.sh

# Stop the server
./stopServer.sh

# Or manually
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Install dependencies into the venv
pip install -r requirements.txt
```

Environment variables are loaded from `.env` at startup via `start.sh`. Copy `.env.example` to `.env` and set values — at minimum `ANTHROPIC_API_KEY` for the `/decompose` endpoint and `DEVICE` for GPU acceleration (`cuda`, `mps`, or `cpu`). Set `GEMINI_API_KEY` to enable the Gemini/Imagen image provider, and `MESHY_API_KEY` to enable the Figure Maker 3D generator.

API keys can also be managed at runtime from the **Settings** page (gear icon, top-left of every header), which persists them server-side to `config.json` (gitignored) and applies them without a restart. Key resolution precedence at every generation call site is **per-request override → `config.json` → environment variable** (see `settings_store.get_key`).

## Architecture

**Single-process FastAPI server** (`main.py`) that serves both the REST API and the static frontend. There are no separate processes, no database, and no build step for the frontend. The frontend lives in `frontend/` and is served as a static mount — that mount must remain last in `main.py` to avoid shadowing API routes.

### Backend modules

- **`config.py`** — all configuration via `os.getenv`. All other modules import from here; changing a default means changing it here.
- **`generator.py`** — `ImageGenerator` singleton (`generator`) wraps a `diffusers` pipeline for SD/SDXL. Loads lazily on first request (or at startup via lifespan), hot-swaps models via `load()`/`load_by_number()`, supports up to 2 simultaneous LoRAs. Model type (SD 1.5 vs SDXL) is auto-detected by file size (≥4 GB → SDXL).
- **`gemini_generator.py`** — stateless functions for Google Imagen and Gemini image generation. Lazily imports `google-genai` so the server starts even if the package is absent.
- **`meshy_generator.py`** — stateless functions for Meshy.AI text-to-3D generation (preview → refine). Lazily imports `httpx`, reads the key at call time, and `download_model()` streams to a temp file then atomic-renames. The Meshy v2 REST flow returns a GLB (no STL).
- **`settings_store.py`** — server-side API-key store. `load()`/`get_key()`/`set_keys()`/`status()`. Persists to `config.json` (atomic write + `chmod 0o600`); `status()` only ever exposes masked values. `get_key(name)` resolves `config.json` then environment.
- **`languages.py`** — registry of supported storybook languages (Chinese, Japanese, Korean). Each entry defines field names, display labels, font metadata, and the Claude system prompt for that language. `public_metadata()` strips prompts before exposing to the frontend via `GET /languages`.
- **`main.py`** — FastAPI app with image generation, story decomposition, 3D figure generation, storybook/gallery endpoints, settings endpoints, and static file serving.

### Key data flows

**Image generation** (`POST /generate/stream`): SSE endpoint runs generation in a background thread (because `diffusers` is synchronous), bridges results to an `asyncio.Queue`, and streams `{"step": N, "total": N}` progress events followed by `{"done": true, "filename": "...", "seed": N}`. The non-streaming `POST /generate` also exists for programmatic use. Both accept a `provider` field: `"sd"` (default, uses `generator.py`) or `"gemini"` (uses `gemini_generator.py`). Gemini images are saved via `generator.save()` even though the SD pipeline isn't involved.

**Story decomposition** (`POST /decompose`): Calls Claude using **forced tool use** (`tool_choice: {type: "tool", name: "submit_storybook"}`). The tool schema enforces the storybook JSON structure — the API validates the model's response against it before returning, guaranteeing structural correctness. The system prompt (from `languages.py`) is cached with `cache_control: ephemeral`. Falls back to text parsing only if the model ignores the forced tool call.

**3D figure generation** (`POST /figure/generate`): Kid-friendly Meshy.AI pipeline. Claude (`claude-haiku-4-5`, forced tool use) rewrites the child's prompt into a strong Meshy prompt — it **begins with the child's own words** and **ends with a size constraint** ("under 6 inches / 152 mm tall…"). A daemon worker thread then runs Meshy's two-stage async job (preview → refine), polling Meshy and updating a keyed in-memory job store (`_figure_jobs`, guarded by `_figure_jobs_lock`); the frontend polls `GET /figure/status/{job_id}`. Stages: `prompting → preview → refine → downloading → analyzing → done` (`error` on failure, with a per-stage timeout). On completion the worker downloads the GLB to `FIGURES_DIR` (served by `GET /figure/model/{filename}` as `model/gltf-binary`), generates a kid/parent-friendly print report via Claude, and **auto-saves** the model to the gallery (best-effort thumbnail download + `models.json` append, wrapped so a save failure never fails the job).

**Gallery persistence** — three types, all under `./gallery/`:
- **Books**: JSON files named `{slug}_{8-hex}.json`. Listed by `GET /gallery`; `list_gallery()` skips the two manifest files when globbing.
- **Images**: a `gallery/images.json` manifest (records `{id, filename, prompt, …}`). The Character Generator fire-and-forget calls `POST /gallery/image` after a successful generation. Listed by `GET /gallery/images`.
- **3D Models**: a `gallery/models.json` manifest (records `{id, glb_filename, report, filament, thumbnail_filename, …}`), written worker-side by the figure pipeline. Listed by `GET /gallery/models`.

Manifests are read/written through `_manifest_{read,append,delete}` under `_manifest_lock` with atomic temp+rename. Deletes are manifest-only (the underlying file is left in place, since it may be shared). **Route ordering matters**: the literal `/gallery/images`, `/gallery/models`, `/gallery/image/{id}`, `/gallery/model/{id}` routes are declared before the parametrized `/gallery/{book_id}` so they aren't shadowed. Images live in `./output/` (served by `GET /image/{filename}`); GLBs in `./output/figures/`. `POST /upload-image` re-encodes an uploaded image through Pillow into `OUTPUT_DIR`.

### Frontend pages

Five HTML pages in `frontend/`, each self-contained with its own JS. `GET /` redirects to `book_builder.html` (the static mount is last in `main.py`; the explicit `/` route is declared before it). Every page header carries a ⚙️ gear icon (far left) linking to Settings, and a shared nav.

| File | JS | Purpose |
|---|---|---|
| `book_builder.html` | `book_builder.js` | Full storybook workflow (decompose → edit → generate → export) — **entry point** |
| `character_generator.html` | `character_generator.js` | Single character-portrait generator via Gemini; auto-saves to the gallery |
| `figure_maker.html` | `figure_maker.js` | Kid-friendly Meshy 3D figure generator with a three.js viewer (ES module; three.js via CDN import map) |
| `gallery.html` | `gallery.js` | Tabbed gallery — Images / Books / 3D Models; 3D models open in an inline three.js viewer modal (ES module). `storybook_print.js` is loaded as a non-module first so `window.openPrintWindow` stays available |
| `settings.html` | `settings.js` | Manage API keys (Anthropic / Gemini / Meshy); masked display, show/hide, clear |

**Book builder state** is persisted to `localStorage` (key `monkeyking_bb_state`) on every image generation and project save. On load, it checks for a `?gallery_id=` query param (linking from gallery) and falls back to restoring localStorage. The project JSON schema (`version: 1`) has `concept`, `style_prompt`, `story` (DecomposeResponse shape), and `generated_images` (page number → filename map).

`book_builder.js` contains its own copy of `LANG_META` (mirrors `languages.py` minus prompts). When adding a language, both must be kept in sync — the backend is the source of truth, and `GET /languages` returns `public_metadata()` which the frontend could fetch, but currently the JS has a hard-coded copy.

### Models and LoRAs

- Models: placed as `.safetensors`/`.ckpt` files or HuggingFace hub-cached directories under `./models/`. `discover_models()` scans and assigns stable 1-based numeric IDs used by the frontend selects.
- LoRAs: `.safetensors`/`.pt` files under `./models/LORAs/`. Up to **2 LoRAs** can be active simultaneously. When 2 are used, the first is fused into the model weights (`fuse_lora()`) and the second is loaded normally — fusing permanently modifies the loaded weights, so `_fused = True` is tracked and triggers a full model reload the next time the LoRA set changes. Changing the LoRA set when `_fused` is true always forces a reload from disk.

### Export

`storybook_print.js` (shared by both print and HTML export flows) fetches each page's image, converts to base64, and assembles a self-contained HTML document with inline styles and images — no server round-trips at read time.

### Mobile (Capacitor)

`mobile/` contains a Capacitor wrapper (`com.bookbuilderbot.app`) that packages the frontend as an iOS/Android app. The web assets are copied to `mobile/www/` and synced with `npx cap sync`. The app talks to a remote server — there is no embedded backend.

```bash
cd mobile
npx cap sync          # copy frontend assets and sync plugins
npx cap open ios      # open in Xcode
npx cap open android  # open in Android Studio
```

## Agent workflow (`agents/`)

Four Claude Code sub-agents define the feature development workflow. For any non-trivial change, follow this sequence:

1. **`product-manager`** — orchestrator. Clarifies scope, defines acceptance criteria, and sequences delegation to the other agents. Always start here for new features.
2. **`design-agent`** — UI/UX spec. Produces component/layout specs as Markdown under `/design-specs/` (not final code). Runs before any implementation.
3. **`architect-agent`** — technical review. Evaluates the proposed plan for architectural consistency, data flow correctness, and breaking changes. Must approve before `developer-agent` begins, and reviews the diff again after implementation.
4. **`developer-agent`** — implementation. Writes code following the approved spec and existing conventions; runs tests before reporting completion.

Sub-agents are invoked via Claude Code's `--agent` flag or the Agent tool, pointing at the `.md` files in `agents/`.

## Adding a new language

1. Add an entry to `LANGUAGES` in `languages.py` with the required fields (field names, reading label, font stack, system prompt)
2. Add the corresponding optional fields to `PageData` and `DecomposeResponse` in `main.py`
3. Add the matching entry to `LANG_META` in `book_builder.js`
4. The gallery meta-reader (`_read_gallery_meta`), card UI, and print template pick up the new language automatically via the registry
