# Character Generator — Design Spec
# BookBuilderBot · New Page

Status: Ready for developer-agent implementation
New files: `frontend/character_generator.html`, `frontend/character_generator.css`, `frontend/character_generator.js`
Shared dependencies: `frontend/style.css` (MCM tokens), `frontend/book_builder.css` (no edits needed — `.builder-step`, `.gemini-options-row`, `.ar-btn` patterns are replicated)

---

## 1. Purpose

The Character Generator is a standalone page that lets the user generate portrait images of a storybook's main character via the Gemini image API, before starting the Book Builder. The workflow is: describe the character → pick a style → generate several looks → optionally carry the final image into the book. It is intentionally simpler than the Book Builder — one input, one result, a short session gallery strip.

---

## 2. Nav order change (all pages)

The `<nav class="header-nav">` in **every existing page** (`index.html`, `book_builder.html`, `gallery.html`) must be updated to add the new first link and reorder:

```html
<nav class="header-nav" aria-label="Main navigation">
  <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
  <a href="book_builder.html"        class="nav-link">📖 Book Builder</a>
  <a href="gallery.html"             class="nav-link">🖼 Gallery</a>
</nav>
```

- The `active` class is placed on the link matching the current page.
- Existing `.nav-link` styles from `style.css` apply unchanged (charcoal header, mustard active pill, paper-tint hover).
- Nav scrolls horizontally on mobile — no change needed to `.header-nav` CSS.

---

## 3. Page layout

### 3a. Shell structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Character Generator · MonkeyKing</title>
  <!-- same Google Fonts + style.css links as book_builder.html -->
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="character_generator.css">
</head>
<body>

  <header><!-- identical structure to book_builder.html; active on Character Generator --></header>

  <main class="cg-main" id="cgMain">

    <div class="cg-layout">

      <!-- LEFT: Controls panel -->
      <aside class="cg-controls-panel" aria-label="Character generation controls">
        <!-- section: character description -->
        <!-- section: style prompt + presets -->
        <!-- section: gemini model + aspect ratio -->
        <!-- generate button -->
      </aside>

      <!-- RIGHT: Result area -->
      <section class="cg-result-area" aria-label="Generated character portrait">
        <!-- image frame / empty state / error -->
        <!-- action row: download, use as cover -->
      </section>

    </div>

    <!-- BOTTOM: Session thumbnail strip -->
    <section class="cg-strip-section" id="cgStrip" aria-label="Recent generations this session">
      <!-- thumbnails injected by JS -->
    </section>

  </main>

  <script src="character_generator.js"></script>
