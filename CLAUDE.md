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

Environment variables are loaded from `.env` at startup via `start.sh`. Copy `.env.example` to `.env` and set values — at minimum `ANTHROPIC_API_KEY` for the `/decompose` endpoint. Set `GEMINI_API_KEY` to enable Imagen/Gemini image generation, and `MESHY_API_KEY` to enable the Figure Maker 3D generator.

API keys can also be managed at runtime from the **Settings** page (gear icon, top-left of every header), which persists them server-side to `config.json` (gitignored) and applies them without a restart. Key resolution precedence at every generation call site is **per-request override → `config.json` → environment variable** (see `settings_store.get_key`).

## Architecture

**Single-process FastAPI server** (`main.py`) that serves both the REST API and the static frontend. There are no separate processes, no database, and no build step for the frontend. The frontend lives in `frontend/` and is served as a static mount — that mount must remain last in `main.py` to avoid shadowing API routes.

### Backend modules

- **`config.py`** — all configuration via `os.getenv`. All other modules import from here; changing a default means changing it here. SD/LoRA/device settings have been removed; only `OUTPUT_DIR`, `FIGURES_DIR`, API key names, `SAFETY_STYLE_SUFFIX`, `HOST`, and `PORT` remain.
- **`gemini_generator.py`** — stateless functions for Google Imagen and Gemini image generation. Lazily imports `google-genai` so the server starts even if the package is absent. Exposes `save_image(image, filename)` to write PNGs to `OUTPUT_DIR`.
- **`meshy_generator.py`** — stateless functions for Meshy.AI text-to-3D generation (preview → refine). Lazily imports `httpx`, reads the key at call time, and `download_model()` streams to a temp file then atomic-renames. The Meshy v2 REST flow returns a GLB (no STL — the **STL is exported client-side** in `figure_maker.js` from the loaded GLB via three.js `STLExporter`, so the download button needs no server round-trip).
- **`settings_store.py`** — server-side API-key store. `load()`/`get_key()`/`set_keys()`/`status()`. Persists to `config.json` (atomic write + `chmod 0o600`); `status()` only ever exposes masked values. `get_key(name)` resolves `config.json` then environment.
- **`languages.py`** — registry of supported storybook languages (Chinese, Japanese, Korean). Each entry defines field names, display labels, font metadata, and the Claude system prompt for that language. `public_metadata()` strips prompts before exposing to the frontend via `GET /languages`.
- **`main.py`** — FastAPI app with image generation, story decomposition, 3D figure generation, storybook/gallery endpoints, settings endpoints, and static file serving.

### Key data flows

**Image generation** (`POST /generate/stream`): SSE endpoint runs Gemini/Imagen generation in a background thread, bridges results to an `asyncio.Queue`, and streams `{"step": 0, "total": 1}` then `{"done": true, "filename": "...", "seed": -1}`. The non-streaming `POST /generate` also exists for programmatic use. Both use Gemini exclusively (`gemini_generator.generate()`) and save via `gemini_generator.save_image()`. The SD pipeline has been removed.

**Story decomposition** (`POST /decompose`): Calls Claude using **forced tool use** (`tool_choice: {type: "tool", name: "submit_storybook"}`). The tool schema enforces the storybook JSON structure — the API validates the model's response against it before returning, guaranteeing structural correctness. The system prompt (from `languages.py`) is cached with `cache_control: ephemeral`. Falls back to text parsing only if the model ignores the forced tool call. `_decompose_tool(lang, *, min_pages, max_pages, include_image_prompt)` is parameterized so it can be reused by `/recheck-readings`.

**Readings re-check** (`POST /recheck-readings`): Accepts `{language, pages: PageData[], anthropic_key?}`. Strips `image_prompt` from the pages before sending to Claude (preserving it client-side to save tokens), calls `claude-opus-4-7` with the correction system prompt from `languages.correction_prompt()` (which wraps the per-language reading rules from `languages.py`), and returns the same page array with corrected native text, reading strings, and re-aligned `characters[]`. Response is a plain dict (no `response_model`) since `image_prompt` is absent. Key resolution and error codes mirror `/decompose` exactly (503 for missing key, 502 for Claude API error). The `_decompose_tool` is called with `min_pages=max_pages=len(req.pages)` and `include_image_prompt=False` so the schema matches the actual page count and omits `image_prompt` from required fields.

