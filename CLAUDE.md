# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Data safety — never delete user-generated content (READ FIRST)

The directories **`output/`** (and its subfolders `output/images/`, `output/figures/`, `output/practice/`, `output/book_pdfs/`) and **`gallery/`** hold **irreplaceable user-generated content** — generated images, 3D models, saved books, and their manifests. These paths are **gitignored, so they are NOT recoverable from git.** Treat every file under them as precious and permanent.

Rules for this session AND every sub-agent (developer, tester, and any other):

- **Never run a wildcard/bulk delete against a real content directory.** No `rm … output/*.png`, `rm -rf output/…`, `git clean` in the repo, `find output … -delete`, `shutil.rmtree`/`os.remove` on these paths, or any equivalent. A cleanup that "removes test artifacts" must delete **only the exact files it just created, by full name** — never a glob, and never in a shared real directory.
- **Tests and ad-hoc verification must write to a temp dir** (`tmp_path`, `tempfile.mkdtemp()`, or the session scratchpad) — monkeypatch `OUTPUT_DIR`/`IMAGES_DIR`/`FIGURES_DIR`/`BOOK_PDF_DIR`/`PRACTICE_DIR`/`GALLERY_DIR` to that temp dir. Never generate or clean test files inside the real `output/` or `gallery/`.
- **When unsure whether a path holds user data, stop and ask** rather than delete. Deletion of these files is effectively irreversible.

*(This rule exists because a `rm -f output/*.png` cleanup once wiped every saved image. Do not repeat it.)*

## Commands

```bash
# Start the server (activates venv, loads .env, starts with --reload)
./start.sh

# Stop the server
./stopServer.sh

# Or manually (defaults to loopback; use --host 0.0.0.0 for LAN/phone access)
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Install dependencies into the venv
pip install -r requirements.txt
```

Environment variables are loaded from `.env` at startup via `start.sh`. Copy `.env.example` to `.env` and set values — at minimum `ANTHROPIC_API_KEY` for the `/decompose` endpoint. Set `GEMINI_API_KEY` to enable Imagen/Gemini image generation, and `MESHY_API_KEY` to enable the Figure Maker 3D generator.

API keys can also be managed at runtime from the **Settings** page (gear icon, top-left of every header), which persists them server-side to `config.json` (gitignored) and applies them without a restart. Key resolution precedence at every generation call site is **per-request override → `config.json` → environment variable** (see `settings_store.get_key`).

### Tests & checks

There is **no configured linter and no build step**. Verification is lightweight and scaled to the change (see the agent workflow). Tests under `tests/` are purpose-built per-feature scripts (not a comprehensive suite); `tester-agent` adds them for large-scale changes.

```bash
# Python tests use pytest, which is NOT in requirements.txt — install once:
pip install pytest
pytest tests/                                  # all Python tests
pytest tests/test_page_count.py                # a single file
pytest tests/test_recheck_readings.py -k decompose_tool   # a single test (by keyword)

# JS tests are plain Node scripts (no test runner); run directly:
node tests/test_storybook_print_fallback.js
node tests/test_cover_title.js

# Sanity checks used in place of a linter (what agents run before reporting done):
node --check frontend/book_builder.js
python3 -c "import ast; ast.parse(open('main.py').read())"
```

Most tests are offline (no API/network). Live paths that need real keys (e.g. the `/decompose` round-trip) are guarded/skipped when the key is absent.

## Architecture

**Single-process FastAPI server** (`main.py`) that serves both the REST API and the static frontend. There are no separate processes, no database, and no build step for the frontend. The frontend lives in `frontend/` and is served as a static mount — that mount must remain last in `main.py` to avoid shadowing API routes. The frontend is **same-origin** with the API, so **CORS is off by default**; opt in only by setting `CORS_ALLOW_ORIGINS` (comma-separated origin list — never `*`, since every endpoint is unauthenticated).

