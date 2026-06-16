# MKS Mobile — Design Spec

**Related:** `design-specs/home-tab.md` — the simple web landing page (`home.html`) that this spec does NOT supersede. `mks_mobile.html` is a distinct, additional page (the mobile app body) that reuses the same Home hero pattern. `home.html` remains as the web landing; `mks_mobile.html` is a separate experience.
**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`

**Core reframe:** `mks_mobile.html` is a self-contained, touch-friendly launcher for the Monkey King Studios (MKS) mobile app. It greets the user, accepts the primary prompt, and runs all three generation tasks inline on the page without navigation. It is served by the existing FastAPI static mount at `/mks_mobile.html` — no backend route change is required.

> **Mobile shell note:** A Capacitor wrapper was previously removed from the repository (see git history). This spec does not assume any native shell exists. The page is designed as a standalone PWA-style experience served by FastAPI at the same origin. Capacitor/React Native wrapping is a follow-up, explicitly out of scope here.

---

## Overview

A single-column, touch-friendly page that contains:

1. A hero section: the bouncing 🤖 mascot, the headline "What will you build today?", and one shared `character` prompt textarea.
2. Three action buttons: **Create Image**, **Build Figure**, **Book Builder**.
3. Three result regions that appear inline below the buttons as each task produces output.

Visual result: dark `var(--paper)` (#0a0b1a) background. The robot and headline anchor the top third. Below them, three pill-style buttons sit in a column (one per task). As each task runs, its dedicated result panel expands below the buttons — the three panels stack vertically and each is independently collapsible. On small phones the panels fill the full viewport width. On wider screens they cap at `560px` centered (matching the hero width).

The overall feel is calm and kid-appropriate, matching the existing dark-space aesthetic. The density stays lower than the full-page workflow tools — this is a launcher, not a full editing environment.

---

## 1. Page Layout

### Document structure

```html
<html lang="en">
  <head>…</head>                      <!-- see Section 9 -->
  <body>
    <a href="#mksMain" class="skip-link">Skip to main content</a>
    <header>…</header>               <!-- see Section 10 -->

    <main class="mks-main" id="mksMain">

      <!-- Hero -->
      <div class="mks-hero">
        <div class="home-robot-container" aria-hidden="true">
          <span class="home-robot">🤖</span>
        </div>
        <h1 class="home-headline">What will you build today?</h1>
        <div class="mks-input-wrap">
          <label for="mksPromptInput" class="home-input-label">
            Character Description
          </label>
          <textarea
            id="mksPromptInput"
            class="mks-prompt-input"
            rows="3"
            placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
            aria-describedby="mksPromptHint"
          ></textarea>
          <p class="hint" id="mksPromptHint">
            Describe your hero — this travels with you to every tool.
          </p>
        </div>
      </div>

      <!-- Action buttons -->
      <div class="mks-action-group" role="group" aria-label="Create with your character">
        <button class="mks-action-btn mks-action-primary" id="mksCreateImageBtn"
                aria-controls="mksImageResult">
          <span class="mks-action-label" id="mksCreateImageLabel">Create Image</span>
          <span class="spinner hidden" id="mksCreateImageSpinner" aria-hidden="true"></span>
        </button>
        <button class="mks-action-btn" id="mksBuildFigureBtn"
                aria-controls="mksFigureResult">
          <span class="mks-action-label" id="mksBuildFigureLabel">Build Figure</span>
          <span class="spinner hidden" id="mksBuildFigureSpinner" aria-hidden="true"></span>
        </button>
        <button class="mks-action-btn" id="mksBookBuilderBtn"
                aria-controls="mksBookResult">
          <span class="mks-action-label" id="mksBookBuilderLabel">Book Builder</span>
          <span class="spinner hidden" id="mksBookBuilderSpinner" aria-hidden="true"></span>
        </button>
      </div>

      <!-- Error message (shared, above result regions) -->
      <p class="mks-error hidden" id="mksErrorMsg" role="alert" aria-live="assertive"></p>

      <!-- Result regions (each collapsed by default; expand on first task run) -->
      <section class="mks-result-region hidden" id="mksImageResult"
               aria-label="Generated image" aria-live="polite">
        <!-- see Section 4 -->
      </section>

      <section class="mks-result-region hidden" id="mksFigureResult"
               aria-label="3D figure" aria-live="polite">
        <!-- see Section 5 -->
      </section>

      <section class="mks-result-region hidden" id="mksBookResult"
               aria-label="Storybook pages" aria-live="polite">
        <!-- see Section 6 -->
      </section>

    </main>

    <!-- Load order: see Section 9 for the authoritative end-of-body load order.
         The importmap lives in <head> (see Section 10); shared_inputs.js (non-module)
         must appear before the ES module so window.SharedInputs is defined. -->
    <script src="shared_inputs.js"></script>
    <script type="module" src="mks_mobile.js"></script>
  </body>
</html>
```

### Vertical rhythm

```
mks-main
  flex: 1
  display: flex
  flex-direction: column
  align-items: center
  gap: 1.5rem
  padding: 2rem 1rem 4rem

mks-hero
  display: flex
  flex-direction: column
  align-items: center
  gap: 1.5rem
  max-width: 560px
  width: 100%

mks-action-group
  max-width: 560px
  width: 100%
  display: flex
  flex-direction: column
  gap: .75rem

mks-result-region
  max-width: 560px
  width: 100%
