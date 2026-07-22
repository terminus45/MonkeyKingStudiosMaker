# API Reference

HTTP API for driving the three generators programmatically: the **Character Generator** (single image), the **Book Generator** (multi-page storybook), and the **3D Figure Maker** (image/text → 3D printable model). Written for other agents and scripts — every endpoint below is verified against `main.py`.

## Base URL & transport

```
http://127.0.0.1:8000
```

- Single-process FastAPI server (`main.py`). Start it with `./start.sh`.
- `HOST` defaults to `127.0.0.1` (loopback only). To reach it from another machine, start the server with `HOST=0.0.0.0` — **but the API is unauthenticated and drives paid third-party calls, so only do this on a trusted network.** Port is `8000` (`PORT`).
- All request/response bodies are JSON (`Content-Type: application/json`) unless noted (`/upload-image` is multipart; `/generate/stream` is SSE; file endpoints return binary).
- CORS is **off** by default (frontend is same-origin). Cross-origin browser callers need `CORS_ALLOW_ORIGINS` set on the server; server-to-server callers are unaffected.
- No API-key header, no auth token. There is **no rate limiting and no authentication** — treat the whole surface as trusted-caller-only.

## API keys (provider credentials)

Endpoints that call Anthropic, Gemini, or Meshy resolve the provider key in this order:

1. **Per-request override** — a field in the request body (`anthropic_key`, `gemini_key`, or `meshy_key`).
2. **Server key store** — `config.json` (managed via the Settings page / `POST /settings/keys`).
3. **Environment variable** — `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MESHY_API_KEY`.

If none resolves, the endpoint returns **503** with a `detail` naming the missing key. As an agent you normally rely on the server-side key store or env and omit the `*_key` fields entirely.

| Subsystem | Provider(s) needed |
|---|---|
| Character Generator (`/generate*`) | Gemini |
| Book Generator (`/decompose`, `/recheck-readings`) | Anthropic |
| Book PDF (`/book-pdf*`) | Anthropic (prompt mode / recheck) + Gemini (any page not reused) — either or both may be skippable depending on the request (see below) |
| 3D Figure Maker (`/figure/*`) | Meshy (required) + Anthropic (optional, for the print report) |

---

# 1. Character Generator

Generates a single image via Google Imagen / Gemini. A child-safety suffix is appended to the style prompt server-side automatically.

## `POST /generate`

Synchronous. Generates one image, saves it to `output/images/`, returns the filename.

