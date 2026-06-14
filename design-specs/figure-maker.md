# Figure Maker — Design Spec
# BookBuilderBot · New Page (`figure_maker.html`)

Status: Ready for developer-agent implementation
New files: `frontend/figure_maker.html` (replace placeholder), `frontend/figure_maker.css`, `frontend/figure_maker.js` (replace stub)
Shared dependencies: `frontend/style.css` (all MCM tokens and shared components — no edits needed)

---

## 1. Purpose

Figure Maker is a kid-friendly 3D model generator. A child types what they want to build, Bolt the mascot mascot narrates the process, Claude rewrites the input into a strong Meshy prompt, Meshy runs a two-stage async job (preview → refine), and the result is shown in an interactive three.js viewer alongside a kid/parent-friendly print-readiness report.

This page is a polling-based async workflow, unlike the SSE streaming used by the image generator pages. The frontend POSTs to `/figure/generate`, receives a `job_id`, then polls `/figure/status/{job_id}` every ~2 seconds until `stage === "done"` or `stage === "error"`.

---

## 2. three.js CDN approach

The page uses ES module imports via an import map. This must appear in `<head>` before any `<script type="module">`. No bundler, no npm.

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

`figure_maker.js` must be `<script type="module">` to use these imports. The existing `figure_maker.js` stub uses a plain `<script>` — this must change. The health-check code it contains (the only thing in the stub) is carried forward into the module script.

Pin the three.js version (`0.169.0` shown above is an example — developer should verify the latest stable at implementation time and lock it). Do not use a version range (`@latest`).

---

## 3. Layout

### 3a. Overall shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Figure Maker · MonkeyKing</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@400;600;700;800&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="figure_maker.css">

  <script type="importmap">
  {
    "imports": {
      "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
    }
  }
  </script>
</head>
<body>

  <a href="#fmMain" class="skip-link">Skip to main content</a>

  <header>
    <div class="header-inner">
      <div class="header-title">
        <span class="title-zh">齐天大圣</span>
        <span class="title-en">MonkeyKing Story Studio</span>
      </div>
      <nav class="header-nav" aria-label="Main navigation">
        <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
        <a href="book_builder.html"        class="nav-link">📖 Book Builder</a>
        <a href="figure_maker.html"        class="nav-link active">🧩 Figure Maker</a>
        <a href="gallery.html"             class="nav-link">🖼 Gallery</a>
      </nav>
      <div class="server-status">
        <span class="status-dot" id="statusDot"></span>
        <span id="statusLabel">Connecting…</span>
      </div>
    </div>
  </header>

  <main class="fm-main" id="fmMain">

    <!-- Mascot zone — always visible, sits above the two-column layout -->
    <div class="fm-mascot-zone" id="fmMascotZone" aria-live="polite" aria-atomic="true">
      <!-- spec: section 5 -->
    </div>

    <div class="fm-layout">

      <!-- LEFT: Controls/prompt panel -->
      <aside class="fm-controls-panel" aria-label="Figure generation controls">
        <!-- spec: section 4 -->
      </aside>

      <!-- RIGHT: Viewer + report area -->
      <section class="fm-result-area" aria-label="3D model viewer and print report">
        <!-- spec: sections 6 and 7 -->
      </section>

    </div>

  </main>

  <script type="module" src="figure_maker.js"></script>
</body>
</html>
```

### 3b. Layout grid behaviour

| Breakpoint | Columns | Viewer column |
|---|---|---|
| < 700 px (mobile) | 1 column — controls stack above result | Full width |
| >= 700 px (desktop) | 2 columns: `7fr 4fr` — result area is the larger left column; controls are the narrower right column | `7fr` |

**Note on column order:** Unlike `character_generator.html` where controls are on the left, Figure Maker puts the viewer/result area in the larger left column on desktop, matching the source app's priority (the 3D model is the hero). Controls are on the right. On mobile both columns collapse to a single column, controls appearing first (DOM order) so the user sees the prompt before the empty viewer.

```css
/* Desktop column order */
.fm-layout {
  display: grid;
  grid-template-columns: 7fr 4fr;
  gap: 1.5rem;
  align-items: start;
}