</body>
</html>
```

### 3b. Layout behaviour

| Breakpoint | Layout |
|---|---|
| < 700 px (mobile) | Single column. Controls panel stacks above result area. Strip below. |
| >= 700 px (wide) | Two columns: controls left (fixed ~340 px), result right (flex 1). Strip below both columns at full width. |

The two-column split matches the visual balance of the Book Builder's `gen-controls` grid without being a three-column grid (controls are simpler here).

---

## 4. Controls panel

The panel is a `.builder-step`-style card with a mustard left border (consistent with the "input" accent color used on Book Builder step 2). It is always visible — it is not a wizard step, so no `.hidden` / step sequencing needed.

### 4a. Panel card skeleton

```html
<aside class="cg-controls-panel">
  <div class="builder-step" id="cgControlCard" style="border-left: 5px solid var(--mustard)">

    <div class="step-header">
      <!-- no step-num badge — this is a single card, not a wizard -->
      <h2>Character Details</h2>
    </div>

    <!-- CHARACTER DESCRIPTION -->
    <div class="control-group" id="cgDescGroup">
      <label for="cgDescInput">Character Description</label>
      <textarea
        id="cgDescInput"
        rows="4"
        placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
        aria-describedby="cgDescHint"
        required
      ></textarea>
      <p class="hint" id="cgDescHint">
        Describe your hero's appearance, personality, and any key props.
      </p>
    </div>

    <!-- STYLE PROMPT -->
    <div class="control-group" id="cgStyleGroup" style="margin-top: .9rem">
      <label for="cgStyleInput">
        Style Prompt <span class="hint">(optional — applied to the portrait)</span>
      </label>
      <textarea
        id="cgStyleInput"
        rows="2"
        placeholder="e.g. Vibrant watercolor, children's book art, warm tones…"
      ></textarea>
      <div class="presets" id="cgStylePresets" role="group" aria-label="Style presets" style="margin-top: .4rem">
        <button class="preset" data-suffix="Black and white ink line art, manga linework, chibi storybook illustration, white background, no color">Ink &amp; Manga</button>
        <button class="preset" data-suffix="Traditional Chinese ink painting, brush strokes, Sumi-e style, monochrome">Sumi-e</button>
        <button class="preset" data-suffix="Vibrant cinematic illustration, detailed painterly, storybook art, rich colors">Cinematic</button>
        <button class="preset" data-suffix="Soft watercolor illustration, children's book art, delicate washes, pastel tones">Watercolor</button>
        <button class="preset" data-suffix="">Clear</button>
      </div>
    </div>

    <!-- GEMINI OPTIONS ROW -->
    <div class="control-group" id="cgGeminiGroup" style="margin-top: .9rem">
      <div class="gemini-options-row">

        <div class="gemini-opt">
          <label for="cgModelSelect">Model</label>
          <select id="cgModelSelect" aria-label="Gemini model">
            <!-- populated at runtime from GET /gemini/models -->
            <option value="imagen-4.0-generate-001">Imagen 4</option>
            <option value="imagen-4.0-fast-generate-001">Imagen 4 Fast</option>
            <option value="imagen-4.0-ultra-generate-001">Imagen 4 Ultra</option>
            <option value="gemini-2.5-flash-image">Gemini 2.5 Flash</option>
          </select>
        </div>

        <div class="gemini-opt">
          <label>Aspect Ratio</label>
          <div class="presets" id="cgAspectPresets" role="group" aria-label="Aspect ratio">
            <button class="preset ar-btn" data-ar="1:1">1:1</button>
            <button class="preset ar-btn active" data-ar="3:4">3:4</button>
            <button class="preset ar-btn" data-ar="4:3">4:3</button>
            <button class="preset ar-btn" data-ar="9:16">9:16</button>
            <button class="preset ar-btn" data-ar="16:9">16:9</button>
          </div>
        </div>

      </div>
    </div>

    <!-- GENERATE BUTTON -->
    <button
      class="generate-btn"
      id="cgGenerateBtn"
      style="width: 100%; margin-top: 1.25rem"
      aria-live="polite"
    >
      <span id="cgGenerateLabel">🎭 Generate Character</span>
      <div class="spinner hidden" id="cgSpinner" aria-hidden="true"></div>
    </button>

    <!-- INLINE ERROR (controls panel) -->
    <p class="cg-error hidden" id="cgErrorMsg" role="alert" aria-live="assertive"></p>

  </div>
</aside>
```

**Aspect ratio default:** `3:4` is pre-selected (`.active`) because portrait orientation is the natural fit for a character portrait. This differs from the Book Builder default of `1:1`.

**Model select:** populated at runtime from `GET /gemini/models`. On load, default to `imagen-4.0-generate-001` (Imagen 4). If the endpoint fails, show the hardcoded option list as fallback (matching the pattern in `book_builder.html`).

---

## 5. Result area

### 5a. Frame structure

```html
<section class="cg-result-area">

  <!-- IMAGE FRAME -->
  <div class="cg-image-frame" id="cgImageFrame" aria-live="polite">

    <!-- EMPTY STATE (default) -->
    <div class="cg-empty-state" id="cgEmptyState" aria-hidden="false">
      <span class="cg-empty-icon" aria-hidden="true">🎭</span>
      <p>Your character portrait will appear here.</p>
      <p class="hint">Describe your hero and hit Generate.</p>
    </div>

    <!-- LOADING STATE (hidden until generating) -->
    <div class="cg-loading-state hidden" id="cgLoadingState" aria-hidden="true" aria-label="Generating portrait…">
      <div class="spinner cg-big-spinner" aria-hidden="true"></div>
      <p>Generating your character…</p>
    </div>

    <!-- SUCCESS STATE (hidden until image ready) -->
    <img
      class="cg-portrait hidden"
      id="cgPortraitImg"
      src=""
      alt=""
      aria-hidden="true"
    >

  </div>

  <!-- ACTION ROW (hidden until image ready) -->
  <div class="cg-action-row hidden" id="cgActionRow">
    <a
      class="settings-btn"
      id="cgDownloadBtn"
      href="#"
      download="character-portrait.png"
      aria-label="Download portrait image"
    >↓ Download</a>

    <button
      class="settings-btn"
      id="cgUseAsCoverBtn"
      aria-label="Copy filename to clipboard for use as book cover"
    >📖 Use as Book Cover</button>
  </div>