**Request body** (`GenerateRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `prompt` | string | **required** | The subject / character description. |
| `style_prompt` | string | `""` | Visual style. A safety guardrail is appended server-side. |
| `negative_prompt` | string | `""` | Things to avoid. |
| `gemini_model` | string | `"imagen-4.0-fast-generate-001"` | Model id — see `GET /gemini/models`. Must be non-empty. |
| `gemini_aspect_ratio` | string \| null | `null` | One of `1:1`, `3:4`, `4:3`, `9:16`, `16:9`. If null, derived from width/height. |
| `width` | int | `1024` | |
| `height` | int | `1024` | |
| `return_base64` | bool | `false` | When true, also return the PNG inline as base64. |
| `gemini_key` | string \| null | `null` | Per-request Gemini key override. |

**Response** (`GenerateResponse`, `200`):

```json
{
  "filename": "a1b2c3...ef.png",
  "seed": -1,
  "loaded_model": "imagen-4.0-fast-generate-001",
  "image_base64": null
}
```

Fetch the image bytes at **`GET /image/{filename}`** (supports GET and HEAD; media type `image/png`). `seed` is always `-1` (Gemini does not expose one).

> **Image storage.** Generated and uploaded images are written to `output/images/`. `GET /image/{filename}` resolves that folder first, then falls back to the top level of `output/` (where older or manually-recovered images live), so callers never need to know which location a file is in. Every endpoint that takes a saved image filename (`/gallery/image`, `/figure/generate-from-image`, `/book-pdf` reuse) checks both locations the same way.

**Errors:** `500` with `detail` on any generation failure (missing/invalid key surfaces here as the underlying provider error).

**Example:**

```bash
curl -s http://127.0.0.1:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a friendly cartoon monkey king","style_prompt":"soft watercolor picture-book","gemini_model":"imagen-4.0-fast-generate-001"}'
```

## `POST /generate/stream`

Same request body as `/generate`, but returns **Server-Sent Events** (`text/event-stream`). Use this for progress UX; the payload is otherwise identical.

Event sequence (each line is `data: <json>\n\n`):

```
data: {"step": 0, "total": 1}
data: {"done": true, "filename": "a1b2c3...png", "seed": -1, "loaded_model": "imagen-4.0-fast-generate-001"}
```

On failure a single `{"error": "<message>"}` event is emitted instead of `done`. The stream closes after `done` or `error`.

## `GET /gemini/models`

Lists selectable image models with human labels (including per-image price).

```json
{ "models": [
  {"id": "imagen-4.0-generate-001",       "name": "Imagen 4 ($0.04/image)",        "type": "imagen"},
  {"id": "imagen-4.0-fast-generate-001",  "name": "Imagen 4 Fast ($0.02/image)",   "type": "imagen"},
  {"id": "imagen-4.0-ultra-generate-001", "name": "Imagen 4 Ultra ($0.06/image)",  "type": "imagen"},
  {"id": "gemini-2.5-flash-image",        "name": "Gemini 2.5 Flash (~$0.04/image)","type": "gemini"}
]}
```

## Saving to the gallery (optional)

After a successful generation you may register the image so it appears in the gallery:

**`POST /gallery/image`** — body `{ "filename", "prompt"?, "story"?, "style_prompt"?, "model"? }`. `filename` must be a `[a-f0-9]{32}.png` that exists on disk (in `output/images/` or `output/`). Returns the created record (with an 8-hex `id`). List via **`GET /gallery/images`**; delete a record via **`DELETE /gallery/image/{id}`** (manifest-only; the PNG is left in place).

---

# 2. Book Generator

Turns a concept and/or character into a structured multi-page bilingual storybook via Claude (`claude-opus-4-8`, forced tool use → structurally validated JSON). Supported languages: **Chinese (`zh`)**, **Japanese (`ja`)**, **Korean (`ko`)**. Call `GET /languages` for the live registry.

## `POST /decompose`

**Request body** (`DecomposeRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `concept` | string | `""` | Story prompt / plot seed. |
| `character` | string | `""` | Main-character description (kept consistent across every page). |
| `style_suffix` | string | `""` | Visual style applied to every page's `image_prompt`. Safety suffix appended server-side. |
| `language` | string | `"zh"` | `zh` \| `ja` \| `ko`. |
| `page_count` | int | `11` | Clamped to one of `11`, `15`, `19` (anything else → 11). |
| `anthropic_key` | string \| null | `null` | Per-request key override. |

**At least one of `concept` or `character` must be non-empty**, else `400`. If only `character` is given, Claude invents a fitting plot.

**Response** (`DecomposeResponse`, `200`) — a language-tagged storybook. Title and per-page fields vary by language (native + reading variant). For `zh`:

```json
{
  "book_title_en": "The Monkey King's First Friend",
  "book_title_zh": "美猴王的第一个朋友",
  "book_title_pinyin": "měi hóu wáng de dì yī gè péng you",
  "book_title_characters": [ {"c": "美", "p": "měi"}, {"c": "猴", "p": "hóu"} ],
  "language": "zh",
  "pages": [
    {
      "page": 1,
      "zh": "从前有一只猴子。",
      "pinyin": "cóng qián yǒu yì zhī hóu zi.",
      "en": "Once there was a monkey.",
      "image_prompt": "A friendly cartoon monkey standing on a green hill, soft watercolor...",
      "characters": [ {"c": "从", "p": "cóng"}, {"c": "前", "p": "qián"} ]
    }
  ]
}
```

Field name mapping by language:

| Language | native text | reading | title native | title reading |
|---|---|---|---|---|
| `zh` | `zh` | `pinyin` | `book_title_zh` | `book_title_pinyin` |
| `ja` | `ja` | `romaji` | `book_title_ja` | `book_title_romaji` |
| `ko` | `ko` | `romanization` | `book_title_ko` | `book_title_romanization` |

`characters[]` is a per-token `{c, p}` array (character/token + its reading) used for ruby alignment; present on each page and on the title. `page` is 1-indexed; the `pages` array length equals the resolved `page_count`.

Render each page's image with the Character Generator (`/generate` using the page's `image_prompt`), then fetch at `/image/{filename}`.

**Errors:** `503` (Anthropic key missing), `400` (neither concept nor character), `502` (Claude API error), `500` (model returned unparseable output).

**Example:**