> **Known security/architecture backlog:** a read-only sweep (2026-06-21) fixed the trivial items (loopback `HOST` default, CORS lockdown, dep pinning, `.env` perms, dead `/status` removal, stale status label). Deferred items — no auth on cost-bearing endpoints, unbounded job stores, file/gallery cleanup, the 4× language-registry and dual pinyin-splitter duplication — are tracked in **`design-specs/security-architecture-backlog.md`**. The no-auth items are the natural scope of the planned auth phase.

### Backend modules

- **`config.py`** — all configuration via `os.getenv`. All other modules import from here; changing a default means changing it here. SD/LoRA/device settings have been removed; the paths are `OUTPUT_DIR`, **`IMAGES_DIR`** (defaults to `OUTPUT_DIR/images` — where generated/uploaded images are written), `FIGURES_DIR`, `PRACTICE_DIR`, `BOOK_PDF_DIR`, plus API key names, `SAFETY_STYLE_SUFFIX`, `HOST`, and `PORT`. **`HOST` defaults to `127.0.0.1`** (loopback) — the API is unauthenticated and drives paid third-party calls, so it is not LAN-reachable out of the box; set `HOST=0.0.0.0` to access from a phone/other device.
- **`gemini_generator.py`** — stateless functions for Google Imagen and Gemini image generation. Lazily imports `google-genai` so the server starts even if the package is absent. Exposes `save_image(image, filename)` to write PNGs to **`IMAGES_DIR`** (`output/images/`).
- **`meshy_generator.py`** — stateless functions for Meshy.AI text-to-3D generation (preview → refine). Lazily imports `httpx`, reads the key at call time, and `download_model()` streams to a temp file then atomic-renames. The Meshy v2 REST flow returns a GLB (no STL — the **STL is exported client-side** in `figure_maker.js` from the loaded GLB via three.js `STLExporter`, so the download button needs no server round-trip).
- **`settings_store.py`** — server-side API-key store. `load()`/`get_key()`/`set_keys()`/`status()`. Persists to `config.json` (atomic write + `chmod 0o600`); `status()` only ever exposes masked values. `get_key(name)` resolves `config.json` then environment.
- **`languages.py`** — registry of supported storybook languages (Chinese, Japanese, Korean). Each entry defines field names, display labels, font metadata, and the Claude system prompt for that language. `public_metadata()` strips prompts before exposing to the frontend via `GET /languages`.
- **`main.py`** — FastAPI app with image generation, story decomposition, 3D figure generation, storybook/gallery endpoints, settings endpoints, and static file serving.

### Key data flows

**Image generation** (`POST /generate/stream`): SSE endpoint runs Gemini/Imagen generation in a background thread, bridges results to an `asyncio.Queue`, and streams `{"step": 0, "total": 1}` then `{"done": true, "filename": "...", "seed": -1}`. The non-streaming `POST /generate` also exists for programmatic use. Both use Gemini exclusively (`gemini_generator.generate()`) and save via `gemini_generator.save_image()`. The SD pipeline has been removed.

**Story decomposition** (`POST /decompose`): Calls Claude (`claude-opus-4-8`) using **forced tool use** (`tool_choice: {type: "tool", name: "submit_storybook"}`). The tool schema enforces the storybook JSON structure — the API validates the model's response against it before returning, guaranteeing structural correctness. The system prompt (from `languages.py`) is cached with `cache_control: ephemeral`. Falls back to text parsing only if the model ignores the forced tool call. `_decompose_tool(lang, *, min_pages, max_pages, include_image_prompt)` is parameterized so it can be reused by `/recheck-readings`.

**Readings re-check** (`POST /recheck-readings`): Accepts `{language, pages: PageData[], anthropic_key?}`. Strips `image_prompt` from the pages before sending to Claude (preserving it client-side to save tokens), calls `claude-opus-4-8` with the correction system prompt from `languages.correction_prompt()` (which wraps the per-language reading rules from `languages.py`), and returns the same page array with corrected native text, reading strings, and re-aligned `characters[]`. Response is a plain dict (no `response_model`) since `image_prompt` is absent. Key resolution and error codes mirror `/decompose` exactly (503 for missing key, 502 for Claude API error). The `_decompose_tool` is called with `min_pages=max_pages=len(req.pages)` and `include_image_prompt=False` so the schema matches the actual page count and omits `image_prompt` from required fields.