/* Mobile: reverse visual order so controls come first */
@media (max-width: 700px) {
  .fm-layout {
    grid-template-columns: 1fr;
  }
  .fm-controls-panel { order: -1; } /* controls first on mobile */
}
```

### 3c. Page-level sizing

```css
.fm-main {
  flex: 1;
  max-width: 1200px;   /* matches .cg-main */
  margin: 0 auto;
  width: 100%;
  padding: 1.5rem 1rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
```

---

## 4. Controls / Prompt Panel

The controls panel is a `.builder-step`-style card (mustard left border, same as the Character Generator controls card). It is always visible.

### 4a. Card skeleton

```html
<aside class="fm-controls-panel" aria-label="Figure generation controls">
  <div class="fm-controls-card" id="fmControlCard" style="border-left: 5px solid var(--mustard)">

    <div class="fm-controls-header">
      <h2>What do you want to build?</h2>
    </div>

    <!-- PROMPT INPUT -->
    <div class="control-group" id="fmPromptGroup">
      <label for="fmPromptInput">Describe your figure</label>
      <textarea
        id="fmPromptInput"
        rows="4"
        placeholder="A roaring T-Rex with tiny arms…"
        aria-describedby="fmPromptHint"
        required
        maxlength="500"
      ></textarea>
      <p class="hint" id="fmPromptHint">
        Type anything — Bolt will help turn it into a great 3D design!
      </p>
    </div>

    <!-- QUICK-PICK CHIPS -->
    <div class="control-group" id="fmChipGroup" style="margin-top: .75rem">
      <label id="fmChipLabel">Quick ideas</label>
      <div class="presets" id="fmChips" role="group" aria-labelledby="fmChipLabel">
        <button class="preset" data-prompt="rocket ship">🚀 Rocket ship</button>
        <button class="preset" data-prompt="dinosaur">🦖 Dinosaur</button>
        <button class="preset" data-prompt="cute kitty cat">🐱 Kitty</button>
        <button class="preset" data-prompt="fantasy castle">🏰 Castle</button>
        <button class="preset" data-prompt="friendly robot">🤖 Robot</button>
        <button class="preset" data-prompt="pirate ship">🏴‍☠️ Pirate ship</button>
        <button class="preset" data-prompt="rainbow unicorn">🦄 Unicorn</button>
      </div>
    </div>

    <!-- GENERATE BUTTON -->
    <button
      class="generate-btn"
      id="fmGenerateBtn"
      style="width: 100%; margin-top: 1.25rem"
    >
      <span id="fmGenerateLabel">🧩 Build my figure!</span>
      <div class="spinner hidden" id="fmSpinner" aria-hidden="true"></div>
    </button>

    <!-- ENHANCED PROMPT REVEAL (shown after prompting stage completes) -->
    <div class="fm-enhanced-prompt hidden" id="fmEnhancedPromptBox" aria-live="polite">
      <p class="fm-enhanced-label">Bolt's version of your idea:</p>
      <p id="fmEnhancedPromptText"></p>
    </div>

    <!-- INLINE ERROR -->
    <p class="cg-error hidden" id="fmErrorMsg" role="alert" aria-live="assertive"></p>

    <!-- MAKE ANOTHER (ready state only) -->
    <button
      class="settings-btn hidden"
      id="fmResetBtn"
      style="width: 100%; margin-top: .75rem; justify-content: center;"
      aria-label="Clear and start over"
    >↺ Make another</button>

  </div>
</aside>
```

**Chip behaviour:** Clicking a chip sets the textarea value to the chip's `data-prompt` and marks the chip `.active` (radio behaviour — only one active at a time). If the user edits the textarea after selecting a chip, the chip is de-activated. Clicking the active chip again clears the textarea and deactivates it.

**Enhanced prompt box:** After the `prompting` stage completes, the backend returns `enhanced_prompt`. Show the `.fm-enhanced-prompt` div with the text, styled as a muted italic inset — gives the child/parent visibility into what was actually sent to Meshy. Hidden again on reset.

**"Make another" reset button:** Uses `.settings-btn` (not `.generate-btn`) to be visually quieter. Appears only in the `ready` or `error` states, below the error message.

---

## 5. Bolt Mascot Zone

Bolt is a contextual emoji robot with a speech bubble. He appears above the two-column layout and narrates every stage.

### 5a. Markup skeleton

```html
<div class="fm-mascot-zone" id="fmMascotZone" aria-live="polite" aria-atomic="true">
  <div class="bolt-mascot" aria-hidden="true">🤖</div>
  <div class="bolt-bubble" id="fmBoltBubble" role="status">
    <span id="fmBoltText">What should we build today?</span>
  </div>
</div>
```

The `aria-live="polite"` on the wrapper zone means screen readers announce stage changes without interrupting ongoing speech. `aria-atomic="true"` ensures the full bubble text is announced, not just the changed portion. `role="status"` on the bubble itself is redundant with the live region but adds belt-and-suspenders compatibility. The `.bolt-mascot` emoji is `aria-hidden="true"` — the text content is what matters.

### 5b. Stage → message map

JS should call `setBoltMessage(msg)` on every `stage` change. The developer should implement this as a small lookup table:

| `stage` value | Bolt's message |
|---|---|
| *(idle — page load)* | "What should we build today?" |
| *(idle — after reset)* | "Let's make something new! What should it be?" |
| `prompting` | "Ooh, great idea! I'm thinking up the perfect design…" |
| `preview` | "Sculpting your shape — almost like magic!" |
| `refine` | "Painting it and adding all the details…" |
| `downloading` | "Packing it up and bringing it over…" |
| `analyzing` | "Checking if it's ready to print…" |
| `done` | "Ta-da! Here's your very own 3D figure! 🎉" |
| `error` | "Oops! Something went wobbly. Let's try again!" |

### 5c. Visual treatment

```css
.fm-mascot-zone {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: .75rem 1rem;
  background: var(--paper-dark);
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border-left: 5px solid var(--teal); /* teal = output/result accent */
}

.bolt-mascot {
  font-size: 2.5rem;
  line-height: 1;
  flex-shrink: 0;
  /* Subtle bounce animation when generating */
}
.bolt-mascot.bolt-bounce {
  animation: boltBounce 0.6s ease infinite alternate;
}
@keyframes boltBounce {
  from { transform: translateY(0); }
  to   { transform: translateY(-5px); }
}

.bolt-bubble {
  flex: 1;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.4;
}
```

The `.bolt-bounce` class is added to `.bolt-mascot` while `stage` is anything other than `idle`/`done`/`error`, and removed otherwise.

---

## 6. Generation Progress (generating state)

Shown inside `.fm-result-area`, replacing the viewer empty-state when generation is underway.

### 6a. Markup skeleton

```html
<!-- GENERATING STATE (hidden until generation begins) -->
<div class="fm-progress-state hidden" id="fmProgressState" aria-label="Generating your figure">

  <!-- Stage label -->
  <p class="fm-stage-label" id="fmStageLabel" aria-live="polite">
    Dreaming up your idea…
  </p>

  <!-- Progress bar -->
  <div
    class="fm-progress-track"
    role="progressbar"
    aria-valuenow="0"
    aria-valuemin="0"
    aria-valuemax="100"
    aria-labelledby="fmStageLabel"
    id="fmProgressBar"
  >
    <div class="fm-progress-fill" id="fmProgressFill" style="width: 0%"></div>
  </div>

  <p class="fm-progress-pct hint" id="fmProgressPct">0%</p>

</div>
```

JS updates `#fmProgressFill` width, `aria-valuenow` on `#fmProgressBar`, and `#fmProgressPct` text on each poll response.

### 6b. Stage → kid-friendly label map

| `stage` | Label text |
|---|---|
| `prompting` | "Dreaming up your idea…" |
| `preview` | "Sculpting the shape…" |
| `refine` | "Painting it in…" |
| `downloading` | "Almost ready…" |
| `analyzing` | "Checking the details…" |

### 6c. Progress bar CSS

Reuse the visual pattern of the book builder's progress bar (`progress-bar` / `progress-bar-track` in `book_builder.css`), but defined in `figure_maker.css` with `fm-` prefixes to avoid conflicts (the book builder CSS is not loaded on this page).

```css
.fm-progress-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .75rem;
  padding: 3rem 2rem;
  width: 100%;
}

.fm-stage-label {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ink);
  text-align: center;
}

.fm-progress-track {
  width: 100%;
  max-width: 360px;
  height: 12px;
  background: var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.fm-progress-fill {
  height: 100%;
  background: var(--teal);
  border-radius: 6px;
  transition: width .4s ease;
}

.fm-progress-pct {
  font-size: .85rem;
  color: var(--muted);
}
```

---

## 7. 3D Viewer (ready state)

### 7a. Frame markup

```html
<!-- EMPTY STATE (default) -->
<div class="fm-viewer-empty" id="fmViewerEmpty">
  <span class="fm-viewer-empty-icon" aria-hidden="true">🧩</span>
  <p>Your 3D figure will appear here.</p>
  <p class="hint">Type what you want to build and hit the button!</p>
</div>

<!-- 3D VIEWER FRAME (hidden until ready) -->
<div class="fm-viewer-frame hidden" id="fmViewerFrame">

  <!-- three.js canvas mounts here -->
  <div
    id="fmViewer"
    role="img"
    aria-label="Interactive 3D model viewer — drag to rotate, scroll to zoom"
    style="width: 100%; height: 100%;"
  ></div>

  <!-- Viewer controls hint -->
  <p class="fm-viewer-hint" aria-hidden="true">Drag to rotate · Scroll to zoom</p>

  <!-- Error boundary fallback (hidden unless three.js throws) -->
  <div class="fm-viewer-error hidden" id="fmViewerError" role="alert">
    <span aria-hidden="true">⚠️</span>
    <p>Couldn't load the 3D model.</p>
    <p class="hint" id="fmViewerErrorDetail"></p>
    <a class="settings-btn" id="fmDownloadGlbBtn" href="#" download="figure.glb">
      ↓ Download GLB
    </a>
  </div>

</div>
```

`#fmViewer` is the mount target for the three.js `WebGLRenderer`. JS creates the `<canvas>` element and appends it here. Do not put a `<canvas>` in the HTML — three.js owns it.

`role="img"` with a descriptive `aria-label` on `#fmViewer` gives screen readers a sensible summary of the interactive region. The canvas itself gets `aria-hidden="true"` once three.js creates it (JS responsibility).

### 7b. Viewer sizing

```css
.fm-viewer-frame {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;

  /* Mobile sizing */
  height: 60svh;
  min-height: 360px;
  max-height: 560px;
}

/* Desktop — taller, let the 7fr column breathe */
@media (min-width: 700px) {
  .fm-viewer-frame {
    height: 600px;
    max-height: none;
  }
}

@media (min-width: 1100px) {
  .fm-viewer-frame {
    height: 680px;
  }
}
```

The viewer container uses a fixed pixel height on desktop (not a min-height trick) so OrbitControls and the renderer resize correctly.

### 7c. Viewer hint overlay

```css
.fm-viewer-hint {
  position: absolute;
  bottom: .75rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: .75rem;
  color: var(--muted);
  background: rgba(245,240,232,.80);
  padding: .25rem .65rem;
  border-radius: 20px;
  pointer-events: none;
  white-space: nowrap;
  /* Fade out after first interaction — JS adds .hint-faded */
  opacity: 1;
  transition: opacity .6s;
}
.fm-viewer-hint.hint-faded { opacity: 0; }
```

### 7d. Viewer empty state

```css
.fm-viewer-empty {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: .5rem;
  color: var(--muted);
  text-align: center;
  padding: 3rem 2rem;
  min-height: 360px;
}
.fm-viewer-empty-icon {
  font-size: 3.5rem;
  line-height: 1;
  opacity: .35;
}
```

### 7e. Error boundary treatment

The `#fmViewerError` div is an overlay positioned absolutely within `.fm-viewer-frame` (full cover). JS catches loader exceptions in a try/catch around the `GLTFLoader.load()` call and shows this div, hiding the canvas. The `.fm-viewer-error` provides the model URL via a download link so the user can still retrieve the file.

```css
.fm-viewer-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: .75rem;
  background: rgba(245,240,232,.95);
  padding: 2rem;
  text-align: center;
  border-radius: calc(var(--radius) - 2px);
}
.fm-viewer-error.hidden { display: none; }
```

### 7f. three.js setup notes (for developer)

- Import `GLTFLoader` from `'three/addons/loaders/GLTFLoader.js'` and `OrbitControls` from `'three/addons/controls/OrbitControls.js'`.
- Renderer: `antialias: true`, `alpha: true` (transparent background so the `#faf7f2` card shows through). Set `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))`.
- Camera: `PerspectiveCamera(45, aspect, 0.1, 100)`. Position at `(0, 0, 3)` initially; after load, compute the model bounding box and move the camera to fit (same intent as the source app's `<Bounds fit>`). A simple approach: get the bounding sphere radius, set `camera.position.z = radius * 2.5`.
- `OrbitControls`: enable damping (`enableDamping: true`, `dampingFactor: 0.05`). Auto-rotate at `autoRotateSpeed: 1.5`. Stop auto-rotate on `'start'` event; resume after 10 s idle via `setTimeout` (clear on `'start'` and on model swap).
- Lighting: `AmbientLight(0xffffff, 0.6)` + `DirectionalLight(0xffffff, 1.2)` at `(5, 10, 5)`. This gives clean mid-century neutral lighting.
- On `ResizeObserver` of `#fmViewer`, call `renderer.setSize()` and update `camera.aspect`.
- Dispose: on reset (`#fmResetBtn` click), call `renderer.dispose()`, remove the canvas, null the renderer reference. Re-instantiate on next successful load.

---

## 8. Print Report Card (ready state)

The report appears below the viewer on mobile, and below the controls panel on desktop (inside `.fm-result-area` on mobile / stacked in the controls column on desktop).

**Layout placement:** The report card lives inside `.fm-result-area`, stacked below `.fm-viewer-frame`. On desktop (7fr/4fr), this means the report sits below the large viewer — which is the natural reading flow. The controls panel stays sticky on the right.

```html
<!-- PRINT REPORT (hidden until ready) -->
<div class="fm-report-card hidden" id="fmReportCard">

  <div class="fm-report-header">
    <span class="fm-report-icon" aria-hidden="true">🖨️</span>
    <h3>Print Report</h3>
    <span class="fm-filament-tag" id="fmFilamentTag" aria-label="Suggested filament">PLA</span>
  </div>

  <p class="fm-report-text" id="fmReportText">
    <!-- Populated by JS from backend report field -->
  </p>

  <div class="fm-report-actions">
    <a
      class="settings-btn"
      id="fmDownloadStlBtn"
      href="#"
      download="figure.stl"
      aria-label="Download STL file for 3D printing"
    >↓ Download STL</a>
    <a
      class="settings-btn"
      id="fmDownloadGlbBtn2"
      href="#"
      download="figure.glb"
      aria-label="Download GLB file"
    >↓ Download GLB</a>
  </div>

</div>
```

### 8a. Report card CSS

```css
.fm-report-card {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border-left: 5px solid var(--olive); /* olive = analysis/report accent */
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: .75rem;
}
.fm-report-card.hidden { display: none; }

.fm-report-header {
  display: flex;
  align-items: center;
  gap: .5rem;
}
.fm-report-header h3 {
  font-size: 1rem;
  font-weight: 800;
  color: var(--ink);
  flex: 1;
}
.fm-report-icon { font-size: 1.2rem; }

.fm-filament-tag {
  font-size: .75rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--olive-dark);
  background: rgba(107,124,58,.12);
  border: 1px solid rgba(107,124,58,.30);
  border-radius: 12px;
  padding: .2rem .55rem;
}

.fm-report-text {
  font-size: .9rem;
  color: var(--ink-soft);
  line-height: 1.55;
}

.fm-report-actions {
  display: flex;
  gap: .5rem;
  flex-wrap: wrap;
}
```

The `olive` accent is used for the report card border because olive is already in the MCM palette (`var(--olive)`, `var(--olive-dark)`) and was not used for either the controls (mustard) or the viewer/mascot zone (teal). This gives the three main cards distinct MCM accent colors without introducing new tokens.

---

## 9. State Machine

### 9a. State table

| State | Visible elements | `#fmGenerateBtn` | `#fmResetBtn` | Notes |
|---|---|---|---|---|
| **idle** | `#fmViewerEmpty`, `#fmMascotZone` | Enabled | Hidden | Default on page load |
| **generating** | `#fmProgressState` (replaces empty), `#fmMascotZone` (bolt bouncing) | Disabled, spinner shown, label hidden | Hidden | Input and chips disabled |
| **ready** | `#fmViewerFrame`, `#fmReportCard`, `#fmEnhancedPromptBox`, `#fmMascotZone` | Hidden (replaced by reset) | Visible | viewer empty state hidden |
| **error** | `#fmViewerEmpty`, `#fmErrorMsg`, `#fmMascotZone` | Re-enabled | Visible | Enhanced prompt hidden if error was in `prompting` stage |

### 9b. Generating sub-states

Within the `generating` macro-state, the stage value drives the progress bar and Bolt's message. The input textarea and chip buttons are `disabled` (not just visually muted). The generate button shows `.spinner` and hides `#fmGenerateLabel`.

On reset (`#fmResetBtn` click):
- Clear textarea, deactivate all chips.
- Hide `#fmViewerFrame`, `#fmReportCard`, `#fmEnhancedPromptBox`, `#fmErrorMsg`, `#fmResetBtn`.
- Show `#fmViewerEmpty`.
- Dispose the three.js renderer.
- Set Bolt to idle message.
- Re-enable generate button (show label, hide spinner).
- Re-enable textarea and chips.

---

## 10. Polling logic (JS responsibility)

```
POST /figure/generate { prompt: textarea.value }
  → { job_id }

Poll GET /figure/status/{job_id} every 2000ms:
  → { stage, progress, enhanced_prompt?, model_url?, stl_url?, report?, error? }

On each poll:
  - Update progress bar fill and aria-valuenow to response.progress
  - Update stage label and Bolt message using stage lookup tables
  - If enhanced_prompt present and not yet shown: reveal #fmEnhancedPromptBox
  - If stage === "done": load GLB via GLTFLoader(model_url), show report, stop polling
  - If stage === "error": show error state, stop polling
  - Otherwise: continue polling
```

Stop polling in all terminal states (`done`, `error`). Also cancel any in-flight poll if `#fmResetBtn` is clicked mid-generation (use an `AbortController` or a module-level boolean flag `_cancelled`).

---

## 11. CSS file organization

All page-specific styles go in `frontend/figure_maker.css`. No edits to `style.css` are needed.

Classes reused from `style.css` as-is (no redeclaration needed):
- `.control-group` + `label` + `textarea` focus ring
- `.presets` + `.preset` (including `:hover`, `.active` states)
- `.generate-btn` (including `:disabled`, spinner integration)
- `.spinner` (including `.hidden` toggle, `@keyframes spin`)
- `.settings-btn`
- `.hint`
- `.cg-error` — reused verbatim from `character_generator.css`. The developer should either extract this to `style.css` as a shared utility or copy the 9-line rule block into `figure_maker.css` as `.cg-error`. Flagged below.

Classes that must be declared in `figure_maker.css`:
- All `.fm-*` classes defined in sections 3–9 above.
- `.skip-link` — copy from `character_generator.css` (same 6-line block); it is not in `style.css`.
- `.bolt-mascot`, `.bolt-bubble`, `.bolt-bounce`, `@keyframes boltBounce`.

### 11a. Controls card (`.fm-controls-card`)

The card is styled identically to `.cg-controls-panel .builder-step` but without importing `book_builder.css`. Redeclare the card treatment in `figure_maker.css`:

```css
.fm-controls-card {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.5rem;
  /* border-left set inline on the element */
}
.fm-controls-header {
  margin-bottom: 1.1rem;
}
.fm-controls-header h2 {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--ink);
}
.fm-controls-panel {
  position: sticky;
  top: 4rem; /* clears header */
}
@media (max-width: 700px) {
  .fm-controls-panel { position: static; }
}
```

### 11b. Enhanced prompt box

```css
.fm-enhanced-prompt {
  margin-top: .75rem;
  background: rgba(58,125,122,.07);
  border: 1px solid rgba(58,125,122,.25);
  border-radius: 10px;
  padding: .6rem .8rem;
}
.fm-enhanced-prompt.hidden { display: none; }
.fm-enhanced-label {
  font-size: .72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--teal-dark);
  margin-bottom: .25rem;
}
#fmEnhancedPromptText {
  font-size: .85rem;
  color: var(--ink-soft);
  font-style: italic;
  line-height: 1.45;
}
```

---

## 12. Accessibility notes

- `<a href="#fmMain" class="skip-link">Skip to main content</a>` — present before `<header>`, using the same `.skip-link` rule as `character_generator.css`.
- `#fmPromptInput` has `<label for="fmPromptInput">` and `aria-describedby="fmPromptHint"`.
- `#fmChips` group uses `role="group"` + `aria-labelledby="fmChipLabel"`. Individual chip `<button>` elements have visible emoji + text labels — no additional ARIA needed. The emoji is presentational within a button that has full text content.
- `#fmGenerateBtn`: when entering the generating state, set `aria-disabled="true"` and `disabled`. Do not rely solely on opacity. After generation, restore both.
- `#fmProgressBar`: `role="progressbar"` with `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-labelledby="fmStageLabel"`. Update `aria-valuenow` on every poll.
- `#fmViewer` (`role="img"`): The `aria-label` should be updated when the model loads to include the model name, e.g. `"3D model of a rocket ship — drag to rotate, scroll to zoom"`. The canvas element created by three.js should have `aria-hidden="true"` set by JS immediately after creation.
- `#fmMascotZone`: `aria-live="polite"` announces Bolt's stage messages. Use `aria-atomic="true"` so the full sentence is read. Do not use `aria-live="assertive"` — stage changes are informational, not urgent.
- `#fmErrorMsg`: `role="alert"` + `aria-live="assertive"` for immediate announcement on error.
- All `.settings-btn` links/buttons that trigger downloads must have descriptive `aria-label` attributes (the visible `↓ Download STL` text is acceptable but `aria-label="Download STL file for 3D printing"` is better for context).
- Touch targets: `.generate-btn` has `min-height: 48px` (already in `style.css`). `.settings-btn` has `min-height: 36px` — acceptable for secondary actions; if this page is used on touch devices, verify by inspection. Chips (`.preset`) have `min-height: 36px`. Consider increasing chip `padding` on mobile if testers flag tap difficulty.
- Contrast: all text on `#faf7f2` backgrounds uses `var(--ink)` (`#2c2416`) or `var(--ink-soft)` (`#5a4a38`), both verified >4.5:1 against the card background in the `mcm-redesign.md` spec. The teal progress fill (`#3a7d7a`) does not carry text — no contrast check needed. The filament tag (`var(--olive-dark)` on olive-tint background) should be checked by the developer; it is borderline and may need `font-weight: 800` to compensate.
- Keyboard navigation: natural DOM order gives focus path: skip link → header nav → textarea → chips → generate button → (when ready) reset button → download buttons. The sticky controls panel does not disrupt DOM order. The `<canvas>` created by three.js is not keyboard-focusable by default — this is acceptable since the viewer is a supplementary visual; meaningful interaction is via the download buttons.
- `reduced-motion`: add a media query to disable `.bolt-bounce` animation and the progress fill `transition`:

```css
@media (prefers-reduced-motion: reduce) {
  .bolt-mascot.bolt-bounce { animation: none; }
  .fm-progress-fill { transition: none; }
  .fm-viewer-hint { transition: none; }
}
```

---

## 13. Consistency flags

**Flag 1 — `.cg-error` is not in `style.css`:** The terracotta error message style is defined in `character_generator.css` and is needed here too. Two options: (a) copy the 9-line block into `figure_maker.css` as `.cg-error` (quick, creates minor duplication), or (b) move it to `style.css` as a shared utility (cleaner, requires touching `character_generator.css` to remove the local copy). Recommend option (b) as a follow-up cleanup, with option (a) acceptable for now.

**Flag 2 — `.skip-link` is not in `style.css`:** Same issue as `.cg-error` — currently only in `character_generator.css`. Both `figure_maker.html` and any future pages need it. Recommend the developer copy into `figure_maker.css` now, and flag for extraction to `style.css`.

**Flag 3 — `figure_maker.js` is currently a plain `<script>`, not `type="module"`:** The existing `figure_maker.html` uses `<script src="figure_maker.js">`. The three.js ESM import map requires the consuming script to be `type="module"`. This is a breaking change to the existing stub but the stub is trivial (health check only) and the change is contained to one line in the HTML and one change in how the JS file is structured. The health-check code should be retained and called from inside the module.

**Flag 4 — `style.css` has a `.figure-main` and `.figure-placeholder` block** (lines 353–371) that was the placeholder for this page. Once `figure_maker.css` is in use, those rules become dead code. They do not conflict (different class names), but the developer should remove them from `style.css` to avoid confusion.

**Flag 5 — column order inversion vs. Character Generator:** All other two-column pages (book builder, character generator) put controls on the left. Figure Maker inverts this to give the viewer the larger column on the left. This is intentional and matches the source app's design intent (model is the hero). No CSS conflict, but the developer should verify that the sticky controls column (`top: 4rem`) still works correctly on the right side — it does, since `position: sticky` is column-agnostic.

---

## 14. File checklist for developer-agent

- `frontend/figure_maker.html` — replace the placeholder body content with the markup skeleton in this spec. Keep the `<head>` font/CSS links and add the importmap. Change `<script src="figure_maker.js">` to `<script type="module" src="figure_maker.js">`.
- `frontend/figure_maker.css` — new file. All `.fm-*` rules, `.bolt-*` rules, `.skip-link` copy, `.cg-error` copy.
- `frontend/figure_maker.js` — replace the stub. Must be an ES module. Retain health-check code. Implement state machine, polling loop, three.js viewer setup/teardown, Bolt message updates.
- `frontend/style.css` — remove the dead `.figure-main` / `.figure-placeholder` block (lines 353–371). No other changes needed.