</section>
```

**Alt text strategy:** when an image is generated, JS sets `alt` to the character description text truncated to ~120 characters, e.g. `"Character portrait: A brave young monkey king with golden fur…"`. This provides meaningful alt text without the user having to type it separately.

**"Use as Book Cover":** Copies the image filename to `sessionStorage` under the key `cg_cover_filename`. The Book Builder can read this on load and pre-populate the cover image slot. This is a low-friction affordance — the developer can decide whether to implement the receiving side now or as a follow-up. If not implemented yet, the button shows a tooltip "Copied! Open Book Builder to use." using a `.hint-text` element.

---

## 6. Session gallery strip

Recommendation: **include it.** It adds high value — the user will often generate 3–5 looks for the same character before choosing one. The strip is a horizontal scrolling row of thumbnails, generated purely in-memory (not persisted to the server gallery). It disappears on page reload.

```html
<section class="cg-strip-section hidden" id="cgStrip" aria-label="Generated portraits this session">
  <div class="cg-strip-header">
    <h3>This Session</h3>
    <button class="settings-btn" id="cgClearStripBtn" aria-label="Clear session history">✕ Clear</button>
  </div>
  <div class="cg-strip-scroll" id="cgStripScroll" role="list">
    <!-- .cg-strip-thumb elements injected by JS -->
  </div>
</section>
```

Each thumbnail item (injected by JS):

```html
<button class="cg-strip-thumb" role="listitem" aria-label="Portrait [N]: [truncated description]" data-filename="…">
  <img src="/image/[filename]" alt="" aria-hidden="true">
</button>
```

Clicking a `.cg-strip-thumb` re-displays that image in the main result frame (sets `#cgPortraitImg` src, shows action row, hides empty/loading states).

The strip section is hidden until at least one image is generated (`id="cgStrip"` removes `.hidden` class on first success).

---

## 7. States

| State | Elements visible | Button state | Notes |
|---|---|---|---|
| **Empty** | `#cgEmptyState` | Enabled | Default on page load |
| **Generating** | `#cgLoadingState`, button with spinner | Disabled + `aria-disabled="true"` | Empty state hidden, image hidden, action row hidden |
| **Success** | `#cgPortraitImg`, `#cgActionRow` | Re-enabled | Empty + loading states hidden; thumbnail added to strip |
| **Error** | `#cgErrorMsg` (below generate button) | Re-enabled | Image frame returns to empty state; error message shown in terracotta |