```bash
curl -s http://127.0.0.1:8000/decompose \
  -H 'Content-Type: application/json' \
  -d '{"character":"a brave little monkey king in golden armor","language":"zh","page_count":11}'
```

## `POST /recheck-readings`

Re-validates and corrects the reading annotations (pinyin/romaji/romanization) and re-aligns `characters[]` for an existing set of pages, without regenerating the story. Strips `image_prompt` before sending to Claude (preserve it client-side).

**Request body** (`RecheckRequest`): `{ "language", "pages": PageData[], "anthropic_key"?, "book_title_native"?, "book_title_reading"?, "book_title_characters"? }`. Each `PageData` matches a page from `/decompose` (page number, native text, reading, `en`, optional `characters`).

**Response:** the same page array with corrected native text, readings, and re-aligned `characters[]`. Errors mirror `/decompose` (`503`, `502`).

## `GET /languages`

```json
{ "languages": [ /* per-language metadata: field names, labels, fonts (no system prompts) */ ], "default": "zh" }
```

## Book gallery (persisted storybooks)

- **`POST /gallery`** — save a book JSON (arbitrary storybook payload). Returns an id.
- **`GET /gallery`** — list saved books (metadata).
- **`GET /gallery/{book_id}`** — fetch one saved book.
- **`DELETE /gallery/{book_id}`** — remove it.

---

# 3. Book PDF

Runs the full storybook pipeline server-side and hands back one downloadable, printable PDF: decompose (or an already-built story) → readings error-check → per-page image generation → HTML render → PDF (headless Chromium) → Chinese practice-sheet append → merge. **Asynchronous** — start a job, then poll for status, same pattern as the 3D Figure Maker and the Practice Sheet.

This is the single most expensive endpoint in the app in its worst case (`mode="prompt"`, nothing reused: up to 2 Claude opus calls + up to 19 Gemini image calls, no confirmation gate) and the cheapest in its best case (`mode="existing"`, everything reused, readings check off: zero paid calls, pure local rendering). Design spec: `design-specs/book-pdf-endpoint.md`.

## `POST /book-pdf`

**Request body** (`BookPDFRequest`):

| Field | Type | Default | Applies to | Notes |
|---|---|---|---|---|
| `mode` | `"prompt"` \| `"existing"` | `"prompt"` | both | Selects the pipeline entry point. |
| `concept` | string | `""` | `prompt` | Same semantics as `/decompose`'s `concept`. |
| `character` | string | `""` | `prompt` | Same semantics as `/decompose`'s `character`. |
| `style_suffix` | string | `""` | `prompt` | Same semantics as `/decompose`'s `style_suffix`. |
| `language` | string | `"zh"` | both | `zh` \| `ja` \| `ko`. For `existing`, must match `story.language` if `story` carries one — `400` on mismatch. |
| `page_count` | int | `11` | `prompt` | **Must be exactly** `11`, `15`, or `19` — unlike `/decompose`, this is a strict `400` on any other value, not a silent clamp. Ignored for `existing`. |
| `story` | object | `null` | `existing` | **Required**, must have a non-empty `pages` array. Same shape `/decompose` returns — pass a finished Book Builder project's `story` object verbatim. |
| `generated_images` | `dict[str, str]` (page number as string key → `[a-f0-9]{32}.png`) | `null` | `existing` | Pages present here with a file that actually exists on disk (`output/images/` or `output/`) are **reused**, skipping generation; everything else is generated. A malformed filename is `400`. |
| `recheck_readings` | bool \| null | `null` | both | Resolves per-mode: **locked `true`** for `prompt` (not overridable), **`false`** for `existing` unless explicitly set `true`. |
| `gemini_model` | string | `"imagen-4.0-fast-generate-001"` | both | Only matters for pages that need generating. |
| `anthropic_key`, `gemini_key` | string \| null | `null` | both | Per-request overrides, same resolution order as every other endpoint. |

Returns `{"job_id": "<32-hex>"}`.

