# Book PDF Endpoint — Design Spec

**Feature:** `prompt → printable book PDF`, an async HTTP API job that runs the full storybook
pipeline (decompose → readings error-check → per-page image generation → PDF render → Chinese
practice-sheet append → merge) and hands back one downloadable PDF.

**Status:** Spec only. Implementation by `developer-agent`, after `architect-agent` picks the
rendering engine (Section 3 is deliberately left as an open question) and `cyber-architect` +
`financials-agent` review this doc (Section 7 explains why both are required).

**Mirrors:** the Figure Maker job pattern (`_figure_jobs` + lock, `_job_create/_job_update/_job_read`,
`POST → {job_id}` / `GET status/{job_id}` / stage strings) and the Practice Sheet job pattern
(`_practice_jobs`, `GET download/{job_id}` serving `application/pdf` via `FileResponse`). No new
async pattern is introduced — this spec composes existing ones.

---

## 1. API shape

### Routes (declared before the static mount, same as every other route group)

| Method + path | Purpose |
|---|---|
| `POST /book-pdf` | Start a job. Returns `{"job_id": "<32-hex>"}`. |
| `GET /book-pdf/status/{job_id}` | Poll the job record. |
| `GET /book-pdf/download/{job_id}` | Download the finished PDF (`409` if not done). |

### Request body — `BookPDFRequest`

Two modes, selected by `mode`. This directly answers requirement 4 (reuse already-generated
images): `mode="existing"` is the cost-saving path, `mode="prompt"` is the full from-scratch
pipeline described in the task.