**`characters[]` round-trip fix**: `readCard()` in `book_builder.js` now carries `characters[]` forward from `storyData` rather than reading from the DOM (it was never in the DOM). When a card is flagged `data-readings-stale="true"` (set when the user edits the native textarea after a Check Readings Apply), `characters` is set to `null` so the stale array is never exported as wrong ruby — it degrades to the deterministic fallback in `renderRubyText`.

**3D figure generation** (`POST /figure/generate`): Kid-friendly Meshy.AI pipeline. Claude (`claude-haiku-4-5`, forced tool use) rewrites the child's prompt into a strong Meshy prompt — it **begins with the child's own words** and **ends with a size constraint** ("under 6 inches / 152 mm tall…"). A daemon worker thread then runs Meshy's two-stage async job (preview → refine), polling Meshy and updating a keyed in-memory job store (`_figure_jobs`, guarded by `_figure_jobs_lock`); the frontend polls `GET /figure/status/{job_id}`. Stages: `prompting → preview → refine → downloading → analyzing → done` (`error` on failure, with a per-stage timeout). On completion the worker downloads the GLB to `FIGURES_DIR` (served by `GET /figure/model/{filename}` as `model/gltf-binary`), generates a kid/parent-friendly print report via Claude, and **auto-saves** the model to the gallery (best-effort thumbnail download + `models.json` append, wrapped so a save failure never fails the job).

**Gallery persistence** — three types, all under `./gallery/`:
- **Books**: JSON files named `{slug}_{8-hex}.json`. Listed by `GET /gallery`; `list_gallery()` skips the two manifest files when globbing.
- **Images**: a `gallery/images.json` manifest (records `{id, filename, prompt, story, style_prompt, model, …}`). The Character Generator fire-and-forget calls `POST /gallery/image` after a successful generation. Listed by `GET /gallery/images`. The gallery Images tab has a **Reuse** action per card that writes the saved `prompt`/`story`/`style_prompt` back into the shared-inputs store (and the model into the CG draft) then navigates to the Character Generator.
- **3D Models**: a `gallery/models.json` manifest (records `{id, glb_filename, report, filament, thumbnail_filename, …}`), written worker-side by the figure pipeline. Listed by `GET /gallery/models`.

Manifests are read/written through `_manifest_{read,append,delete}` under `_manifest_lock` with atomic temp+rename. Deletes are manifest-only (the underlying file is left in place, since it may be shared). **Route ordering matters**: the literal `/gallery/images`, `/gallery/models`, `/gallery/image/{id}`, `/gallery/model/{id}` routes are declared before the parametrized `/gallery/{book_id}` so they aren't shadowed. Images live in `./output/` (served by `GET /image/{filename}`, which accepts **both GET and HEAD** — the Book Builder restore probes each saved page image with a HEAD request, and Starlette no longer auto-adds HEAD to GET routes); GLBs in `./output/figures/`. `POST /upload-image` re-encodes an uploaded image through Pillow into `OUTPUT_DIR`.

### Frontend pages

Five HTML pages in `frontend/`, each self-contained with its own JS. `GET /` redirects to `book_builder.html` (the static mount is last in `main.py`; the explicit `/` route is declared before it). Every page header carries a ⚙️ gear icon (far left) linking to Settings, and a shared nav.

