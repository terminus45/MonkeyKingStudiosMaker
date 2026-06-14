# Gallery Split (Images / Books / 3D Models) — Design Spec
# BookBuilderBot · `gallery.html` redesign

Status: Ready for developer-agent implementation
Modified files: `frontend/gallery.html`, `frontend/gallery.css`, `frontend/gallery.js`
Shared dependencies: `frontend/style.css`, `frontend/storybook_print.js` (unchanged)
New dependency: three.js via CDN importmap (for 3D model viewer modal — same version as figure_maker)

---

## 1. Overview

The gallery gains a **three-tab segmented control** at the top that switches between three content panels. Only the active panel is visible. Each panel has its own grid, loading state, empty state, and error message. The URL can optionally carry `?tab=images|books|models` so deep-linking from other pages works.

---

## 2. Tab bar component

### 2a. Visual design

Reuse the `.lang-toggle` / `.lang-btn` pattern from `book_builder.css`. The tab bar is the same pill-row segmented control already in the app — a rounded border wraps three buttons, the active one fills with mustard, inactive ones are muted. This is the canonical "segmented control" in the MCM design system.

However, the tab bar is wider than the language toggle (three longer labels), so it uses `width: 100%` rather than `width: fit-content`, and tabs are `flex: 1` to fill equally.

Visual: A full-width (up to ~480 px on desktop) pill row with three tabs — "🖼 Images", "📖 Books", "🧊 3D Models". The active tab has a mustard fill (`var(--mustard)`, `color: var(--ink)`). Hover on inactive tabs shows teal tint (matches `.lang-btn:hover`).

### 2b. Markup skeleton

The tab bar sits inside `.gallery-toolbar`, replacing the old static `<h2>Saved Storybooks</h2>`. The heading becomes the accessible name of the tablist.

```html
<div class="gallery-toolbar">
  <div
    class="gallery-tabs"
    role="tablist"
    aria-label="Gallery type"
  >
    <button
      class="gallery-tab active"
      id="tab-images"
      role="tab"
      aria-selected="true"
      aria-controls="panel-images"
      data-tab="images"
    >🖼 Images</button>
    <button
      class="gallery-tab"
      id="tab-books"
      role="tab"
      aria-selected="false"
      aria-controls="panel-books"
      tabindex="-1"
      data-tab="books"
    >📖 Books</button>
    <button
      class="gallery-tab"
      id="tab-models"
      role="tab"
      aria-selected="false"
      aria-controls="panel-models"
      tabindex="-1"
      data-tab="models"
    >🧊 3D Models</button>
  </div>

  <button id="refreshBtn" class="project-btn">↺ Refresh</button>
</div>
```

Keyboard behaviour (ARIA tabs pattern):
- Arrow left/right moves focus between tabs and activates the tab (automatic activation).
- `Home` / `End` jump to first/last.
- Non-focused tabs get `tabindex="-1"`; the active tab has no `tabindex` (default 0).

### 2c. Tab bar CSS

Add to `gallery.css`:

```css
.gallery-tabs {
  display: flex;
  border: 2px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  background: var(--ctrl-bg);
  /* fill the toolbar, capped at a sensible width */
  max-width: 480px;
  flex: 1;
}

.gallery-tab {
  flex: 1;
  background: transparent;
  border: none;
  border-right: 2px solid var(--border);
  padding: .5rem .75rem;
  font-size: .88rem;
  font-family: inherit;
  font-weight: 700;
  color: var(--ink-soft);
  cursor: pointer;
  transition: background .15s, color .15s;
  min-height: 44px;
  white-space: nowrap;
}
.gallery-tab:last-child { border-right: none; }
.gallery-tab:hover:not(.active) {
  color: var(--teal);
  background: rgba(58,125,122,.08);
}
.gallery-tab.active,
.gallery-tab[aria-selected="true"] {
  background: var(--mustard);
  color: var(--ink);
}
```

On mobile (≤ 480 px) the tab labels may need to shorten. Allow the emoji only on the smallest breakpoint:

```css
@media (max-width: 480px) {
  .gallery-tab { font-size: .78rem; padding: .5rem .4rem; }
}
```

---

## 3. Panel structure

Three `<div role="tabpanel">` containers appear in the main area. Only the active one is visible.