```

All four major blocks (hero, action-group, error, result regions) share the same `max-width: 560px` centering. This creates a single visual column on all screen sizes.

---

## 2. The Bouncing Robot

Carry over the robot animation from `home-tab.md` verbatim:

- Container: `home-robot-container`, `6rem × 6rem`, `aria-hidden="true"`.
- Emoji: `home-robot`, `font-size: 4.5rem`, `animation: homeBounce 1.8s ease-in-out infinite`, `will-change: transform`.
- Keyframes (`@keyframes homeBounce`): 0%/100% at `translateY(0)`, plateau at 45%–55% at `translateY(-18px)`.
- `@media (prefers-reduced-motion: reduce)` disables the bounce entirely (no fallback animation).
- On mobile at `max-width: 700px`, reduce to `3.5rem`.

The robot container is `aria-hidden="true"` — purely decorative.

---

## 3. Headline and Prompt Input

### Headline

Identical to `home-tab.md` Section 3:
- `class="home-headline"`, `font-size: 1.75rem`, `font-weight: 900`, `color: var(--ink)`.
- Scales to `1.35rem` at `max-width: 700px`.

### SharedInputs field id

The textarea `id` is **`mksPromptInput`** (not `homeDescInput` from the earlier home-tab spec). This is the canonical id for this page's `bindFields` call. The rest of the input styling is identical to `home-tab.md`:

- `class="mks-prompt-input"` inherits the `style.css` textarea base rules.
- Add one page-specific override: `font-size: 1rem; min-height: 4.5rem;`.
- Placeholder: `"A brave young monkey king with golden fur, red cape, and a mischievous grin…"`.
- `aria-describedby="mksPromptHint"`.

The hint paragraph uses the existing `.hint` class.

### What this field feeds into each task

- **Create Image**: used as the image `prompt` field (combined with `story` from the shared store, matching the CG combine logic: `story ? \`${character}, in a scene: ${story}\` : character`).
- **Build Figure**: sent as `prompt` to `POST /figure/generate`.
- **Book Builder**: used as the `concept` field in `POST /decompose` when no dedicated concept field exists (see Section 6 for the empty-story case).

---

## 4. The Three Action Buttons

### Visual spec

```css
.mks-action-btn {
  width: 100%;
  min-height: 52px;          /* exceeds 44px WCAG touch target */
  padding: .85rem 1.25rem;
  border-radius: var(--radius);   /* 18px */
  font-size: 1rem;
  font-family: inherit;
  font-weight: 700;
  letter-spacing: .02em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .6rem;
  transition: background .15s, opacity .15s;
  border: none;
}

/* Primary: Create Image — mustard, matching .generate-btn */
.mks-action-primary {
  background: var(--mustard);
  color: #0a0b1a;
}
.mks-action-primary:hover:not(:disabled) { background: var(--mustard-dark); }

/* Secondary: Build Figure + Book Builder — ghost style */
.mks-action-btn:not(.mks-action-primary) {
  background: rgba(255,255,255,.10);
  color: var(--ink);
  border: 1px solid rgba(255,255,255,.10);
}
.mks-action-btn:not(.mks-action-primary):hover:not(:disabled) {
  background: rgba(255,255,255,.18);
}

/* Disabled / loading state */
.mks-action-btn:disabled {
  opacity: .40;
  cursor: not-allowed;
}
```

### Hierarchy rationale

"Create Image" is primary (orange) because it is the fastest task (seconds, no polling) and the most immediately rewarding result for a child. "Build Figure" and "Book Builder" are secondary (ghost) because they involve longer waits and more complex inline results. All three are full-width — no cramped side-by-side layout on small phones.

### Loading states

When a task is running, its button is `disabled` (opacity 0.4) and the button label is hidden while a spinner is shown. Buttons for the OTHER two tasks remain enabled — all three tasks can coexist as active (their result regions stack). Concurrent runs are explicitly allowed, though the UX hint text recommends finishing one at a time.

Spinner markup reuses the existing `.spinner` class from `style.css` (the same spinner used across all pages).

### Button states table

| State | Create Image | Build Figure | Book Builder |
|---|---|---|---|
| Idle (no task running) | Enabled, orange | Enabled, ghost | Enabled, ghost |
| This task running | Disabled + spinner | same | same |
| Other task running | Unaffected | Unaffected | Unaffected |
| Prompt empty on click | Flash terracotta border on `#mksPromptInput`, no task starts | same | same — EXCEPT Book Builder starts with empty prompt too (see Section 6) |

---

## 5. Result Region Layout and Stacking Strategy

### Recommendation: concurrent stacking with per-region collapse

Each result region is an independent `<section>` that starts `hidden` and becomes visible when its task is triggered. Results stack vertically in the order: Image first, Figure second, Book third (matching the button order). All three can be simultaneously visible.

This is preferable to a "one active at a time" accordion for two reasons:
1. Figure Builder jobs can take several minutes — it would be frustrating to lose the progress indicator because the user tapped "Create Image" to fill the time.
2. A child may want to see the image alongside the storybook when sharing.

Each result region has a **dismiss button** in its top-right corner (a small `×` icon button, `aria-label="Close [result name]"`, `min-height: 36px`, `min-width: 36px`) so the user can collapse a result they are done with. Dismissing a result that still has an in-flight Figure job does NOT cancel the job — the job continues in `localStorage` and the result region can be re-opened by running the task again (where `resumeJobIfAny()` will re-attach).

### Shared result region structure