**`characters[]` round-trip fix**: `readCard()` in `book_builder.js` now carries `characters[]` forward from `storyData` rather than reading from the DOM (it was never in the DOM). When a card is flagged `data-readings-stale="true"` (set when the user edits the native textarea after a Check Readings Apply), `characters` is set to `null` so the stale array is never exported as wrong ruby — it degrades to the deterministic fallback in `renderRubyText`.

**3D figure generation** (`POST /figure/generate`): Kid-friendly Meshy.AI pipeline. Claude (`claude-haiku-4-5`, forced tool use) rewrites the child's prompt into a strong Meshy prompt — it **begins with the child's own words** and **ends with a size constraint** ("under 6 inches / 152 mm tall…"). A daemon worker thread then runs Meshy's two-stage async job (preview → refine), polling Meshy and updating a keyed in-memory job store (`_figure_jobs`, guarded by `_figure_jobs_lock`); the frontend polls `GET /figure/status/{job_id}`. Stages: `prompting → preview → refine → downloading → analyzing → done` (`error` on failure, with a per-stage timeout). On completion the worker downloads the GLB to `FIGURES_DIR` (served by `GET /figure/model/{filename}` as `model/gltf-binary`), generates a kid/parent-friendly print report via Claude, and **auto-saves** the model to the gallery (best-effort thumbnail download + `models.json` append, wrapped so a save failure never fails the job).