```html
<main class="gallery-main">

  <!-- Tab bar lives in the toolbar above -->
  <div class="gallery-toolbar"> … </div>

  <!-- IMAGES PANEL -->
  <div
    id="panel-images"
    role="tabpanel"
    aria-labelledby="tab-images"
    class="gallery-panel"
    tabindex="0"
  >
    <div id="imagesGrid" class="gallery-image-grid">
      <p class="gallery-empty-msg" id="imagesEmpty">Loading…</p>
    </div>
  </div>

  <!-- BOOKS PANEL -->
  <div
    id="panel-books"
    role="tabpanel"
    aria-labelledby="tab-books"
    class="gallery-panel hidden"
    tabindex="0"
  >
    <div id="booksGrid" class="gallery-book-grid">
      <p class="gallery-empty-msg" id="booksEmpty">Loading…</p>
    </div>
  </div>

  <!-- 3D MODELS PANEL -->
  <div
    id="panel-models"
    role="tabpanel"
    aria-labelledby="tab-models"
    class="gallery-panel hidden"
    tabindex="0"
  >
    <div id="modelsGrid" class="gallery-model-grid">
      <p class="gallery-empty-msg" id="modelsEmpty">Loading…</p>
    </div>
  </div>

</main>
```

```css
.gallery-panel { display: flex; flex-direction: column; }
.gallery-panel.hidden { display: none; }
```

`tabindex="0"` on each panel allows keyboard users to tab into the panel content after activating the tab. The `aria-labelledby` connects the panel to its tab label.

---

## 4. Empty states

Each panel has its own copy of `.gallery-empty-msg`. The developer should set these messages via JS after the API response:

| Panel      | No-items text                                                                        |
|------------|--------------------------------------------------------------------------------------|
| Images     | "No saved images yet — make one in the Character Generator!"                         |
| Books      | "No saved storybooks yet — build one in the Book Builder!"                           |
| 3D Models  | "No saved 3D models yet — sculpt one in the Figure Maker!"                           |

All three use the existing `.gallery-empty-msg` class (centered, `color: var(--muted)`, `padding: 3rem 0`).

---

## 5. Books grid (unchanged)

The existing `.book-card` + `.gallery-book-grid` design is carried over without change. The grid is now inside `#panel-books` instead of directly in `<main>`. The JS `buildBookCard()` function is unchanged; only where cards are appended changes (`#booksGrid` instead of `#galleryGrid`).

---

## 6. Images grid

### 6a. Grid density

Character images are square portraits — they look good at a smaller card size than books. Use a denser grid:

```css
.gallery-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

@media (max-width: 600px) {
  .gallery-image-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .65rem; }
}
@media (max-width: 380px) {
  .gallery-image-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

### 6b. Image card markup

```html
<div class="image-card" data-filename="abc123.png">

  <div class="image-card-thumb">
    <img
      src="/image/abc123.png"
      alt="Character portrait: a brave young monkey king with golden fur"
      loading="lazy"
    >
  </div>

  <div class="image-card-info">
    <p class="image-card-prompt" title="Full prompt text here">
      A brave young monkey king with golden fur…
    </p>
    <p class="image-card-date">Jun 10, 2026</p>
  </div>

  <div class="image-card-actions">
    <a
      class="book-action-btn"
      href="/image/abc123.png"
      download="character-abc123.png"
      aria-label="Download image"
    >↓ Download</a>
    <button
      class="book-action-btn danger"
      data-action="delete-image"
      data-filename="abc123.png"
      aria-label="Delete image"
    >🗑</button>
  </div>

</div>
```

Reuse `.book-action-btn` (and `.book-action-btn.danger`) from `gallery.css` — no new button classes.

### 6c. Image card CSS

```css
.image-card {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color .18s, transform .18s, box-shadow .18s;
}
.image-card:hover {
  border-color: var(--mustard);
  transform: translateY(-3px);
  box-shadow: 0 8px 22px rgba(232,160,32,.22);
}

.image-card-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  background: var(--paper-dark);
  overflow: hidden;
}
.image-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-card-info {
  padding: .55rem .7rem .4rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: .2rem;
}
.image-card-prompt {
  font-size: .72rem;
  color: var(--ink-soft);
  line-height: 1.35;
  /* Clamp to 2 lines */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.image-card-date {
  font-size: .65rem;
  color: var(--muted);
}

/* Actions — reuse .book-actions / .book-action-btn from gallery.css */
.image-card .book-actions {
  display: flex;
  gap: .4rem;
  padding: .5rem .7rem;
  border-top: 2px solid var(--border);
}
```

### 6d. Alt text strategy

The alt text on each image should be derived from the prompt, truncated at ~80 characters. The `GET /gallery/images` response should include the `prompt` field. JS sets `img.alt = "Character portrait: " + prompt.slice(0, 80)`. Decorative-only images can use `alt=""` only if the prompt is truly unavailable.

---

## 7. 3D Models grid

### 7a. Grid density

Same density as the book grid — models are complex items with more metadata:

```css
.gallery-model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.5rem;
}