| File | JS | Purpose |
|---|---|---|
| `book_builder.html` | `book_builder.js` | Full storybook workflow (decompose → edit → generate → export) — **entry point** |
| `character_generator.html` | `character_generator.js` | Single character-portrait generator via Gemini; auto-saves to the gallery |
| `figure_maker.html` | `figure_maker.js` | Kid-friendly Meshy 3D figure generator (ES module; three.js via CDN import map). Single-column layout: shared inputs card → "Build my figure!" button → **full-width** three.js viewer (height `clamp(460px, 60svh, 600px)`, 50px side gutters to scroll past it). Client-side GLB→STL export via `STLExporter` |
| `gallery.html` | `gallery.js` | Tabbed gallery — Images / Books / 3D Models; 3D models open in an inline three.js viewer modal (ES module). `storybook_print.js` is loaded as a non-module first so `window.openPrintWindow` stays available |
| `settings.html` | `settings.js` | Manage API keys (Anthropic / Gemini / Meshy); masked display, show/hide, clear |

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

A second button "✏️ Generate Practice Locally" sits next to the cloud one (same zh-only gating in `setLanguage()`). It generates the PDF **in-process with ReportLab — no Claude call, no dictionary**. `POST /practice-sheet/local` (synchronous; declared before the static mount) accepts `{language, book_title_zh, book_title_en, pages}` and returns the PDF directly as `application/pdf` (rejects non-zh with 400). This is the one path that adds a real dependency: **`reportlab`** (in `requirements.txt`); the cloud path does not.

`practice_sheet_local.py` does the work:
- `top_characters(pages, n=10)` — frequency-counts the hanzi across the story and returns the N most frequent as `(char, pinyin)`. Pinyin comes from each page's `characters[]` (`{c,p}`) when present; **for books without that array (older Gallery books saved before per-character tracking), it falls back to deriving per-character pinyin from `zh` + `pinyin`** via a Python port of `storybook_print.js`'s `_splitPinyinSyllables`/`_buildCharacters`. Isolated-character pinyin is lowercased.
- `render_pdf_bytes(title_zh, title_en, chars, boxes=8)` — renders a US-Letter sheet: header (Chinese title + "Writing Practice" + English subtitle + Name/Date), then one row per character showing the character + pinyin and 8 田字格 boxes (box 1 a faded trace, the rest blank with dashed crosshairs), and a footer. A host CJK font that also covers pinyin tone marks is discovered at import time (`STHeiti`/`Hiragino`/`Arial Unicode` on macOS, `wqy-zenhei` on Linux) — **no bundled font**.

This means the local sheet works both for freshly-built books (authoritative `characters[]`) and for any loaded Gallery book (derived pinyin).

### Export

`storybook_print.js` (shared by both print and HTML export flows) fetches each page's image, converts to base64, and assembles a self-contained HTML document with inline styles and images — no server round-trips at read time.

## Agent workflow (`agents/`)

Five Claude Code sub-agents define the feature development workflow. For any non-trivial change, follow this sequence:

1. **`product-manager`** — orchestrator. Clarifies scope, defines acceptance criteria, and sequences delegation to the other agents. Always start here for new features.
2. **`design-agent`** — UI/UX spec. Produces component/layout specs as Markdown under `/design-specs/` (not final code). Runs before any implementation.
3. **`architect-agent`** — technical review. Evaluates the proposed plan for architectural consistency, data flow correctness, and breaking changes. Must approve before `developer-agent` begins, and reviews the diff again after implementation.
4. **`developer-agent`** — implementation. Writes code following the approved spec and existing conventions; runs lightweight sanity checks (not full test scripts) before reporting completion.
5. **`tester-agent`** — test-script generation. Invoked by `product-manager` **only for large-scale changes** (new subsystem, API-contract change, multi-file feature, or shared-data-flow change). Generates and runs purpose-built test scripts under `tests/`; reports bugs back rather than fixing them. Skipped for small/localized changes — scale verification effort to the size and risk of the change.

Sub-agents are invoked via Claude Code's `--agent` flag or the Agent tool, pointing at the `.md` files in `agents/`.

## Adding a new language

1. Add an entry to `LANGUAGES` in `languages.py` with the required fields (field names, reading label, font stack, system prompt)
2. Add the corresponding optional fields to `PageData` and `DecomposeResponse` in `main.py`
3. Add the matching entry to `LANG_META` in `book_builder.js`
4. Add the `<option>` to `#settingsLang` in `settings.html` (the language list is hand-copied there — keep it in sync)
5. The gallery meta-reader (`_read_gallery_meta`), card UI, and print template pick up the new language automatically via the registry