```html
<section class="mks-result-region hidden" id="mksImageResult" aria-label="…" aria-live="polite">
  <div class="mks-result-header">
    <h2 class="mks-result-title">Your Image</h2>
    <button class="mks-result-close" aria-label="Close image result">×</button>
  </div>
  <div class="mks-result-body">
    <!-- task-specific content -->
  </div>
</section>
```

```css
.mks-result-region {
  width: 100%;
  max-width: 560px;
  background: var(--ctrl-bg);     /* #0f1129 */
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.mks-result-region.hidden { display: none; }

.mks-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .75rem 1rem .5rem;
  border-bottom: 1px solid var(--border);
}
.mks-result-title {
  font-size: .9rem;
  font-weight: 700;
  color: var(--ink-soft);
  text-transform: uppercase;
  letter-spacing: .05em;
}
.mks-result-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 1.2rem;
  cursor: pointer;
  min-height: 36px;
  min-width: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: background .15s, color .15s;
}
.mks-result-close:hover { background: rgba(255,255,255,.10); color: var(--ink); }

.mks-result-body {
  padding: 1rem;
}
```

---

## 6. Inline Create Image

### Behavior

Clicking "Create Image" runs the same flow as Character Generator's `cgGenerateBtn` click handler. The mobile page calls `POST /generate` (non-streaming, for simplicity — SSE adds complexity with no meaningful UX benefit on a one-image result). If SSE is preferred for parity, use `POST /generate/stream` as a fallback.

### Request payload

```js
// Inside mks_mobile.js
const inputs = SharedInputs.read();
const character = inputs.character.trim();
const story     = inputs.story.trim();
const draft     = JSON.parse(localStorage.getItem('monkeyking_cg_draft') || '{}');
const model     = draft.model || 'imagen-4.0-generate-001';
const ar        = draft.ar    || '3:4';

const prompt = story ? `${character}, in a scene: ${story}` : character;

const payload = {
  prompt,
  style_prompt:        inputs.style.trim(),
  provider:            'gemini',
  gemini_model:        model,
  gemini_aspect_ratio: ar,
};
```

Model and aspect ratio are read from `localStorage['monkeyking_cg_draft']` (set by Settings), exactly as `character_generator.js` does. No new config mechanism.

### Validation

If `character` is empty after trim, flash the terracotta border on `#mksPromptInput` and do not send the request. This is the only field required for image generation.

### Result region contents

```html
<section class="mks-result-region hidden" id="mksImageResult"
         aria-label="Generated image" aria-live="polite">
  <div class="mks-result-header">
    <h2 class="mks-result-title">Your Image</h2>
    <button class="mks-result-close" id="mksImageClose" aria-label="Close image result">×</button>
  </div>
  <div class="mks-result-body">
    <!-- Loading state -->
    <div class="mks-img-loading hidden" id="mksImgLoading" aria-label="Generating image…">
      <div class="mks-img-skeleton"></div>
      <p class="hint">Painting your character…</p>
    </div>
    <!-- Image -->
    <img class="mks-portrait hidden" id="mksPortraitImg"
         src="" alt="" style="width:100%;border-radius:12px;">
    <!-- Actions below image -->
    <div class="mks-img-actions hidden" id="mksImgActions">
      <a id="mksImgDownload" class="settings-btn" download>Download</a>
    </div>
  </div>
</section>
```

**States:**

| State | Visible elements |
|---|---|
| Before first run | Region hidden entirely |
| Loading | Region visible; `mksImgLoading` visible; `mksPortraitImg` hidden |
| Success | Region visible; `mksPortraitImg` visible; `mksImgActions` visible |
| Error | Region visible; `.mks-error` (shared) updated with message |

**Skeleton loader:** A `mks-img-skeleton` `<div>` with `aspect-ratio: 3/4`, `background: rgba(255,255,255,.07)`, `border-radius: 12px`, animated with a horizontal shimmer using `@keyframes mksShimmer`. Reduced-motion: replace shimmer with a static muted-bg rectangle (no animation).

**Gallery auto-save:** After a successful generation, fire-and-forget `POST /gallery/image` with the same payload shape as Character Generator — `{ filename, prompt: character, story, style_prompt: style, model }`. Errors are silently ignored.

---

## 7. Inline Build Figure

### Behavior

Clicking "Build Figure" sends `POST /figure/generate` and then enters the poll loop (`GET /figure/status/{job_id}` every 2500 ms). The in-flight job is persisted to `localStorage['monkeyking_fm_job']` using the same `{ job_id, started_at }` shape as `figure_maker.js`, so `resumeJobIfAny()` logic can be ported directly.

### Request payload

```js
const inputs = SharedInputs.read();
// prompt is required — character field must not be empty
const payload = {
  prompt: inputs.character.trim(),
  style:  inputs.style.trim(),
  story:  inputs.story.trim(),
};
```

The server validates `prompt` is non-empty and returns 400 if not. The client guard: if `inputs.character` is empty, flash the input border and bail — same as Create Image.

### Stage progression

The five stages from `figure_maker.js` apply verbatim: `prompting → preview → refine → downloading → analyzing → done` (with `error` on failure). Use the same `STAGE_LABELS` and `BOLT_MESSAGES` copy (or a condensed subset appropriate to this inline context without the mascot).

### Result region contents