**Error display:** The `.cg-error` element lives inside the controls card, immediately below the generate button. It uses terracotta color (matching `.card-error` and the MCM spec's error token). Text is set by JS. After a new generate attempt begins, the error is hidden again.

```css
.cg-error {
  margin-top: .6rem;
  font-size: .82rem;
  color: var(--terracotta);
  background: rgba(196,81,58,.07);
  border: 1px solid rgba(196,81,58,.28);
  border-radius: 10px;
  padding: .45rem .65rem;
  line-height: 1.45;
}
.cg-error.hidden { display: none; }
```

---

## 8. CSS additions (`character_generator.css`)

This file extends `style.css` tokens. It does not override any shared component class — all shared classes (`.builder-step`, `.control-group`, `.generate-btn`, `.preset`, `.ar-btn`, `.spinner`, `.gemini-options-row`, `.gemini-opt`, `.settings-btn`, `.hint`) are used as-is.

```css
/* ── Page layout ── */

.cg-main {
  flex: 1;
  max-width: 1200px;       /* matches .builder-main max-width */
  margin: 0 auto;
  width: 100%;
  padding: 1.5rem 1rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.cg-layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 1.5rem;
  align-items: start;
}

/* ── Controls panel ── */

.cg-controls-panel {
  /* Sticky so controls stay in view while result scrolls on tall viewports */
  position: sticky;
  top: 4rem;               /* clears header (~56px) */
}

/* ── Result area ── */

.cg-result-area {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cg-image-frame {
  background: #faf7f2;     /* matches .builder-step card bg */
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}

/* Empty state */
.cg-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .5rem;
  color: var(--muted);
  text-align: center;
  padding: 2rem;
}
.cg-empty-icon {
  font-size: 3.5rem;
  line-height: 1;
  opacity: .35;
}

/* Loading state */
.cg-loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: var(--muted);
}
.cg-big-spinner {
  width: 40px;
  height: 40px;
  border-width: 3px;
  /* Uses .spinner keyframes from style.css */
  border-color: rgba(44,36,22,.15);
  border-top-color: var(--mustard);
}

/* Portrait image */
.cg-portrait {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  border-radius: calc(var(--radius) - 2px);
}

/* Action row */
.cg-action-row {
  display: flex;
  gap: .5rem;
  flex-wrap: wrap;
}

/* ── Session strip ── */

.cg-strip-section {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border-left: 5px solid var(--teal);  /* teal accent — generation output color */
  padding: 1rem 1.25rem;
}
.cg-strip-section.hidden { display: none; }

.cg-strip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: .75rem;
}
.cg-strip-header h3 {
  font-size: .9rem;
  font-weight: 800;
  color: var(--ink);
}

.cg-strip-scroll {
  display: flex;
  gap: .65rem;
  overflow-x: auto;
  padding-bottom: .35rem;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.cg-strip-scroll::-webkit-scrollbar { height: 5px; }
.cg-strip-scroll::-webkit-scrollbar-track { background: transparent; }
.cg-strip-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

.cg-strip-thumb {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  border: 2px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  background: var(--paper-dark);
  padding: 0;
  transition: border-color .15s, box-shadow .15s, transform .12s;
}
.cg-strip-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cg-strip-thumb:hover {
  border-color: var(--mustard);
  box-shadow: 0 3px 10px rgba(232,160,32,.22);
  transform: translateY(-2px);
}
.cg-strip-thumb.active {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(58,125,122,.20);
}
.cg-strip-thumb:focus-visible {
  outline: 3px solid var(--teal);
  outline-offset: 2px;
}

/* ── Responsive ── */

@media (max-width: 700px) {
  .cg-layout {
    grid-template-columns: 1fr;
  }
  .cg-controls-panel {
    position: static;     /* unstick on mobile — scroll naturally */
  }
  .cg-image-frame {
    min-height: 280px;
  }
  .cg-main {
    padding: 1rem .75rem 3rem;
    gap: 1.5rem;
  }
}
```

---

## 9. JavaScript responsibilities (`character_generator.js`)

The developer should implement the following behaviours. This is a behaviour spec, not code.

**On load:**
- Fetch `GET /gemini/models` and populate `#cgModelSelect`. Default selection: first item with `type === "imagen"` or fall back to index 0. On fetch failure, leave the hardcoded options in place.
- Check `sessionStorage` for any prior session strip data and restore thumbnails (optional — only if the developer considers it low-cost).

**On `#cgStylePresets` preset click:**
- Toggle `.active` on clicked `.preset`. The "Clear" preset deactivates all others and clears `#cgStyleInput`. Other presets set `#cgStyleInput` to their `data-suffix` value.

**On `#cgAspectPresets` ar-btn click:**
- Toggle `.active` — only one active at a time (radio behaviour matching book_builder pattern).

**On `#cgGenerateBtn` click:**
- Validate: `#cgDescInput` must not be empty. If empty, focus the field and show a brief shake or border highlight (use `border-color: var(--terracotta)` on the textarea for 1.5 s, then restore).
- Set button to loading state: disable, hide label span, show spinner, update `aria-label="Generating…"`.
- Hide `#cgErrorMsg`, hide `#cgPortraitImg`, hide `#cgActionRow`, hide empty state, show `#cgLoadingState`.
- POST `/generate` with `{ prompt: cgDescInput.value, style_prompt: cgStyleInput.value, provider: "gemini", gemini_model: cgModelSelect.value, gemini_aspect_ratio: active ar-btn data-ar }`.
- On success (`{ filename, seed }`):
  - Set `#cgPortraitImg` src to `/image/{filename}`, set alt to `"Character portrait: " + description.slice(0, 120)`.
  - Hide loading state, show `#cgPortraitImg`, show `#cgActionRow`.
  - Set `#cgDownloadBtn` href to `/image/{filename}`.
  - Set `#cgUseAsCoverBtn` data attribute `data-filename="{filename}"`.
  - Add thumbnail to `#cgStripScroll`, show `#cgStrip` if hidden, mark new thumb `.active`.
  - Re-enable generate button, restore label.
- On error:
  - Hide loading state, show empty state, show `#cgErrorMsg` with error text.
  - Re-enable generate button.

**On `#cgUseAsCoverBtn` click:**
- Write `{ filename, description }` to `sessionStorage` key `cg_cover_filename`.
- Change button text briefly to "Copied! Open Book Builder." and disable for 2 s, then restore.

**On `.cg-strip-thumb` click:**
- Set `#cgPortraitImg` src to clicked thumb's `/image/{filename}`.
- Show image, show action row, update download href.
- Mark clicked thumb `.active`, remove from others.

---

## 10. Accessibility notes

- `<main class="cg-main">` has `id="cgMain"` for skip-link target (add `<a href="#cgMain" class="skip-link">Skip to main content</a>` in the `<body>` before the header — this is missing from the existing pages too; flag it).
- All form fields have associated `<label for="…">` elements. Do not use placeholder-only labels.
- `#cgGenerateBtn` uses `aria-live="polite"` on the button itself so the spinner swap is announced. Alternatively, pair it with a visually hidden status region — either approach is acceptable.
- `#cgErrorMsg` uses `role="alert"` and `aria-live="assertive"` for immediate announcement on error.
- `#cgLoadingState` uses `aria-label="Generating portrait…"` and is shown/hidden via `.hidden` class (which uses `display: none !important` from `style.css`) — screen readers will not read hidden content.
- Style preset buttons and aspect ratio buttons: the `role="group"` + `aria-label` on the `.presets` wrapper gives context. Individual `.preset` buttons need no additional ARIA since they are `<button>` elements with visible text labels.
- `.cg-strip-thumb` buttons need descriptive `aria-label` set by JS, e.g. `"Portrait 1: A brave young monkey king…"`.
- Contrast: all color usage follows the MCM spec ratios from `design-specs/mcm-redesign.md` section 13. No new colors are introduced — only the existing MCM tokens are used.
- Keyboard: tab order is natural (controls panel top-to-bottom, then result area, then strip). The sticky panel on wide screens does not disrupt tab order since it is DOM-order first. The strip thumbnails are keyboard-focusable buttons with `:focus-visible` ring.

---

## 11. Consistency flags (no action required — for developer awareness)

- The existing pages do not have a `<a href="#main" class="skip-link">` element. This is an existing gap, not introduced by this page. Adding it to `character_generator.html` is good; retroactively adding to the other pages is optional but recommended.
- `book_builder.html` has a duplicate `id="stylePresets"` (once in step 1, once in step 3) — this is a pre-existing bug, not introduced here. The Character Generator avoids it by using `id="cgStylePresets"` and `id="cgAspectPresets"`.
- The `ar-btn` class is used in `book_builder.html` but is not defined in any CSS file (it works because `.preset` already provides all the styling). The Character Generator uses it the same way — no new CSS needed, but the developer should be aware that `.ar-btn` is purely a JS selector hook.