@media (max-width: 600px) {
  .gallery-model-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 380px) {
  .gallery-model-grid { grid-template-columns: 1fr; }
}
```

### 7b. Model card markup

```html
<div class="model-card" data-job-id="job_abc123">

  <!-- Thumbnail: Meshy thumbnail image or placeholder tile -->
  <div class="model-card-thumb">
    <!-- If thumbnail_url available: -->
    <img
      src="https://meshy-thumbnail-url…/preview.png"
      alt="3D model preview: a friendly robot"
      loading="lazy"
    >
    <!-- If no thumbnail: show placeholder tile (no <img>) -->
    <!-- .model-card-thumb gets class="model-card-thumb no-thumb" for the placeholder -->
    <div class="model-thumb-placeholder" aria-hidden="true">🧊</div>
  </div>

  <div class="model-card-info">
    <p class="model-card-title">A friendly robot</p>
    <div class="model-card-meta">
      <span class="model-filament-tag" aria-label="Suggested filament: PLA">PLA</span>
      <span class="model-card-date">Jun 12, 2026</span>
    </div>
  </div>

  <div class="book-actions">
    <button
      class="book-action-btn"
      data-action="view-model"
      data-job-id="job_abc123"
      data-glb-url="/output/model_abc123.glb"
      aria-label="View 3D model for a friendly robot"
    >🧊 View 3D</button>
    <a
      class="book-action-btn"
      href="/output/model_abc123.glb"
      download="model_abc123.glb"
      aria-label="Download GLB file"
    >↓ GLB</a>
    <button
      class="book-action-btn danger"
      data-action="delete-model"
      data-job-id="job_abc123"
      aria-label="Delete this 3D model"
    >🗑</button>
  </div>

</div>
```

### 7c. Model card CSS

```css
.model-card {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color .18s, transform .18s, box-shadow .18s;
}
.model-card:hover {
  border-color: var(--mustard);
  transform: translateY(-3px);
  box-shadow: 0 8px 22px rgba(232,160,32,.22);
}

.model-card-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  background: var(--paper-dark);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.model-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.model-thumb-placeholder {
  font-size: 3rem;
  opacity: .30;
  line-height: 1;
}
/* Hide placeholder when real image is present */
.model-card-thumb img ~ .model-thumb-placeholder { display: none; }

.model-card-info {
  padding: .8rem 1rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: .3rem;
}
.model-card-title {
  font-size: .95rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.3;
}

.model-card-meta {
  display: flex;
  align-items: center;
  gap: .5rem;
  flex-wrap: wrap;
}

/* Filament tag — olive chip (same treatment as .fm-filament-tag in figure_maker.css) */
.model-filament-tag {
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--olive-dark);
  background: rgba(107,124,58,.12);
  border: 1px solid rgba(107,124,58,.30);
  border-radius: 12px;
  padding: .18rem .5rem;
}

.model-card-date {
  font-size: .72rem;
  color: var(--muted);
}
```

---

## 8. 3D Model viewer modal

### 8a. Purpose

Clicking "View 3D" on a model card opens a full-screen overlay containing a three.js viewer. The overlay is not a new page — it is an `<div>` injected into the DOM of `gallery.html`.

### 8b. Markup skeleton (injected once, reused)

The modal is inserted into `<body>` once on page load, hidden by default. When a "View 3D" button is clicked, the GLB URL is passed to the viewer and the modal is shown.

```html
<!-- Model viewer modal — injected once, hidden until needed -->
<div
  class="model-viewer-modal hidden"
  id="modelViewerModal"
  role="dialog"
  aria-modal="true"
  aria-label="3D model viewer"
>
  <div class="model-viewer-backdrop" id="modelViewerBackdrop" aria-hidden="true"></div>

  <div class="model-viewer-content">

    <div class="model-viewer-header">
      <h3 class="model-viewer-title" id="modelViewerTitle">3D Model</h3>
      <button
        class="model-viewer-close"
        id="modelViewerClose"
        aria-label="Close 3D viewer"
      >✕</button>
    </div>

    <!-- three.js mounts here -->
    <div
      id="modelViewerCanvas"
      class="model-viewer-canvas"
      role="img"
      aria-label="Interactive 3D model — drag to rotate, scroll to zoom"
    ></div>

    <p class="model-viewer-hint" aria-hidden="true">Drag to rotate · Scroll to zoom</p>

    <div class="model-viewer-footer">
      <a
        class="settings-btn"
        id="modelViewerDownload"
        href="#"
        download
        aria-label="Download GLB file"
      >↓ Download GLB</a>
    </div>

  </div>
</div>
```

### 8c. Modal CSS

```css
/* ── Model viewer modal ── */
.model-viewer-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.model-viewer-modal.hidden { display: none; }