```html
<section class="mks-result-region hidden" id="mksFigureResult"
         aria-label="3D figure" aria-live="polite">
  <div class="mks-result-header">
    <h2 class="mks-result-title">Your Figure</h2>
    <button class="mks-result-close" id="mksFigureClose" aria-label="Close figure result">×</button>
  </div>
  <div class="mks-result-body">

    <!-- Progress state -->
    <div class="mks-fig-progress hidden" id="mksFigProgress">
      <p class="mks-fig-stage" id="mksFigStage" aria-live="polite">Dreaming up your idea…</p>
      <div class="mks-fig-track"
           role="progressbar"
           aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"
           aria-labelledby="mksFigStage"
           id="mksFigBar">
        <div class="mks-fig-fill" id="mksFigFill"></div>
      </div>
      <span class="hint" id="mksFigPct" aria-live="off">0%</span>
    </div>

    <!-- Viewer container — three.js canvas appended here by mountViewer() -->
    <div class="mks-fig-viewer hidden" id="mksFigViewer"
         style="width:100%;height:clamp(280px,55vw,420px);border-radius:12px;overflow:hidden;"
         role="img"
         aria-label="3D model — drag to rotate, scroll to zoom">
    </div>

    <!-- Post-generation actions -->
    <div class="mks-fig-actions hidden" id="mksFigActions">
      <a id="mksFigDownloadGlb" class="settings-btn" download>Download GLB</a>
      <a id="mksFigDownloadStl" class="settings-btn hidden" download>Download STL</a>
    </div>

    <!-- Viewer error -->
    <p class="mks-error hidden" id="mksFigViewerError" role="alert"></p>
  </div>
</section>
```

**States:**

| State | Visible elements |
|---|---|
| Before first run | Region hidden |
| In-flight (any stage) | Region visible; `mksFigProgress` visible; viewer hidden |
| Done | Region visible; `mksFigProgress` hidden; `mksFigViewer` visible; `mksFigActions` visible |
| Error | Region visible; `mksFigProgress` hidden; `.mks-error` updated |
| Missing/stale job on resume | Region visible; soft notice in `mksFigStage`, "Check the Gallery" |

### three.js viewer — ES module and import map

The inline viewer uses the same three.js CDN import map and the same `mountViewer()` approach from `figure_maker.js`. The `<script type="importmap">` block must appear in `<head>` before any module script. `shared_inputs.js` is a plain (non-module) `<script>` loaded at end-of-body BEFORE the `<script type="module" src="mks_mobile.js">` tag. This is the exact pattern already established in `gallery.html` (where `storybook_print.js` is a non-module loaded before `<script type="module" src="gallery.js">`).

**Concrete head block additions:**

```html
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
  }
}
</script>
```

**End-of-body load order:**

```html
<script src="shared_inputs.js"></script>     <!-- non-module, sets window.SharedInputs -->
<script type="module" src="mks_mobile.js"></script>   <!-- ES module, imports THREE -->
```

`mks_mobile.js` uses `window.SharedInputs` (set by the non-module) after the DOM is ready — this is safe because module scripts are deferred by default and run after the DOM is parsed.

### STL export

After the GLB loads into the viewer, export STL client-side via `STLExporter` (same as `figure_maker.js`). The `mksFigDownloadStl` anchor gets a blob URL and is revealed. The blob URL is revoked on teardown (`URL.revokeObjectURL`).

### Job persistence

`mks_mobile.js` must implement the same `saveFmJob` / `readFmJob` / `clearFmJob` functions using `localStorage['monkeyking_fm_job']` with the same `{ job_id, started_at }` shape. `resumeJobIfAny()` runs on page init (same 35-min staleness cap). If a stale job is found on load, the Figure result region is opened automatically and the progress UI is shown.

**Single-flight guard:** The `_currentJobId` variable (same pattern as `figure_maker.js`) prevents a resumed loop and a new Generate click from racing. Setting `_currentJobId = null` before starting a new job supersedes any running poll.

---

## 8. Inline Book Builder

### Empty-story behavior — the key design decision

The decompose endpoint requires `concept: str` (mandatory, from `DecomposeRequest`). The Home/mobile page only exposes the `character` field in the visible UI. The `story` and `style` fields come from the shared store (they may be blank).

**Exact payload spec when Story field is blank:**

```js
const inputs = SharedInputs.read();
const character = inputs.character.trim();
const story     = inputs.story.trim();

// concept falls back to character text if story is empty.
// This is intentional: character IS the seed for a kid making a figure book.
const concept   = story || character || 'A fun adventure story';

const payload = {
  concept,
  character: character,     // sent separately so Claude can pin it to every page
  style_suffix: inputs.style.trim(),
  language: 'zh',           // default — architect to decide if a lang picker is in scope
};
```

If both `story` AND `character` are blank, `concept` falls back to the literal string `'A fun adventure story'` as a last resort (so the book always starts, never hangs). The fallback is visible in the UX: a hint below the button reads "No prompt? We'll make up an adventure!" when both fields are blank.

**Page range:** The backend defaults to `min_pages=10, max_pages=10`. The mobile launcher sends no page-range override — it accepts the default 10-page storybook.

**Language:** Default `zh` (Chinese). A language toggle within the Book result region is a v2 concern — the architect should flag if this is a blocking omission. For v1, the spec prescribes `zh` fixed.

### Request

```js
// POST /decompose
const res = await fetch(`${API}/decompose`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
```

This is synchronous HTTP (no streaming). The server response takes ~20 s. The Book button must show a spinner and "Writing…" label for the full duration. The hint text below the button updates to "Claude is writing your storybook… (about 20 seconds)".