| Field | Type | Default | Applies to | Notes |
|---|---|---|---|---|
| `mode` | `"prompt"` \| `"existing"` | `"prompt"` | both | Selects the pipeline entry point. |
| `concept` | string | `""` | `prompt` | Same semantics as `DecomposeRequest.concept`. |
| `character` | string | `""` | `prompt` | Same semantics as `DecomposeRequest.character`. |
| `style_suffix` | string | `""` | `prompt` | Same semantics as `DecomposeRequest.style_suffix`; safety suffix appended server-side via the existing `_safe_style`. |
| `language` | string | `"zh"` | both | `zh` \| `ja` \| `ko`. For `existing`, must match `story.language` if `story` carries one (400 on mismatch — don't silently prefer one over the other). |
| `page_count` | int | `11` | `prompt` | Clamped to `{11, 15, 19}`, identical to `/decompose`'s existing behavior — no new page-count policy introduced. Ignored for `existing` (derived from `len(story.pages)`). |
| `story` | `DecomposeResponse`-shaped object | `null` | `existing` | **Required** when `mode="existing"`. Same JSON shape `/decompose` already returns — a caller with a finished Book Builder project can pass its `project.story` object verbatim. `400` if absent or malformed. |
| `generated_images` | `dict[str, str]` (page number as string key → `[a-f0-9]{32}.png` filename) | `{}` | `existing` (and, for symmetry, honored but normally empty for `prompt`) | Filenames already in `OUTPUT_DIR`. Pages present here with a file that actually exists on disk are **skipped** in the illustrating stage; everything else is generated. Partial maps are explicitly supported (see Section 4). |
| `recheck_readings` | bool \| null | `null` | both | `null` resolves per-mode (see Section 4 decision below): **`true`** for `mode="prompt"` (non-overridable — the task marks this REQUIRED), **`false`** for `mode="existing"` (assumed already correct/checked in the UI). Caller may explicitly pass `true`/`false` to override the `existing`-mode default; `prompt` mode ignores an explicit `false` and always runs the check. |
| `include_practice_sheet` | bool | `true` | both, zh-only | Chinese-only regardless of value — silently has no effect for `ja`/`ko` (mirrors `/practice-sheet/local`'s existing zh-only gate rather than 400ing, since it's a passive default here, not a user-initiated action). |
| `gemini_model` | string | `"imagen-4.0-fast-generate-001"` | both (only matters when pages need generating) | Same field/default as `GenerateRequest` — cheapest tier by default, consistent with the recent "default to Imagen 4 Fast" change. |
| `gemini_aspect_ratio`, `width`, `height` | — | same as `GenerateRequest` | both | Pass through unchanged; `storybook_print.js`'s `.page-img { object-fit: contain }` tolerates any aspect ratio, so no new constraint is needed here. |
| `anthropic_key`, `gemini_key` | string \| null | `null` | both | Per-request overrides, resolved with the existing precedence (`settings_store.get_key` then env) exactly like every other endpoint. |

### Job record — `GET /book-pdf/status/{job_id}`

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

`job_id` is 32-hex (`uuid.uuid4().hex`), matching Figure Maker / Practice Sheet exactly.
`GET .../status/{job_id}` 400s on a malformed id, 404s on an unknown one — same guard as the
existing two status routes.

### Stage list + progress bands

```
decomposing → checking-readings → illustrating (i/N) → rendering → practice-sheet → merging → done
                                                                                              ↘ error (any stage)
```

| Stage | Progress band | Skip condition |
|---|---|---|
| `decomposing` | 0–8 | `mode="existing"` (jumps straight to `checking-readings`) |
| `checking-readings` | 8–18 | resolved `recheck_readings` is `false` |
| `illustrating` | 18–78 | zero pages need generation (band collapses instantly; `current_page`/`total_pages` reflect only the pages actually generated, not the full book, so a caller reusing 10/11 images sees `1/1`, not `11/11`) |
| `rendering` | 78–90 | never skipped |
| `practice-sheet` | 90–96 | `language != "zh"`, or `include_practice_sheet=false`, or zero Chinese characters found (see Section 6) |
| `merging` | 96–99 | no practice-sheet page was produced (the book PDF is already the final artifact — no-op, not literally skipped as a UI-visible stage since it's cheap either way) |
| `done` | 100 | — |

This is the same "banded progress, skip stages that don't apply" convention the Figure Maker
worker already uses (`_poll_until_done`'s `progress_start`/`progress_end` mapping) and the
Practice Sheet's simple `prompting → executing → done` shape — no new convention introduced.

### Design decision to confirm — `recheck_readings` default for `mode="existing"`

The task statement marks the readings error-check "REQUIRED. Applies to all languages" in the
context of the **full from-prompt pipeline**. For `mode="existing"`, the story didn't just come
out of `/decompose` — it's plausibly a book the user already finished editing (possibly having
already run Check Readings in the UI). Re-running it unconditionally would silently double a
Claude opus cost that requirement 4 is explicitly trying to avoid for images. I'm proposing
`recheck_readings` **defaults to `false` for `existing`, `true` (locked) for `prompt`**, with an
explicit override — flagging this rather than silently picking one, per the instruction to surface
inconsistencies. `product-manager`/`architect-agent` should confirm this reading of "REQUIRED" is
scoped to the `prompt` pipeline only.

---

## 2. Layout fidelity

**Target layout:** exactly what `storybook_print.js`'s `buildStorybookHTML()` already produces —
cover page (cover image + ruby title + English title) followed by one page-spread per page
(image left / ruby native text + English line right), because this is what the existing
"🖨 Print / Save as PDF" button already turns into a PDF today via the browser's print dialog.
The book-pdf endpoint should be indistinguishable in output from what a user gets clicking that
button today, just produced server-side without a browser in the loop.

**Page format:** landscape, matching the existing `@page { size: A4 landscape; margin: 0; }` rule
in `storybook_print.js`. Whichever rendering engine is picked (Section 3) must honor this — it's
not an open question, only the *mechanism* for hitting it is.

**Fonts — a real gap to flag:** `languages.py`'s `font_stack` per language (e.g.
`"'Noto Serif SC', 'SimSun', serif"`) currently resolves via the **browser's** font stack (system
fonts or whatever's cached from a prior page load) — nothing is bundled in this repo. A
server-side renderer has no browser to lean on:
- If the rendering engine is headless Chromium (option a below), Chromium itself ships no CJK
  glyphs — it renders whatever fonts the *host OS* has installed, same as any other web content.
  The dev/deploy environment must have `Noto Serif SC/JP/KR` (or equivalent) actually installed,
  or ruby/CJK text silently falls back to tofu/system-default.
- If hand-rolled with ReportLab/pymupdf (option c), the exact same problem exists but is more
  visible: `practice_sheet_local.py` already solves this narrowly for **zh only** via
  `_FONT_CANDIDATES` (a hardcoded list of macOS/Linux font paths checked at import time) — there
  is currently **no equivalent font-discovery list for `ja`/`ko`**, so this endpoint's `ja`/`ko`
  book pages have no proven font path today. This needs either bundling real font files (Noto
  Serif CJK OTFs run ~10–16 MB each — a real new repo/deploy weight decision) or extending the
  `practice_sheet_local.py`-style discovery table for `ja`/`ko`, neither of which currently exists.

This is a blocking dependency regardless of which rendering engine wins Section 3 — flagging it
explicitly rather than letting it surface as a silent tofu-glyph bug during implementation.

**Practice-sheet append + orientation mismatch:** the book pages are landscape A4
(~841.9 × 595.3 pt); `practice_sheet_local.render_pdf_bytes()` renders US-Letter **portrait**
(612 × 792 pt). PDF permits distinct page sizes/orientations per page within one document (each
page carries its own MediaBox) — `pymupdf` (already installed, `fitz.open().insert_pdf(...)`)
concatenates the two documents without forcing a resize, so this is mechanically trivial. The
**visible result** is a final page that's a different shape/orientation than the rest of the
book — most PDF viewers/printers handle this gracefully (auto-fit/auto-rotate on print), and the
task explicitly says this is acceptable. Recommend **not** rescaling the practice sheet to
landscape A4 to force uniformity — that would require re-tuning `practice_sheet_local.py`'s
tianzige box math (built around Letter-portrait proportions) for no functional gain; call this
out to product-manager as the accepted tradeoff rather than a bug.

---

## 3. Rendering-engine decision — OPEN QUESTION for architect-agent

Not picked here. Three options, laid out for architectural evaluation:

### (a) Server-side HTML + headless Chromium (Playwright `page.pdf()`)
- **Fidelity:** highest — literally reuse (a server-portable copy of) `buildStorybookHTML()`'s
  HTML/CSS as-is, including the `<ruby><rt>` markup, which Chromium already renders correctly
  today (that's what the existing Print button proves). Zero new layout logic to write or keep in
  sync with `storybook_print.js`.
- **Weight:** heaviest — a Chromium binary (~300 MB), plus `playwright install`. New process-spawn
  surface on a single-process app that currently has none.
- **Effort:** low (mostly plumbing: serialize the same HTML server-side instead of client-side,
  call `page.pdf({format: ..., landscape: true})`).
- **Font caveat:** applies (Section 2) — Chromium needs host CJK fonts either way.

### (b) WeasyPrint (HTML/CSS → PDF)
- **Fidelity:** medium, with a **likely-disqualifying gap**: WeasyPrint does not support the CSS
  ruby layout model / HTML `<ruby>`/`<rt>` elements the way a browser does. Since ruby-above-hanzi
  is the core pedagogical feature of every page, this would require re-deriving the ruby rendering
  by hand (e.g. absolutely-positioned small `<rt>`-equivalent text), which erases most of "reuse
  the existing CSS" as a benefit and re-introduces hand-rolled layout risk closer to option (c).
- **Weight:** lighter than a full browser (pure Python + Cairo/Pango), no Chromium process.
- **Effort:** medium-high once the ruby workaround is factored in.
- **Recommendation:** deprioritize unless architect-agent finds a workaround for ruby that isn't
  effectively option (c) in disguise.

### (c) Direct construction with ReportLab / pymupdf
- **Fidelity:** lowest by default — hand-implements cover layout, spread grid, ruby positioning,
  line-wrapping, and per-language font metrics from scratch; no shared source of truth with
  `storybook_print.js`, so any future layout change there must be manually ported here too (a
  standing double-maintenance cost the other two options avoid).
- **Weight:** lightest — no browser, and `reportlab`/`pymupdf` are already project dependencies
  (used by `practice_sheet.py`'s sandbox pattern and installed for `pymupdf`/PDF merging
  respectively).
- **Effort:** highest of the three — it's a from-scratch renderer.
- **Fits house style:** the practice sheet already does exactly this (hand-drawn canvas via
  ReportLab), so there's local precedent and pattern reuse for the *technique*, just not for this
  much layout surface.

### Recommended evaluation order (not a pick)
Evaluate **(a) first** — it is the only option with essentially zero new layout risk (it reuses
what already ships and is visually verified today), and the font/dependency-weight concerns are
knowable/boundable up front. Fall back to **(c)** only if the Chromium dependency proves
unacceptable for the deployment target (this is a single-process, currently-loopback-only app per
`CLAUDE.md` — worth checking whether a ~300 MB binary is actually a problem before ruling out (a)
on weight alone). **(b)** should likely be rejected outright unless the ruby gap has a real fix.

Whichever is picked, the **practice-sheet merge step stays pymupdf** regardless (Section 2) — that
part of the pipeline is not in question.

---

## 4. Reuse of already-generated images

Formalized via `mode` + `generated_images` (Section 1). Key behaviors:

- **Partial reuse is supported**, not just all-or-nothing: `generated_images` may cover any subset
  of `story.pages`. The illustrating stage only calls `/generate`-equivalent logic for pages
  *not* present in the map **or** whose file doesn't exist on disk at job-start time (self-healing
  against a stale/deleted filename rather than hard-failing the whole job — flagging this as a
  recommendation, not a hard requirement; architect-agent may prefer strict `404` validation
  instead if silent self-healing feels surprising).
- **Filename validation:** any filename supplied must match the existing `[a-f0-9]{32}\.png`
  pattern (mirrors `figure_generate_from_image`'s guard) — `400` on a malformed filename, since
  that's a caller bug, not a "file went missing" situation.
- **Cost impact:** a fully-reused `mode="existing"` job with `recheck_readings=false` and
  `include_practice_sheet` resolving to "nothing to add" (e.g. `ja`/`ko`) needs **zero** paid API
  calls — pure local rendering + merge. This is the cheapest possible path through this endpoint
  and should be highlighted to `financials-agent` as the expected steady-state cost for the
  Book Builder UI entry point (Section 5), as distinct from the `mode="prompt"` worst case
  (Section 7).

---

## 5. UX entry point

**Recommend:** a new Export-section button in `book_builder.html`'s `#step4`, alongside the
existing `#exportBtn` / `#printBtn` / `#galleryBtn` / `#practiceSheetBtn` / `#practiceLocalBtn`
row — same `.generate-btn` styling, same spinner + polling pattern already implemented for
`practiceSheetBtn` (POST → `job_id` → poll `status` every ~2 s → navigate to `download` on done).

```html
<button id="bookPdfBtn" class="generate-btn" style="max-width:240px;background:rgba(255,255,255,.10)">
  <span id="bookPdfLabel">📕 Download Book PDF</span>
  <div class="spinner hidden" id="bookPdfSpinner"></div>
</button>
```

**Placement rationale:** `#step4` already has `storyData` (a `DecomposeResponse`-shaped object)
and `generatedImages` (page number → filename map) sitting in memory — these map **directly**
onto `mode="existing"` + `story` + `generated_images` with no transformation. This is why the
button belongs in Step 4 specifically (gated the same way `#printBtn`/`#exportBtn` already are —
"All images generated" per the existing `section-sub` copy), not earlier: it's free wiring of
state that already exists, and by definition every page already has an image at that point, so
the illustrating stage is a no-op and the button's real-world cost is at most one recheck-readings
call (Section 4's "recommend default `false` for existing" makes even that opt-in) + rendering +
merge — i.e. this UI entry point is the **cheap path**, not the expensive `mode="prompt"` one.

**Keep it minimal:** this is the only new UI surface recommended. No standalone "prompt → PDF in
one click" page is proposed — the task frames this primarily as an API capability
("exposed as an async HTTP API job"); the Book Builder button is a low-cost, high-fit add-on, not
a new workflow. If product-manager wants to defer even this, the API ships unchanged.

---

## 6. Error / empty / timeout states

| Condition | Behavior |
|---|---|
| No Anthropic key resolvable, but one is needed (any `prompt`-mode job, or `recheck_readings=true`) | `503` at job-start (mirrors `/decompose`, `/figure/generate`) — fail fast, don't spawn the worker thread. |
| No Gemini key resolvable, but at least one page needs generating | `503` at job-start, same fail-fast principle. **Not** required at all when every page is reused and no recheck is requested (Section 4) — don't demand a key the job won't use. |
| `mode="prompt"` with neither `concept` nor `character` | `400` (mirrors `/decompose` exactly). |
| `mode="existing"` with `story` missing/malformed, or `language` mismatch between request and `story.language` | `400`. |
| A page image generation call fails mid-`illustrating` | **Recommend: retry once, then fail the whole job** (`stage="error"`, `error` names the page: `"Image generation failed for page 7: <upstream detail>"`). Rationale to flag for product sign-off: a "printable book PDF" that silently ships a placeholder page (the interactive HTML export's `.page-img-placeholder` "No image" box is an acceptable *editing-time* fallback, but this endpoint's entire contract is "hand back a finished, printable artifact" — a caller polling to `done` shouldn't have to re-open the PDF to discover a blank page). The one retry absorbs a transient Gemini hiccup without doubling cost on every failure. |
| Practice sheet step: zh book, but `practice_sheet_local.top_characters()` returns zero characters | **Must not fail the whole job.** Catch this the same way `POST /practice-sheet/local` gates it today (`if not chars: raise HTTPException(400, ...)`), but at the pipeline level: check `top_characters()`'s return **before** calling `render_pdf_bytes`, and if empty, skip straight to `merging` with `practice_sheet_included=false` in the job record — the book PDF alone is still a complete, correct deliverable. |
| Any stage exceeds its timeout | Mirror the Figure Maker convention (`_MAX_POLL_PER_STAGE * _POLL_INTERVAL`-style caps) — per-stage wall-clock ceilings, e.g. `decomposing`/`checking-readings` ≤ 180 s (matches the `timeout=180` already used on those Claude calls), `illustrating` ≤ 60 s per page, `rendering` ≤ 60 s, `practice-sheet` ≤ 15 s (it's synchronous local ReportLab — should be near-instant), `merging` ≤ 10 s. Additionally cap the **whole job** at a wall-clock ceiling (recommend ~20 min, generous even at `page_count=19`) so a stuck job can't occupy a slot indefinitely — this directly feeds the existing **S3 unbounded-job-store** backlog item (`design-specs/security-architecture-backlog.md`): `_book_pdf_jobs` inherits the exact same never-evicts, uncapped-daemon-thread shape as `_figure_jobs`/`_practice_jobs`, and should be swept up in that backlog item rather than solved bespoke here. |
| Unknown/malformed `job_id` on status/download | `400` malformed, `404` unknown — identical to the two existing job routes. |
| Download requested before `stage == "done"` | `409`, same as `/practice-sheet/download/{job_id}`. |

---

## 7. Cost visibility

**This is the single most expensive unauthenticated endpoint in the app**, and it collapses a
normally multi-step, human-paced UI wizard (decompose → review → generate images one by one →
export) into **one POST with no intermediate confirmation gate**. Per-PDF cost driver, worst case
(`mode="prompt"`, nothing reused):

```
cost_per_pdf ≈ 2 × (claude-opus-4-8 call: decompose + recheck-readings)
             + N × (gemini image call), N ∈ {11, 15, 19}
```

Both terms already exist elsewhere in the app individually (`/decompose` is one opus call,
`/recheck-readings` is a second, `/generate` is one paid image) — this endpoint is new *only* in
that it chains all of them into a single unattended job with no per-step human checkpoint, at up
to `page_count=19`. The cheapest steady state (`mode="existing"`, full reuse, `recheck_readings`
resolved to `false`) is effectively free (local rendering only, Section 4) — the two ends of the
cost range are wide, and the request body alone doesn't make which end a given call lands on
obvious at a glance, which is itself worth `financials-agent` calling out in the request-shape
review.

Exact per-call dollar figures are intentionally **not** guessed here — per `CLAUDE.md`'s agent
workflow, `financials-agent` fetches current provider pricing rather than working from memory, and
should size this against the existing `imagen_model` price table already surfaced in
`GET /gemini/models` plus current Claude opus token pricing. What this design spec asserts is the
**shape** of the cost (formula above) and the **structural** risk (one call, no confirmation gate,
already-clamped but still up to 19 images + 2 opus calls) — worth a hard look from both
`cyber-architect` (this is exactly the kind of "new network/API surface" + "cost-bearing endpoint"
combination S1 in the security backlog already names as the natural auth-phase trigger) and
`financials-agent` (unit economics + whether a lighter interim guardrail, e.g. a max-concurrent-jobs
cap, is warranted before this ships even pre-auth). Recommending — not deciding — that both reviews
happen before implementation, per the existing agent workflow in `CLAUDE.md`.

---

## Summary of new server-side pieces (for architect-agent's reference — not prescriptive code)

- `config.py`: a `BOOK_PDF_DIR` (e.g. `./output/book_pdfs`), mirroring `PRACTICE_DIR`.
- `main.py`: `_book_pdf_jobs` dict + lock + `_book_pdf_job_create/update/read`, a
  `BookPDFRequest` pydantic model, three routes (`POST /book-pdf`, `GET .../status/{job_id}`,
  `GET .../download/{job_id}`), and a daemon worker thread mirroring `_run_figure_job`'s
  try/except-to-`stage="error"` shape.
- A new module (name TBD by architect-agent, e.g. `book_pdf.py`) housing whichever rendering
  approach is chosen (Section 3) plus the pymupdf merge step — kept out of `main.py` the same way
  `practice_sheet.py`/`practice_sheet_local.py` are.
- Reuses without modification: `_decompose_tool`, `languages.py`, `gemini_generator.generate` /
  `save_image`, `practice_sheet_local.top_characters` / `render_pdf_bytes`, `_safe_style`,
  `settings_store.get_key`.