**Gallery persistence** — three types, all under `./gallery/`:
- **Books**: JSON files named `{slug}_{8-hex}.json`. Listed by `GET /gallery`; `list_gallery()` skips the two manifest files when globbing.
- **Images**: a `gallery/images.json` manifest (records `{id, filename, prompt, story, style_prompt, model, …}`). The Character Generator fire-and-forget calls `POST /gallery/image` after a successful generation. Listed by `GET /gallery/images`. Each Images-tab card has four actions: **🔍 View Pic** (opens the image in a lightbox scaled to 85% of viewport width, capped at 82vh; `z-index` above the 3D modal, claims Escape first), **🧸 Make Figure** (same flow as the Character Generator's Create Figure — `POST /figure/generate-from-image` with the saved filename + prompt, stashes the job in `localStorage['monkeyking_fm_job']`, navigates to Figure Maker where `resumeJobIfAny()` picks it up), **↺ Reuse** (writes the saved `prompt`/`story`/`style_prompt` back into the shared-inputs store and the model into the CG draft, then navigates to the Character Generator), and **↓ Download** / **🗑 Delete**.
- **3D Models**: a `gallery/models.json` manifest (records `{id, glb_filename, report, filament, thumbnail_filename, …}`), written worker-side by the figure pipeline. Listed by `GET /gallery/models`.

Manifests are read/written through `_manifest_{read,append,delete}` under `_manifest_lock` with atomic temp+rename. Deletes are manifest-only (the underlying file is left in place, since it may be shared). **Route ordering matters**: the literal `/gallery/images`, `/gallery/models`, `/gallery/image/{id}`, `/gallery/model/{id}` routes are declared before the parametrized `/gallery/{book_id}` so they aren't shadowed.

**Image storage & resolution.** Newly generated/uploaded images are written to **`IMAGES_DIR` (`./output/images/`)**. `GET /image/{filename}` serves them via the shared helper **`_resolve_image_path(filename)`**, which checks `IMAGES_DIR` first and then falls back to the top level of `OUTPUT_DIR` — so older images and any recovered originals dropped into `./output/` still resolve. The route accepts **both GET and HEAD** (the Book Builder restore probes each saved page image with a HEAD request, and Starlette no longer auto-adds HEAD to GET routes). **Every place that reads or reuses an image by filename goes through `_resolve_image_path`** — `GET /image`, `POST /gallery/image` (existence check), `POST /figure/generate-from-image` (+ its worker), and the book-PDF image-reuse path — so the two-location split is transparent to all callers. `POST /upload-image` re-encodes an uploaded image through Pillow into `IMAGES_DIR`. GLBs live in `./output/figures/`.

### Frontend pages

Five HTML pages in `frontend/`, each self-contained with its own JS. `GET /` redirects to `book_builder.html` (the static mount is last in `main.py`; the explicit `/` route is declared before it). Every page header carries a ⚙️ gear icon (far left) linking to Settings, and a shared nav.

| File | JS | Purpose |
|---|---|---|
| `book_builder.html` | `book_builder.js` | Full storybook workflow (decompose → edit → generate → export) — **entry point** |
| `character_generator.html` | `character_generator.js` | Single character-portrait generator via Gemini; auto-saves to the gallery |
| `figure_maker.html` | `figure_maker.js` | Kid-friendly Meshy 3D figure generator (ES module; three.js via CDN import map). Single-column layout: shared inputs card → "Build my figure!" button → **full-width** three.js viewer (height `clamp(460px, 60svh, 600px)`, 50px side gutters to scroll past it). Viewer has a **⛶ fullscreen toggle** (see below). Client-side GLB→STL export via `STLExporter` |
| `gallery.html` | `gallery.js` | Tabbed gallery — Images / Books / 3D Models; 3D models open in an inline three.js viewer modal (ES module) with the same **⛶ fullscreen toggle**. `storybook_print.js` is loaded as a non-module first so `window.openPrintWindow` stays available |
| `settings.html` | `settings.js` | Manage API keys (Anthropic / Gemini / Meshy); masked display, show/hide, clear |

**Mobile nav (hamburger).** At **≤860px** the four header links collapse into a ☰ dropdown, replacing the old horizontally-scrolling row. Behavior lives in **`nav_menu.js`** — a non-module script loaded before each page's own script on every page, like `shared_inputs.js`. Because the `<header>` block is hand-copied and kept byte-identical across pages, the toggle button is **injected by the script**, not pasted into each file; adding a page therefore only needs the one `<script src="nav_menu.js">` tag. It is pure progressive enhancement — if the script never runs, `.header-nav` stays the scrolling row it has always been.

All open/closed state is the **`nav-open` class on `<header>`**; `nav_menu.js` sets no inline styles, so desktop layout is entirely the media query's business and can't be stranded in a broken inline state. Closes on link tap, outside click, Escape (which returns focus to the button), and on resize above the breakpoint. The Escape handler is **gated to when the menu is open**, so it never steals the key from the Gallery lightbox / 3D-viewer fullscreen. **Keep the `860` in `nav_menu.js`'s `BREAKPOINT` in sync with the `@media (max-width: 860px)` block in `style.css`** — every layout rule is scoped inside that block; the only base-scope addition is `.nav-toggle { display: none }`.

**3D viewer — fullscreen + lighting** (Figure Maker viewer + Gallery model modal). Both share **`viewer_fullscreen.js`** (a non-module global `window.ViewerFullscreen`, loaded before each page's module like `shared_inputs.js`): `toggle(wrapper, {onResize})`, `isMaximized()`, `onFullscreenChange()`. The mechanism is a **CSS `position:fixed; inset:0` "maximize" overlay as the baseline** (works on iPhone Safari, which lacks element Fullscreen API) with the **native Fullscreen API layered on opportunistically** (iPad/desktop). Toggling is a pure layout change — the three.js scene is **never remounted** (the existing ResizeObservers re-fit; one explicit `onResize` on `fullscreenchange` is the insurance). The ⛶ button (`.viewer-fullscreen-btn`, a white high-contrast chip) appears only once a model has loaded; **Ctrl+M** also toggles (gated to when a model is loaded, so it never steals the key elsewhere). Gallery Escape order: first Esc exits fullscreen, second closes the modal; `closeModelViewer()` force-exits fullscreen so ✕/backdrop can't strand a torn-down scene. Design spec: `design-specs/viewer-fullscreen.md`. **Lighting**: both viewers use image-based lighting (`RoomEnvironment` via `PMREMGenerator` → `scene.environment`) + ACES tone mapping so PBR materials read as bright as Meshy's studio-lit thumbnail; the generated env texture is disposed on teardown. Note: the Gallery fullscreen button is a static child of `#modelViewerCanvas`, so clearing it uses `_setModalCanvasMsg()` (preserves the button) instead of `textContent` (which would delete it).

**Book builder state** is persisted to `localStorage` (key `monkeyking_bb_state`) on every image generation and project save. On load, it checks for a `?gallery_id=` query param (linking from gallery) and falls back to restoring localStorage. The project JSON schema (`version: 1`) has `concept`, `style_prompt`, `story` (DecomposeResponse shape), and `generated_images` (page number → filename map).

`book_builder.js` contains its own copy of `LANG_META` (mirrors `languages.py` minus prompts). When adding a language, both must be kept in sync — the backend is the source of truth, and `GET /languages` returns `public_metadata()` which the frontend could fetch, but currently the JS has a hard-coded copy.

**Cross-tab shared inputs.** Character / Story / Style sit in one **canonical full-width "Your Story" card at the top of all three generation pages** (Character Generator, Book Builder, Figure Maker) — **literally identical HTML** hand-copied with a "keep identical" comment marker (no build step). The design spec is `design-specs/unified-inputs-collapsible.md` (supersedes `unified-inputs-header.md`). The three fields are synced cross-tab via `shared_inputs.js` (a non-module loaded before each page's script, exposing `window.SharedInputs`), backed by `localStorage['monkeyking_shared_inputs']`.

The element IDs are now **standardized across all three pages**: `sharedCharacterInput` (group `sharedCharacterGroup`), `sharedStoryInput` (group `sharedStoryGroup`), `sharedStyleInput` (group `sharedStyleGroup`). The collapsible `<details id="sharedMoreOptions">` wraps Story + Style; Character is always visible. A per-page `autoExpandIfContent()` function opens the `<details>` on load when Story or Style has content, and also on cross-tab sync via the `onRemote` callback.

The per-page sync wiring is unified in **`SharedInputs.bindFields(map, opts)`** — it resolves each field's element by id, optionally populates from the store, attaches debounced (or immediate when `debounce === 0`) `input→patch` listeners, and registers one `onExternalChange` that assigns `.value` directly (never dispatches synthetic input events). Each page calls it once instead of re-implementing restore/wire logic: Character Generator and Figure Maker use `debounce: 300`; **Book Builder uses `debounce: 0` + `populate: false`** (values must persist before navigation, and its own load flow does population). The three `bindFields` maps are now byte-identical: `{ character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' }`. On Book Builder load, if a saved book (`monkeyking_bb_state`) conflicts with newer shared inputs edited in another tab, it **asks the user** whether to continue the saved book or start fresh (`sharedConflictsWithSaved` + `clearProject({ keepInputs })`); reconciliation runs before the live listener is attached. There are no longer any style-preset pills on these pages (removed); the style field is a plain textarea.

Story Prompt is now optional on all three pages (including Book Builder). The `POST /decompose` endpoint accepts `concept: Optional[str] = ""` — if both concept and character are empty it returns HTTP 400; if only character is provided, Claude invents a plot from the character description alone.

**Per-page client persistence.** Several pages persist working state so navigation doesn't lose it:
- Character Generator: the generated-image session strip + active image → `localStorage['monkeyking_cg_session']`, restored on load.
- Figure Maker: the **in-flight job survives navigation** — the active `job_id` (+ `started_at`) is saved to `localStorage['monkeyking_fm_job']`; on load `resumeJobIfAny()` re-attaches the poll loop (35-min staleness cap; soft "check the Gallery" fallback if the server forgot the job, e.g. after a restart). A single-flight `_currentJobId` guard prevents a resumed loop and a fresh Generate from racing. (This replaced an earlier "leaving cancels the job" warning.)

### Models

Stable Diffusion, LoRA, and local model management have been removed. Image generation uses the Gemini API exclusively. The active model is selected from the **Settings** page (`#settingsCgModel`, persisted to `localStorage['monkeyking_cg_draft'].model`) and shared by both Character Generator and Book Builder.

The Settings page also exposes a **Book Length** select (`#settingsPages`, persisted to `localStorage['monkeyking_bb_pages']`) with options 11/15/19 pages (default 11). This controls the `page_count` sent to `/decompose` for new books. Open/saved books keep their existing length; `/recheck-readings` is not affected.

Also, the **Language** select (`#settingsLang`, persisted to `localStorage['monkeyking_bb_lang']`) controls the storybook language for new books.

### Practice Sheet (Chinese only)

A "🖌 Create Practice Sheet" button appears in the Export section of Book Builder when the active language is Chinese (`code === 'zh'`). It is hidden for Japanese and Korean via `setLanguage()`.

On click, the frontend POSTs to `POST /practice-sheet` with `book_title_en`, `book_title_zh`, `book_title_pinyin`, and the joined Chinese page text. The backend spawns a daemon worker thread and returns `{job_id}`. The frontend polls `GET /practice-sheet/status/{job_id}` every 2 seconds; on `done`, it navigates an anchor to `GET /practice-sheet/download/{job_id}` which serves the PDF as `application/pdf`.

The worker calls `practice_sheet.generate_practice_pdf_bytes()` in `practice_sheet.py`. That function sends a fixed instruction block (田字格 layout spec, font path, UP TO 8 characters, etc.) plus the story context to `claude-opus-4-8` with `tools=[{"type": "code_execution_20260120", "name": "code_execution"}]` (no `tool_choice` — server tools must not be force-named). Claude runs ReportLab 4.2.2 and the WQY ZenHei font (`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`, subfontIndex 0) inside Anthropic's sandbox to produce the PDF, then verifies it with `pdftoppm`. The app collects `file_id` values from every `bash_code_execution_tool_result` block across all `pause_turn` continuations (capped at 6 turns / 150 s), resolves which file is the PDF via `client.beta.files.retrieve_metadata()` (newest → oldest, `.filename` ending `.pdf` or `mime_type == "application/pdf"`), and downloads via `client.beta.files.download(id).read()`. The app has no dependency on reportlab — the PDF is generated entirely inside Claude's sandbox.

PDFs are saved to `PRACTICE_DIR` (`./output/practice/`, configurable via env). Job records are held in `_practice_jobs` (in-memory, mirrors `_figure_jobs`). Stages: `prompting → executing → done` (`error` on failure). Key resolution: `req.anthropic_key → settings_store.get_key("ANTHROPIC_API_KEY") → env`; 503 is returned before spawning if no key.

Three routes (declared before the static mount): `POST /practice-sheet`, `GET /practice-sheet/status/{job_id}`, `GET /practice-sheet/download/{job_id}`.

### Practice Sheet — local (Chinese only, no Claude)

A second button "✏️ Generate Practice Locally" sits next to the cloud one (same zh-only gating in `setLanguage()`). It generates the PDF **in-process with ReportLab — no Claude call**. `POST /practice-sheet/local` (synchronous; declared before the static mount) accepts `{language, book_title_zh, book_title_en, pages}` and returns the PDF directly as `application/pdf` (rejects non-zh with 400). Dependencies this path adds: **`reportlab`** and **`pycccedict`** (bundled offline CC-CEDICT); the cloud path uses neither. The same `practice_sheet_local` module is also what the **`/book-pdf`** worker appends as the last page.

`practice_sheet_local.py` is **word-based** (was per-character): it segments the story into words and shows each with pinyin **and an English translation**.
- `top_words(pages, n=8)` — greedy longest-match segmentation of each page's `zh` against **CC-CEDICT** (`pycccedict`, bundled offline), frequency-counts the words, and returns `(word, pinyin, english)` triples. Proper nouns are excluded during segmentation (CC-CEDICT capitalizes their pinyin, e.g. 大树→"Dà shù"), multi-character words are preferred over single chars, and words with no usable gloss (bare particles) are dropped. Pinyin is CC-CEDICT's numeric tones converted to diacritics (`yue4`→`yuè`); glosses are cleaned of `CL:` classifier notes / `[pinyin]` refs / leading grammatical notes.
- `render_pdf_bytes(title_zh, title_en, words)` — renders a US-Letter sheet: header (Chinese title + "Writing Practice" + English subtitle + Name/Date), then one row per word showing the word + pinyin + English and 田字格 boxes (the word traced faded once, then repeated blank across the row, grouped so a 2-char word is written as a unit). A host CJK font covering pinyin tone marks is discovered at import time (`STHeiti`/`Hiragino`/`Arial Unicode` on macOS, `wqy-zenhei` on Linux) — **no bundled font**. (`boxes=` is accepted-but-ignored for backward-compat.)

**Attribution:** the bundled dictionary is **CC-CEDICT**, licensed **CC-BY-SA 4.0** (via the `pycccedict` package) — attribution is required if distributed.

This works from each page's `zh` text alone, so it covers both freshly-built books and any loaded Gallery book.

### Book PDF (prompt/existing → printable PDF, async job)

`POST /book-pdf` runs the full storybook pipeline server-side — decompose (or an already-built story) → readings error-check → per-page image generation → HTML render → PDF (headless Chromium) → Chinese practice-sheet append → merge — and hands back one downloadable PDF, indistinguishable in layout from clicking the existing "🖨 Print / Save as PDF" button, just produced without a browser in the loop. Design spec: `design-specs/book-pdf-endpoint.md`.

Two modes, selected by `mode`: `"prompt"` (concept/character → full pipeline from scratch, `recheck_readings` locked on) and `"existing"` (caller supplies an already-decomposed `story` + optional `generated_images` page→filename map — any page whose file already exists in `OUTPUT_DIR` is **reused**, skipping generation; `recheck_readings` defaults off). A fully-reused `existing` job with `recheck_readings=false` makes **zero** paid API calls.

- **`book_pdf.py`** — `build_storybook_html(story, image_data_uris)` is a faithful Python port of `frontend/storybook_print.js`'s `buildStorybookHTML()` (same cover + ruby-page-spread markup/CSS, A4 landscape); it reuses `practice_sheet_local.py`'s already-ported pinyin-syllable splitter (`_derive_characters`) for the zh ruby fallback rather than re-porting it. Per-language `font_stack` is broadened with OS-default CJK family fallbacks (`PingFang SC`/`Noto Sans CJK SC` for zh, `Hiragino Sans`/`Noto Sans CJK JP` for ja, `Apple SD Gothic Neo`/`Noto Sans CJK KR` for ko) before the trailing generic `serif`, since a server-side Chromium render has no browser font cache to lean on — **install Noto CJK fonts (`fonts-noto-cjk`) on any Linux deploy host**, or ruby/CJK text silently falls back to tofu. `render_pdf(html_str)` lazily imports Playwright and renders via headless Chromium, locked down (`java_script_enabled=False`, every request aborted via `page.route` — data: URIs still render since they aren't routed, `set_content(..., wait_until="load")` never `goto()`). **Run `playwright install chromium` once after `pip install -r requirements.txt`** — the app starts fine without it (lazy import), but `/book-pdf` jobs fail at the `rendering` stage until it's installed. `merge_pdfs(book_bytes, practice_bytes)` appends the practice sheet via pymupdf (`fitz`); mixed page sizes/orientation (landscape A4 book + portrait Letter practice sheet) is an accepted tradeoff, not rescaled.
- **`main.py`** — `run_decompose()`/`run_recheck()` are extracted (behavior-preserving) from the bodies of `decompose()`/`recheck_readings()` so the `/book-pdf` worker can call them directly without an HTTP round-trip; the two routes are unchanged externally. `_run_book_pdf_job` is a daemon-thread worker mirroring the Figure Maker/Practice Sheet job pattern (`_book_pdf_jobs` + lock, stages `decomposing → checking-readings → illustrating (i/N) → rendering → practice-sheet → merging → done`/`error`), overlays a recheck response onto the decompose story **by page number** (preserving `image_prompt` and the story's own title fields, mirroring `book_builder.js`'s client-side `applyCheckReadings` merge), and retries a failed page image once before failing the whole job (a "printable PDF" must not silently ship a blank page). `_BOOK_PDF_SEM = threading.BoundedSemaphore(2)` bounds concurrent jobs — this is the single most expensive endpoint in the app (up to 2 opus calls + up to 19 Gemini image calls, no confirmation gate) and the bound is an interim guardrail, not a substitute for the auth/rate-limiting phase tracked in `design-specs/security-architecture-backlog.md`. Three routes (declared before the static mount): `POST /book-pdf`, `GET /book-pdf/status/{job_id}`, `GET /book-pdf/download/{job_id}` (`409` if not `done`).
- `config.py`'s `BOOK_PDF_DIR` (`./output/book_pdfs/`, configurable via env) holds the finished PDFs, created at startup like `PRACTICE_DIR`.

### Export

`storybook_print.js` (shared by both print and HTML export flows) fetches each page's image, converts to base64, and assembles a self-contained HTML document with inline styles and images — no server round-trips at read time.

## Agent workflow (`.claude/agents/`)

Seven Claude Code sub-agents define the feature development workflow. For any non-trivial change, follow this sequence:

1. **`product-manager`** — orchestrator. Clarifies scope, defines acceptance criteria, and sequences delegation to the other agents. Always start here for new features.
2. **`design-agent`** — UI/UX spec. Produces component/layout specs as Markdown under `/design-specs/` (not final code). Runs before any implementation.
3. **`architect-agent`** — technical review. Evaluates the proposed plan for architectural consistency, data flow correctness, and breaking changes. Must approve before `developer-agent` begins, and reviews the diff again after implementation.
4. **`cyber-architect`** — security audit. Invoked by `product-manager` for **security-sensitive changes** (auth/authorization, payments/billing, secrets, user data/PII, file uploads, external input, DB access, new network/API surface) — on the design and again on the diff. Produces a severity-rated report; treats Critical/High findings as blocking. Audits only; does not fix.
5. **`financials-agent`** — cost & monetization analysis. Invoked by `product-manager` for **cost- or revenue-sensitive changes** (a new/altered paid Claude/Gemini/Meshy call, a model-tier or generation-flow change, or anything touching pricing/credits/billing) — on the design and again on the diff for cost-moving changes. Produces unit economics, a monetization recommendation, and ranked cost-saving/profit/risk findings. Fetches **current** provider pricing (never from memory). Advises only; routes billing implementation to `developer-agent` (+ `cyber-architect` for the payment surface).
6. **`developer-agent`** — implementation. Writes code following the approved spec and existing conventions; runs lightweight sanity checks (not full test scripts) before reporting completion.
7. **`tester-agent`** — test-script generation. Invoked by `product-manager` **only for large-scale changes** (new subsystem, API-contract change, multi-file feature, or shared-data-flow change). Generates and runs purpose-built test scripts under `tests/`; reports bugs back rather than fixing them. Skipped for small/localized changes — scale verification effort to the size and risk of the change.

Sub-agents live in `.claude/agents/` (the canonical Claude Code project-agents directory — the former duplicate `agents/` folder was removed). They are invoked via the Agent tool (`subagent_type`) or `@.claude/agents/<name>.md`.

## Adding a new language

1. Add an entry to `LANGUAGES` in `languages.py` with the required fields (field names, reading label, font stack, system prompt)
2. Add the corresponding optional fields to `PageData` and `DecomposeResponse` in `main.py`
3. Add the matching entry to `LANG_META` in `book_builder.js`
4. Add the `<option>` to `#settingsLang` in `settings.html` (the language list is hand-copied there — keep it in sync)
5. The gallery meta-reader (`_read_gallery_meta`), card UI, and print template pick up the new language automatically via the registry