### Result region contents

```html
<section class="mks-result-region hidden" id="mksBookResult"
         aria-label="Storybook pages" aria-live="polite">
  <div class="mks-result-header">
    <h2 class="mks-result-title" id="mksBookTitle">Your Story</h2>
    <button class="mks-result-close" id="mksBookClose" aria-label="Close storybook result">×</button>
  </div>
  <div class="mks-result-body">

    <!-- Loading state -->
    <div class="mks-book-loading hidden" id="mksBookLoading" aria-label="Writing storybook…">
      <p class="hint">Claude is writing your storybook… about 20 seconds.</p>
      <div class="mks-book-skeleton-row">
        <!-- 3 skeleton page-card placeholders -->
        <div class="mks-page-skeleton"></div>
        <div class="mks-page-skeleton"></div>
        <div class="mks-page-skeleton"></div>
      </div>
    </div>

    <!-- Decomposed pages — rendered after success -->
    <div class="mks-book-pages hidden" id="mksBookPages">
      <!-- mks_mobile.js dynamically inserts .mks-mini-card elements here -->
    </div>

    <!-- CTA: open in full Book Builder -->
    <div class="mks-book-actions hidden" id="mksBookActions">
      <a href="book_builder.html" class="mks-action-btn" id="mksOpenBookBuilder"
         style="text-decoration:none; display:flex; align-items:center; justify-content:center;">
        Open in Book Builder to add images
      </a>
      <p class="hint" style="text-align:center; margin-top:.5rem;">
        The full editor lets you generate illustrations and export your book.
      </p>
    </div>

  </div>
</section>
```

**Mini page card (`.mks-mini-card`):** A compact read-only view of each page — not the full `buildCard()` from `book_builder.js`. Shows: page number, native text (e.g. Chinese), romanization (pinyin), English translation. No image thumbnail (no images have been generated yet), no editing, no image_prompt visible. This is intentionally read-only — the edit/generate workflow is deferred to the Book Builder page.

```css
.mks-book-pages {
  display: flex;
  flex-direction: column;
  gap: .75rem;
  max-height: 480px;         /* prevent page list from dominating the screen */
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  scroll-snap-type: y proximity;
  padding-right: .25rem;     /* space for scrollbar */
}

.mks-mini-card {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: .75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: .35rem;
  scroll-snap-align: start;
}

.mks-mini-card-num {
  font-size: .7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);
}

.mks-mini-card-native {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.3;
}

.mks-mini-card-reading {
  font-size: .8rem;
  color: var(--muted);
}

.mks-mini-card-en {
  font-size: .85rem;
  color: var(--ink-soft);
  font-style: italic;
}
```

**"Open in Book Builder" link:** When clicked, the inline result IS the starting content — but carrying it to the full page requires state handoff. For v1, clicking this link navigates to `book_builder.html` WITHOUT attempting to pass the decomposed story (the user can re-run decompose there). A v2 enhancement could serialize the `DecomposeResponse` to `sessionStorage` so Book Builder can restore it on load. Flag this as a follow-up; scope it explicitly as out of spec for v1.

**States:**

| State | Visible elements |
|---|---|
| Before first run | Region hidden |
| Loading | Region visible; `mksBookLoading` visible; pages hidden |
| Success | Region visible; pages visible; `mksBookActions` visible |
| Error | Region visible; shared `#mksErrorMsg` updated |

---

## 9. SharedInputs Wiring

### The bindFields call

`mks_mobile.js` is an ES module. `window.SharedInputs` is set by `shared_inputs.js` (non-module, loaded first). The module accesses `window.SharedInputs` at init time — this is safe because modules are deferred.

```js
// mks_mobile.js (ES module)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';

const API = window.location.origin;

// SharedInputs is a global set by the non-module shared_inputs.js
// loaded before this module. window.SharedInputs is available at module
// execution time because modules are deferred and run after parsing.
const SharedInputs = window.SharedInputs;

function wireSharedInputListeners() {
  SharedInputs.bindFields(
    { character: 'mksPromptInput' },
    { debounce: 300 }
  );
}
```

Only `character` is mapped — `story` and `style` are read via `SharedInputs.read()` at task-launch time, not bound to visible fields on this page. Their stored values are never overwritten by this page.

### Cross-tab behavior

1. Typing in `#mksPromptInput` → after 300 ms → `localStorage['monkeyking_shared_inputs'].character` updated.
2. Any sibling tab that edits `character` → storage event → `#mksPromptInput` value updated silently.
3. `story` and `style` values in the store are preserved. This page never touches them via `bindFields`.

### Script load order (end-of-body)

```html
<script src="shared_inputs.js"></script>             <!-- non-module -->
<script type="module" src="mks_mobile.js"></script>  <!-- ES module, deferred automatically -->
```

Do NOT place either script in `<head>`. Do NOT add `defer` explicitly to the module script — it is implicit. `shared_inputs.js` must be the non-module script and must appear first so that `window.SharedInputs` is defined by the time the module's top-level code executes (modules run after parsing, after non-module scripts that appear earlier in body).

---

## 10. Full Head Block

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MKS · MonkeyKing Studios</title>
  <meta name="color-scheme" content="dark">
  <meta name="theme-color" content="#0a0b1a">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="home.css">       <!-- robot animation, headline — already defined -->
  <link rel="stylesheet" href="mks_mobile.css"> <!-- new: action group, result regions, mini cards -->
  <script type="importmap">
  {
    "imports": {
      "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
    }
  }
  </script>