**Errors:** `400` (unknown `language`; `prompt` mode with neither `concept` nor `character`; `prompt` mode with `page_count` not in `{11,15,19}`; `existing` mode with missing/empty `story.pages`; `language`/`story.language` mismatch; a malformed `generated_images` filename). `503` (Anthropic key needed but missing — any `prompt`-mode job, or `recheck_readings` resolving `true`; Gemini key needed but missing — at least one page isn't reusable). `429` if too many book-pdf jobs are already running (a small `BoundedSemaphore`, not full rate limiting).

## `GET /book-pdf/status/{job_id}`

`job_id` must be 32-hex (`400` otherwise); unknown id → `404`. Returns the full job record:

```json
{
  "job_id": "…",
  "stage": "illustrating",
  "progress": 46,
  "current_page": 5,
  "total_pages": 11,
  "pages_generated": 5,
  "pages_reused": 0,
  "practice_sheet_included": true,
  "book_title_en": "The Monkey King's First Friend",
  "pdf_filename": null,
  "error": null,
  "created_at": "2026-07-20T…Z"
}
```

**Stages** (in order): `decomposing` → `checking-readings` → `illustrating` → `rendering` → `practice-sheet` → `merging` → `done`. Terminal states: **`done`** and **`error`** (with `error` message). `current_page`/`total_pages` in the `illustrating` stage reflect only the pages actually being generated (not the whole book) — a caller reusing 10/11 images sees `1/1`, not `11/11`. `practice_sheet_included` is `false` for non-Chinese books or when zero Chinese characters were found (not a failure).

## `GET /book-pdf/download/{job_id}`

`job_id` must be 32-hex (`400` otherwise); unknown id → `404`; **`409`** if `stage` isn't yet `done`. Serves the PDF as `application/pdf` with a filename derived from the book's English title (slugified, mirrors `/practice-sheet/download`'s pattern).

## End-to-end example (existing Book Builder project → PDF, cheapest path)

```bash
JOB=$(curl -s http://127.0.0.1:8000/book-pdf \
  -H 'Content-Type: application/json' \
  -d '{"mode":"existing","language":"zh","story":<your DecomposeResponse JSON>,"generated_images":{"1":"<filename>.png", ...}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')

while :; do
  S=$(curl -s http://127.0.0.1:8000/book-pdf/status/$JOB)
  echo "$S" | python3 -c 'import sys,json;r=json.load(sys.stdin);print(r["stage"],r["progress"])'
  echo "$S" | grep -q '"stage": "done"' && break
  echo "$S" | grep -q '"stage": "error"' && { echo "$S"; exit 1; }
  sleep 2
done

curl -s -o book.pdf http://127.0.0.1:8000/book-pdf/download/$JOB
```

---

# 4. 3D Figure Maker

Turns a text prompt **or** an existing generated image into a 3D-printable model via Meshy.AI (preview → refine). **Asynchronous** — you start a job, then poll for status. Requires a Meshy key; the Anthropic key is optional (used only for the kid/parent print report and, in the text path, prompt enhancement).

## Start a job

### `POST /figure/generate` — from a text prompt

**Request body** (`FigureGenerateRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `prompt` | string | **required** | The thing to model. Must be non-empty (`400` otherwise). |
| `style` | string | `""` | Shared style prompt. Safety suffix appended server-side. |
| `story` | string | `""` | Context/pose hint. |
| `anthropic_key` | string \| null | `null` | Required in practice — text path enhances the prompt and writes the report. |
| `meshy_key` | string \| null | `null` | Meshy key override. |

Returns `{"job_id": "<32-hex>"}`. **Errors:** `400` (empty prompt), `503` (Meshy or Anthropic key missing).

### `POST /figure/generate-from-image` — from a saved portrait

**Request body** (`FigureFromImageRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `filename` | string | **required** | An existing `[a-f0-9]{32}.png` on disk — `output/images/` or `output/` (e.g. from `/generate`). |
| `prompt` | string | `""` | Character description — used only for the print report. |
| `style` | string | `""` | |
| `story` | string | `""` | |
| `anthropic_key` | string \| null | `null` | Optional — report degrades gracefully if absent. |
| `meshy_key` | string \| null | `null` | |

Returns `{"job_id": "<32-hex>"}`. **Errors:** `400` (filename not `[a-f0-9]{32}.png` — the form produced by `/generate` and `/upload-image`), `404` (file not found), `503` (Meshy key missing).

## Poll status

### `GET /figure/status/{job_id}`

`job_id` must be 32-hex (`400` otherwise); unknown id → `404`. Returns the full job record. Poll every ~2–3 s until `stage` is `done` or `error`.

```json
{
  "job_id": "…",
  "stage": "refine",
  "progress": 50,
  "enhanced_prompt": "…",
  "glb_filename": null,
  "report": null,
  "filament": null,
  "error": null
}
```

**Stages** (in order): `prompting` → `preview` → `refine` → `downloading` → `analyzing` → `done`. Terminal states: **`done`** (success) and **`error`** (with `error` message). `progress` is 0–100. (The image path skips `refine`, going `prompting` → `preview` → `downloading` → `analyzing` → `done`.)

On `done` the record carries:
- `glb_filename` — fetch the model at **`GET /figure/model/{filename}`** (media type `model/gltf-binary`). Filename is `{job_id}.glb`.
- `report` — 2–3 sentence kid/parent-friendly print note.
- `filament` — short filament suggestion, e.g. `"PLA · Bright Orange"`.

> **STL:** there is no server STL endpoint. STL is exported client-side from the loaded GLB (three.js `STLExporter`). Agents that need STL must convert the GLB themselves.

On completion the job also **auto-saves** to the model gallery. List via **`GET /gallery/models`** (records include `glb_filename`, `prompt`, `enhanced_prompt`, `report`, `filament`, `thumbnail_filename`, `created_at`, 8-hex `id`); delete a record via **`DELETE /gallery/model/{id}`** (manifest-only).

## End-to-end example (text → GLB)

```bash
# 1. start
JOB=$(curl -s http://127.0.0.1:8000/figure/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a small cartoon monkey king figurine","style":"smooth toy"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')

# 2. poll until done/error
while :; do
  S=$(curl -s http://127.0.0.1:8000/figure/status/$JOB)
  echo "$S" | python3 -c 'import sys,json;r=json.load(sys.stdin);print(r["stage"],r["progress"])'
  echo "$S" | grep -q '"stage": "done"' && break
  echo "$S" | grep -q '"stage": "error"' && { echo "$S"; exit 1; }
  sleep 3
done

# 3. download the GLB (filename is <job_id>.glb)
curl -s -o figure.glb http://127.0.0.1:8000/figure/model/$JOB.glb
```

---

# Shared / utility endpoints

| Method + path | Purpose |
|---|---|
| `GET /health` | Liveness check. |
| `GET /image/{filename}` | Serve a generated PNG (GET + HEAD). Filename is `[a-f0-9]{32}.png`. Resolves `output/images/` first, then `output/`. |
| `POST /upload-image` | Multipart (`file`) upload; re-encoded through Pillow to a `[a-f0-9]{32}.png` in `output/images/`; returns `{"filename"}`. Same filename form as `/generate`, so uploaded images are usable by `/figure/generate-from-image`. |
| `GET /settings/keys` | Masked status of the three managed keys (never returns raw values). |
| `POST /settings/keys` | Set/clear keys in the server store (`config.json`). Body: any of `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MESHY_API_KEY`. |

# Error model

Errors are FastAPI's standard shape:

```json
{ "detail": "human-readable message" }
```

Common codes across the API: **`400`** invalid/insufficient input, **`404`** unknown id/file, **`409`** action not valid in the job's current state (e.g. downloading before `done`), **`422`** request body fails schema validation (wrong types / missing required field), **`429`** too many concurrent jobs of that kind, **`500`** provider/internal failure, **`502`** Claude API error, **`503`** required provider key not configured on the server.

# Typical agent flows

- **Just an image:** `POST /generate` → `GET /image/{filename}`. Optionally `POST /gallery/image` to persist it.
- **A full storybook:** `POST /decompose` → for each page, `POST /generate` with the page's `image_prompt` → collect filenames. Optionally `POST /recheck-readings` to tidy readings, and `POST /gallery` to save.
- **A one-shot printable PDF from a prompt:** `POST /book-pdf` with `mode="prompt"` → poll `GET /book-pdf/status/{job_id}` → `GET /book-pdf/download/{job_id}`. (This alone can decompose, illustrate, and render — no need to drive `/decompose`+`/generate` yourself first.)
- **A printable PDF from an already-built book:** `POST /book-pdf` with `mode="existing"` + the `story` and `generated_images` you already have (e.g. from the storybook flow above) → poll → download. Reuses every image already on disk; the cheapest path through the endpoint.
- **A 3D figure from an image:** `POST /generate` (get a `[a-f0-9]{32}.png`) → `POST /figure/generate-from-image` with that filename → poll `GET /figure/status/{job_id}` → `GET /figure/model/{job_id}.glb`.
- **A 3D figure from text:** `POST /figure/generate` → poll → `GET /figure/model/{job_id}.glb`.