.model-viewer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(44,36,22,.72);
  backdrop-filter: blur(2px);
}

.model-viewer-content {
  position: relative;
  z-index: 1;
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 16px 48px rgba(44,36,22,.30);
  width: 100%;
  max-width: 760px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.model-viewer-header {
  display: flex;
  align-items: center;
  padding: .85rem 1.25rem;
  border-bottom: 2px solid var(--border);
  flex-shrink: 0;
}
.model-viewer-title {
  flex: 1;
  font-size: 1rem;
  font-weight: 800;
  color: var(--ink);
}
.model-viewer-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--muted);
  padding: .25rem .5rem;
  border-radius: 6px;
  min-width: 36px;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color .15s, background .15s;
}
.model-viewer-close:hover { color: var(--terracotta); background: rgba(196,81,58,.08); }

.model-viewer-canvas {
  flex: 1;
  min-height: 340px;
  background: var(--paper-dark);
  position: relative;
  overflow: hidden;
}

.model-viewer-hint {
  text-align: center;
  font-size: .72rem;
  color: var(--muted);
  padding: .35rem 0;
  flex-shrink: 0;
  border-top: 1px solid var(--border);
}

.model-viewer-footer {
  padding: .75rem 1.25rem;
  border-top: 2px solid var(--border);
  flex-shrink: 0;
}

@media (max-width: 600px) {
  .model-viewer-content {
    max-height: 95vh;
    border-radius: calc(var(--radius) / 2);
  }
  .model-viewer-canvas { min-height: 260px; }
}
```

### 8d. Modal three.js notes

- Use the same CDN importmap as `figure_maker.html`. `gallery.html` must add the importmap to `<head>` and change `<script src="gallery.js">` to `<script type="module" src="gallery.js">`.
- On open: instantiate `WebGLRenderer`, `PerspectiveCamera`, `OrbitControls`, load the GLB. On close: call `renderer.dispose()`, remove the `<canvas>`, null the renderer — same teardown pattern as figure_maker spec section 7f.
- Focus management: on open, move focus to `#modelViewerClose`. On close, return focus to the "View 3D" button that triggered the open. Trap focus within the modal while open (cycle between close button and download button).
- Close triggers: click `#modelViewerClose`, click `#modelViewerBackdrop`, press Escape.
- `aria-modal="true"` tells screen readers to ignore content behind the dialog.

---

## 9. Backend contracts

```
GET /gallery/images
Response: [
  {
    "filename": "abc123.png",
    "prompt": "A brave young monkey king…",
    "created_at": "2026-06-10T14:32:00Z"
  },
  …
]

GET /gallery/models
Response: [
  {
    "job_id": "job_abc123",
    "prompt": "A friendly robot",
    "thumbnail_url": "https://…/preview.png",  /* nullable */
    "glb_url": "/output/model_abc123.glb",
    "stl_url": "/output/model_abc123.stl",     /* nullable */
    "filament": "PLA",                          /* nullable */
    "created_at": "2026-06-12T09:15:00Z"
  },
  …
]

DELETE /gallery/images/{filename}
DELETE /gallery/models/{job_id}

/* Existing — unchanged */
GET /gallery          → { books: [ … ] }
GET /gallery/{id}     → full book JSON
DELETE /gallery/{id}
```

All lists are newest-first. The developer should confirm these endpoints exist or note which ones need to be added to `main.py`.

---

## 10. JS architecture changes

The existing `gallery.js` loads all books on init. The new architecture:

- On page load: activate the default tab (images, or the value of `?tab=` query param), load that panel's data. Lazy-load the other panels only when their tabs are first activated.
- Track per-panel load state (`loaded: false` initially) so switching to an already-loaded panel does not re-fetch.
- The `#refreshBtn` re-fetches only the currently active panel.
- The `escHtml()` helper (currently defined inline in `gallery.js`) is needed for all three `buildCard` functions.
- Use the ARIA tabs keyboard pattern: arrow keys activate tabs; `Home`/`End` jump to first/last. Do not close the panel on arrow key; activate immediately.

---

## 11. `gallery.html` head changes required

```html
<!-- Add importmap BEFORE other scripts, for three.js modal viewer -->
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
  }
}
</script>
```

```html
<!-- Change from plain script to module -->
<script type="module" src="gallery.js"></script>
```

`storybook_print.js` is a plain (non-module) script. If it is needed inside an ES module `gallery.js`, import it via a dynamic `import()` or expose its functions on `window` (the existing approach — `openPrintWindow` is used via `window.openPrintWindow` implicitly). Confirm this still works after converting `gallery.js` to a module; if not, the developer should either keep `storybook_print.js` as a non-module include before `gallery.js`, or convert it too.