</head>
```

**CSS layering:**
- `style.css`: tokens, base reset, header, textarea, `.generate-btn`, `.spinner`, `.hint`, `.settings-btn`.
- `home.css`: `.home-robot-container`, `.home-robot`, `@keyframes homeBounce`, `.home-headline`, `prefers-reduced-motion` override, responsive breakpoint for robot/headline size. **Reused unchanged from `home-tab.md`.**
- `mks_mobile.css` (new file): `.mks-main`, `.mks-hero`, `.mks-input-wrap`, `.mks-prompt-input`, `.mks-action-group`, `.mks-action-btn`, `.mks-action-primary`, `.mks-result-region`, `.mks-result-header`, `.mks-result-title`, `.mks-result-close`, `.mks-result-body`, `.mks-img-loading`, `.mks-img-skeleton`, `@keyframes mksShimmer`, `.mks-portrait`, `.mks-img-actions`, `.mks-fig-progress`, `.mks-fig-track`, `.mks-fig-fill`, `.mks-fig-viewer`, `.mks-fig-actions`, `.mks-book-loading`, `.mks-book-pages`, `.mks-mini-card`, `.mks-mini-card-*`, `.mks-book-actions`, `.mks-error`, responsive `@media` blocks.

`home.css` is shared between `home.html` (if that page still exists as a redirect or alias) and `mks_mobile.html`. No changes to `home.css` are required.

---

## 11. Header Block

Identical structure to all sibling pages. Nav active state: Home (or "MKS") if a Home nav link exists. Since this page replaces the home-tab spec, it should carry `class="nav-link active"` on the Home link:

```html
<nav class="header-nav" aria-label="Main navigation">
  <a href="home.html" class="nav-link active">🏠 Home</a>
  <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
  <a href="book_builder.html" class="nav-link">📖 Book Builder</a>
  <a href="figure_maker.html" class="nav-link">🧩 Figure Maker</a>
  <a href="gallery.html" class="nav-link">🖼 Gallery</a>
</nav>
```

Server status block is included (`.server-status`, `#statusDot`, `#statusLabel`). `mks_mobile.js` implements a simple `checkHealth()` that shows "Connected" / "Server offline" without the `loaded_model` suffix (same as the simplified version specified in `home-tab.md` Section 8).

### GET / route

In `main.py`, the `GET /` redirect should point to `home.html` (this page):

```python
@app.get("/")
def root():
    return RedirectResponse(url="/home.html")
```

This is the only backend change required.

---

## 12. Accessibility

### Skip link

`<a href="#mksMain" class="skip-link">Skip to main content</a>` — uses the `.skip-link` class from `style.css`. Target is `id="mksMain"` on `<main>`.

### Input labeling

`<label for="mksPromptInput">` is an explicit label. `aria-describedby="mksPromptHint"` links the hint. Matches the `control-group` pattern.

### Heading hierarchy

- `<h1>` "What will you build today?" — the page-level heading.
- `<h2>` inside each result region (`.mks-result-title`) — "Your Image", "Your Figure", "Your Story". These are sub-sections of the main content.

### aria-live regions

All three result sections carry `aria-live="polite"` so screen readers announce when new content appears:

- Image region: announces when the image result is ready.
- Figure region: `mksFigStage` (inside the region) carries `aria-live="polite"` for stage updates. The progress percentage element carries `aria-live="off"` to avoid noisy announcements every 2.5 s.
- Book region: announces when pages are rendered.

The shared error `#mksErrorMsg` carries `role="alert"` and `aria-live="assertive"` — errors interrupt immediately.

Progress bar in the Figure region uses `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-labelledby="mksFigStage"`.

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  .home-robot { animation: none; }
  .mks-img-skeleton { animation: none; background: rgba(255,255,255,.07); }
}
```

The robot bounce is disabled. The skeleton shimmer is replaced with a static muted rectangle. No other animations exist on this page.

### Color and contrast

All existing tokens apply. White (`var(--ink)`) on `var(--paper)` (#0a0b1a) exceeds WCAG AA. `.hint` text at `.72rem` / `rgba(255,255,255,.50)` is borderline AA — pre-existing system-wide behavior, not introduced here. The primary button (`var(--mustard)` / #ff6b35 on #0a0b1a) is ~3.5:1 contrast, qualifying for WCAG AA at bold text sizes (the button label is `1rem font-weight: 700`).

### Keyboard navigation order

1. Skip link
2. Gear icon (Settings)
3. Site title (non-interactive)
4. Nav links
5. `#mksPromptInput` textarea
6. "Create Image" button
7. "Build Figure" button
8. "Book Builder" button
9. (When visible) Close buttons and download links in each result region
10. (Figure viewer) The `<canvas>` carries `aria-hidden="true"` — orbit controls are mouse/touch; keyboard access to 3D is out of scope for this screen

---

## 13. Responsive Behavior

All layout adjustments live in `mks_mobile.css`:

```css
/* Large screens — unchanged from the centering spec */
.mks-hero,
.mks-action-group,
.mks-result-region { max-width: 560px; width: 100%; }

/* Small phone (< 400px) */
@media (max-width: 400px) {
  .mks-main { padding: 1.25rem .75rem 3rem; }
  .mks-action-btn { min-height: 48px; font-size: .9rem; }
}

/* Landscape phone (short viewport) */
@media (max-height: 500px) {
  .mks-hero { gap: .75rem; }
  .home-robot-container { width: 4rem; height: 4rem; }
  .home-robot { font-size: 3rem; }
  .home-headline { font-size: 1.15rem; }
}
```