## Accounts & Credits (Phase 1, behind `BILLING_ENABLED`)

**Feature flag:** Set `BILLING_ENABLED=true` in `.env` to activate the wallet subsystem. When unset (default), no database is opened, no new routes are registered, and the app behaves exactly as before. The flag gates everything — new imports, DB init, and route registration all happen inside `if BILLING_ENABLED:` guards.

### New modules

- **`billing_db.py`** — stdlib `sqlite3`, no external deps. Creates tables on first use (`init_db()` called in lifespan). Schema: `profiles`, `wallets`, `coin_ledger`, `stripe_events`. Key functions: `get_or_create_profile`, `get_wallet`, `credit_coins`, `charge_coins`, `refund_coins`, `record_stripe_event`. All writes use `BEGIN IMMEDIATE` for atomicity. Designed for Postgres portability (see inline swap notes).
- **`auth.py`** — `current_user(request) -> User` FastAPI dependency. Phase 1 uses a **DEV verifier** (reads `X-Dev-User: <id>` or `Authorization: Bearer dev:<id>` header). See module docstring for Clerk/Supabase JWT swap instructions at Phase 2. Lazy-imports `billing_db`. `DEV_AUTH` env var (default `true`) selects the verifier.
- **`billing.py`** — Stripe logic. `PACKAGES` dict is the server-authoritative coin catalog. `create_checkout_session(profile_id, package_id) -> url` and `handle_webhook(payload_bytes, sig_header)` are the two entry points. Lazily imports `stripe`.

### New routes (only when `BILLING_ENABLED=true`)

All declared before the static mount in `main.py`.

| Route | Auth | Purpose |
|---|---|---|
| `GET /wallet` | `current_user` | Return balance + transaction history |
| `GET /billing/packages` | Public | Server-authoritative package catalog |
| `POST /billing/checkout` | `current_user` | Create Stripe Checkout session; returns `{url}` |
| `POST /stripe/webhook` | Stripe signature | Credit coins after verified payment |

### Database

- **Local dev:** SQLite file at `DATABASE_URL` (default `sqlite:///./billing.db`). File is gitignored.
- **Production swap:** Set `DATABASE_URL=postgres://...` and replace `billing_db.py` with an asyncpg implementation (see inline comments in `billing_db.py`).

### Dev auth shim

`frontend/auth_client.js` (loaded as a plain script before each page's own script) exposes `window.Auth`. In dev mode it stores an `auth_id` in localStorage and adds `X-Dev-User` headers. Use `Auth.devSignIn('user_alice')` in the browser console to sign in. The module docstring describes the Clerk/Supabase replacement pattern.

### Deduction seam (unwired, Phase 1)

`billing_db.charge_coins()` and `billing_db.refund_coins()` are fully implemented and tested but not called by any generation endpoint. Phase 2 wires them via a `Depends(charge_coins(cost, reason))` FastAPI dependency on the 7 generation routes. See `design-specs/accounts-credits-architecture.md` §5 for the Phase 2 wiring plan.

### Frontend

- **`frontend/account.html` / `account.js` / `account.css`** — Wallet page: balance card, transaction history, buy-coins package selection, Stripe Checkout redirect, and `?return=success`/`?return=cancel` polling states.
- **Header auth chip** — `#authChip` element added to `book_builder.html` and `account.html`. Other pages have a `TODO` comment in their headers marking the insertion point. The chip calls `Auth.initChip()` from `auth_client.js` and silently hides itself when billing is off.

### Tests

`tests/test_billing.py` — fully offline pytest suite covering: idempotency of `credit_coins` and `refund_coins`, `record_stripe_event` dedup, balance-always-equals-ledger-sum invariant, `charge_coins` debit and `InsufficientCoins` when short, `get_or_create_profile` idempotency, and basic concurrency.