The figure viewer height is `clamp(280px, 55vw, 420px)` — shorter than the full Figure Maker page's `clamp(460px, 60svh, 600px)` — because the mobile page has more competing content above and below.

The book pages list caps at `max-height: 480px` with `overflow-y: auto` and scroll-snap, allowing the user to scroll through pages without the list dominating the screen.

---

## 14. mks_mobile.js — Init Structure

```js
// mks_mobile.js (ES module)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';

const API = window.location.origin;
const SharedInputs = window.SharedInputs;

// ── State ────────────────────────────────────────────────────────────────────
let _figCurrentJobId  = null;
let _figCancelled     = false;
let _figGlbUrl        = null;
let _figStlObjectUrl  = null;
let fmRenderer = null, fmAnimId = null, fmControls = null, fmRo = null;

// ── DOM refs (abbreviated) ───────────────────────────────────────────────────
const mksPromptInput    = document.getElementById('mksPromptInput');
const mksCreateImageBtn = document.getElementById('mksCreateImageBtn');
const mksBuildFigureBtn = document.getElementById('mksBuildFigureBtn');
const mksBookBuilderBtn = document.getElementById('mksBookBuilderBtn');
// … etc.

// ── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() { /* simplified — see home-tab.md Section 8 */ }

// ── SharedInputs ─────────────────────────────────────────────────────────────
function wireSharedInputListeners() {
  SharedInputs.bindFields({ character: 'mksPromptInput' }, { debounce: 300 });
}

// ── Task handlers ─────────────────────────────────────────────────────────────
async function handleCreateImage() { /* see Section 6 */ }
async function handleBuildFigure() { /* see Section 7 */ }
async function handleBookBuilder() { /* see Section 8 */ }

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  wireSharedInputListeners();
  resumeJobIfAny();   // re-attach to in-flight figure job if any

  mksCreateImageBtn.addEventListener('click', handleCreateImage);
  mksBuildFigureBtn.addEventListener('click', handleBuildFigure);
  mksBookBuilderBtn.addEventListener('click', handleBookBuilder);

  // Close buttons
  document.getElementById('mksImageClose') .addEventListener('click', () => closeResult('mksImageResult'));
  document.getElementById('mksFigureClose').addEventListener('click', () => closeResult('mksFigureResult'));
  document.getElementById('mksBookClose')  .addEventListener('click', () => closeResult('mksBookResult'));
})();

setInterval(checkHealth, 30_000);
```

---

## 15. CSS File Summary

```
style.css      — no changes required (tokens, base, .generate-btn, .spinner, .hint, .settings-btn)
home.css       — no changes required (robot animation, headline, @keyframes homeBounce, breakpoints)
mks_mobile.css — NEW file. Owns:
  .mks-main, .mks-hero, .mks-input-wrap, .mks-prompt-input
  .mks-action-group, .mks-action-btn, .mks-action-primary
  .mks-error
  .mks-result-region, .mks-result-header, .mks-result-title, .mks-result-close, .mks-result-body
  .mks-img-loading, .mks-img-skeleton, @keyframes mksShimmer, .mks-portrait, .mks-img-actions
  .mks-fig-progress, .mks-fig-track, .mks-fig-fill, .mks-fig-stage, .mks-fig-viewer, .mks-fig-actions
  .mks-book-loading, .mks-book-skeleton-row, .mks-page-skeleton
  .mks-book-pages, .mks-mini-card, .mks-mini-card-num, .mks-mini-card-native,
  .mks-mini-card-reading, .mks-mini-card-en
  .mks-book-actions
  @media (max-width: 400px), @media (max-height: 500px)
  @media (prefers-reduced-motion: reduce) — disable mksShimmer
```

**Pre-existing token inconsistency to note (do not fix in this PR):** `--teal`, `--mustard`, and `--olive` all resolve to `#ff6b35` in `style.css`. Use `var(--mustard)` for the primary button (matching `.generate-btn` and `.nav-link.active`). Do not introduce `var(--teal)` in `mks_mobile.css`.

---

## 16. Acceptance Criteria

1. **Landing:** `GET /` loads `home.html` (this page). Page title is "MKS · MonkeyKing Studios".

2. **Create Image — success:** Typing a character description and clicking "Create Image" sends `POST /generate` with the correct payload. The image region opens, shows the skeleton loader, then replaces it with the generated image. The download link is populated.

3. **Create Image — empty prompt:** With `#mksPromptInput` empty, clicking "Create Image" flashes the terracotta border on the input; no request is sent.

4. **Create Image — gallery save:** After a successful generation, `POST /gallery/image` is fired (verify in Network tab). Errors are silently ignored; the page does not show a gallery-save error.

5. **Build Figure — success:** Typing a description and clicking "Build Figure" sends `POST /figure/generate`. The figure region opens and shows stage labels (prompting → preview → refine → downloading → analyzing → done). On done, the three.js viewer appears and the GLB is rendered. The STL download button appears after the GLB loads.

6. **Build Figure — job persistence:** After triggering a figure build, navigating away and back (or reloading) causes `resumeJobIfAny()` to re-open the figure region and re-attach the poll loop. The job continues to completion.

7. **Build Figure — concurrent with Image:** Both "Create Image" and "Build Figure" can be running simultaneously. Both result regions are visible simultaneously. Each button's loading state is independent.

8. **Book Builder — with prompt:** Typing a character description and clicking "Book Builder" sends `POST /decompose` with `concept = character`, `character = character`, `style_suffix`, `language: 'zh'`. The book region shows the loading state for ~20 s, then renders mini-cards for each page.

9. **Book Builder — empty prompt:** With `#mksPromptInput` empty, clicking "Book Builder" sends `POST /decompose` with `concept = 'A fun adventure story'`. The book still runs and returns pages. No validation error is shown for this button alone.

10. **SharedInputs — write:** Typing in `#mksPromptInput` updates `localStorage['monkeyking_shared_inputs'].character` after 300 ms. Verified by inspecting localStorage.

11. **SharedInputs — read on load:** With a stored `character` value, loading the page populates `#mksPromptInput` immediately.

12. **SharedInputs — cross-tab:** Editing `character` in Character Generator updates `#mksPromptInput` within 300 ms (storage event). Editing in this page updates CG's field.

13. **Reduced motion:** With `prefers-reduced-motion: reduce`, the robot is static and the skeleton shimmer is replaced with a static rectangle. Verified via DevTools emulation.

14. **Mobile layout:** At 375px viewport width, all three buttons are full-width, the input fills the column, and no horizontal overflow occurs. All three result regions stack vertically and are scrollable within the page.

15. **Accessibility:** `#mksPromptInput` has a `<label for>` and `aria-describedby`. The page has one `<h1>`. The skip link targets `#mksMain`. Progress bar has `role="progressbar"` and `aria-valuenow`. Stage label updates are announced via `aria-live="polite"`. Error messages are announced via `aria-live="assertive"`. Validated with axe or equivalent.

---

## 17. Design Decisions and Tradeoffs — For Architect Review

The following decisions involve tradeoffs that warrant scrutiny before implementation begins.

### A. Three simultaneous result regions on one screen

**Decision:** All three regions stack vertically and coexist. There is no forced single-active constraint.

**Rationale:** The Figure job can take 5–10 minutes. A hard "one active at a time" rule would prevent the child from generating an image while waiting. Stacking lets results accumulate naturally.

**Risk:** On a small phone, three open result regions (image + 3D viewer + 10-page book) could make the page very tall. Mitigations: (a) result regions are closeable via the × button; (b) the page is scroll-based, not a fixed-viewport SPA; (c) the Figure viewer and book page list both have bounded heights. The architect should evaluate whether a "tab" model (one active result panel, switching tabs) would better serve the mobile UX — but this spec recommends against it because of the Figure job duration issue.

### B. Book Builder with empty Story field

**Decision:** `concept` falls back to `character`, then to `'A fun adventure story'`. The book always starts.

**Risk:** If the user has no character either, Claude receives a very thin concept. The result is likely a generic storybook, which is acceptable for a mobile launcher — the full Book Builder workflow exists for richer authoring.

**Flag for architect:** The `concept` field and the `character` field are separate arguments to `/decompose`. Sending the character text as BOTH `concept` and `character` means Claude sees the protagonist description twice — once as the story seed and once as the character pin. This is likely harmless (Claude uses both sensibly) but the architect should confirm whether a blank `concept` with a populated `character` is a valid call that produces reasonable output, or whether `concept` should default to something else.

### C. Book Builder v1 does not hand off story to full Book Builder

**Decision:** "Open in Book Builder" navigates to `book_builder.html` without serializing the inline decompose result.

**Risk:** The user loses the inline decomposed story and must re-run decompose in Book Builder. This costs ~20 s and another API call.

**Flag for architect:** A v2 enhancement could write the `DecomposeResponse` to `sessionStorage` and have `book_builder.js` read it on load (similar to how CG passes a cover image via `sessionStorage.setItem('cg_cover_filename', …)`). This spec explicitly defers that to v2 to keep scope manageable.

### D. Fixed language (zh) for mobile Book Builder

**Decision:** `language: 'zh'` is hardcoded in the mobile decompose payload.

**Risk:** Users who want Japanese or Korean storybooks must navigate to the full Book Builder. On mobile this is a significant restriction.

**Flag for architect:** A three-button language toggle (zh / ja / ko) in the Book result region header (appearing before the "Writing…" state resolves) is a natural extension. This spec defers it to avoid scope creep but recommends the architect evaluate whether it should be in v1.

### E. ES module tension with shared_inputs.js

**Decision:** The page uses the same pattern as `gallery.html`: non-module `shared_inputs.js` loaded before the ES module. `window.SharedInputs` is accessed at module execution time, which is safe because ES modules are deferred.

**Risk:** If a browser does not support ES modules + import maps (rare but possible on older WebViews if a Capacitor shell is added), the page breaks silently. Architect should specify minimum browser/WebView versions if a native shell is planned.

### F. `POST /generate` vs `POST /generate/stream`

**Decision:** This spec recommends `POST /generate` (non-streaming) for Create Image on the mobile page.

**Rationale:** There is only one image, not a queue of N pages. The SSE handshake adds complexity (EventSource, reconnect logic) with no meaningful UX benefit — the Gemini call resolves in seconds either way. The spinner-then-image reveal is equivalent.

**Flag for architect:** If the developer prefers streaming for consistency with `book_builder.js`'s single-page regen, `POST /generate/stream` is equally valid. The spec is non-prescriptive on this point as long as the same `GenerateRequest` shape is sent.
