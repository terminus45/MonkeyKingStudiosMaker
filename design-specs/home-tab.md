# Home Page — Design Spec

**Scope:** New `home.html` landing page for BookBuilderBot. This page becomes the default route (`GET /`) and replaces the current redirect to `book_builder.html`.
**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`

---

## Overview

Home is a single-purpose welcome screen. It contains the standard site header, a large animated robot mascot, a headline, and one text input bound to the `character` field of the shared inputs store. There is no generation action on this page — its job is to greet the user, prime the most important shared field, and let them navigate to a tool.

Visual result: a centered hero on a dark `var(--paper)` (#0a0b1a) background. The 🤖 emoji bounces gently in a constrained container above the headline "What will you build today?" Below the headline is a single rounded textarea. The overall feel is calm, spacious, and kid-appropriate — matching the dark-space aesthetic of the existing pages without their tool-specific density.

---

## 1. Page Layout

### Document structure

```
<html lang="en">
  <head>
    … (identical head block to siblings — see Section 7)
  </head>
  <body>
    <a href="#homeMain" class="skip-link">Skip to main content</a>
    <header>…</header>              ← identical header pattern (see Section 5)
    <main class="home-main" id="homeMain">
      <div class="home-hero">
        <div class="home-robot-container" aria-hidden="true">
          <span class="home-robot">🤖</span>
        </div>
        <h1 class="home-headline">What will you build today?</h1>
        <div class="home-input-wrap">
          <label for="homeDescInput" class="home-input-label">
            Character Description
          </label>
          <textarea
            id="homeDescInput"
            class="home-desc-input"
            rows="3"
            placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
            aria-describedby="homeDescHint"
          ></textarea>
          <p class="hint" id="homeDescHint">
            Describe your hero — this travels with you to every tool.
          </p>
        </div>
      </div>
    </main>
    <script src="shared_inputs.js"></script>
    <script src="home.js"></script>
  </body>
</html>
```

### Vertical rhythm

The hero block is vertically centered in the available viewport height (between header bottom and page bottom), using flexbox on `home-main`. On very short viewports (e.g. landscape phone), centering falls back to top-aligned with top padding so content never overflows.

```
home-main
  flex: 1
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  padding: 2rem 1rem 4rem   ← generous bottom padding for short-viewport safety
  gap: 0                     ← inner gap controlled by home-hero children

home-hero
  display: flex
  flex-direction: column
  align-items: center
  gap: 1.5rem
  max-width: 560px
  width: 100%
```

The `max-width: 560px` on `home-hero` keeps the input from stretching to full container width on large screens, giving it a focused, card-like feel without adding an actual card background. This is intentionally lighter than the `.builder-step` card treatment used on the other pages — Home is a landing screen, not a workflow step.

### Responsive behavior

At `max-width: 700px` (matching the breakpoint used across sibling pages — this home-specific `@media` block lives in `home.css`, not in the shared `style.css`):
- `home-hero` padding narrows: `padding: 1.5rem .5rem 3rem`
- Robot emoji size reduces from `4.5rem` to `3.5rem`
- Headline reduces from `1.75rem` to `1.35rem`
- No structural change — still single-column flex

---

## 2. The Bouncing Robot

### Container and emoji sizing

```css
.home-robot-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 6rem;
  height: 6rem;
}

.home-robot {
  font-size: 4.5rem;
  line-height: 1;
  display: block;
  animation: homeBounce 1.8s ease-in-out infinite;
  will-change: transform;
}
```

The container is fixed at `6rem × 6rem` so the bounce animation does not shift surrounding content. The emoji itself is `4.5rem` — large enough to read as a mascot rather than an icon, but not so large it dominates small screens. The `will-change: transform` hint allows the browser to compositor-thread the animation without layout recalculation on each frame.

### Keyframes

```css
@keyframes homeBounce {
  0%, 100% {
    transform: translateY(0);
    animation-timing-function: ease-in;
  }
  45% {
    transform: translateY(-18px);
    animation-timing-function: ease-out;
  }
  55% {
    transform: translateY(-18px);
    animation-timing-function: ease-in;
  }
}
```

Rationale: a 45%–55% plateau at the top of the arc gives the bounce a slight "float" moment before it falls back, which reads as friendlier and less mechanical than a simple sine wave. The 1.8s period is slow enough to feel gentle and not distracting. `translateY(-18px)` is a modest 3px-per-rem lift at the base font size — visible but not jumpy.

### Reduced motion fallback

```css
@media (prefers-reduced-motion: reduce) {
  .home-robot {
    animation: none;
  }
}
```

When the system preference is set, the robot renders statically at its resting position. No fallback animation (e.g. a slow pulse) is used — stillness is the correct experience for users who have requested reduced motion.

### Accessibility note

The robot container carries `aria-hidden="true"`. It is purely decorative; the headline "What will you build today?" provides all necessary context. Screen readers skip the emoji entirely.

---

## 3. Headline and Input

### Headline

```css
.home-headline {
  font-family: 'Nunito', system-ui, sans-serif;  /* already loaded via Google Fonts */
  font-size: 1.75rem;
  font-weight: 900;
  color: var(--ink);          /* #ffffff */
  text-align: center;
  line-height: 1.2;
  letter-spacing: -.01em;
}
```

This uses the same Nunito weight-900 used in `.step-num` badges and the site wordmark. The `1.75rem` size sits between the header title (`1.35rem`) and a hypothetical hero h1 — prominent without being oversized for a focused input page. No gradient, no text-shadow — consistent with the flat dark aesthetic.

### Input label

```css
.home-input-label {
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);        /* rgba(255,255,255,.50) */
  display: block;
  margin-bottom: .25rem;
  text-align: left;
}
```

Matches `.control-group label` in `style.css` exactly — same font size, weight, transform, and color. No deviation from the existing design system.

### Textarea

The input uses the existing `style.css` textarea styles directly — no new rules needed:

```css
/* Already in style.css — textarea base */
background: var(--ctrl-bg);         /* #0f1129 */
border: 1px solid var(--border);    /* rgba(255,255,255,.10) */
border-radius: 12px;
padding: .5rem .7rem;
font-size: .9rem;
font-family: 'Nunito', system-ui, sans-serif;
color: var(--ink);
resize: vertical;
width: 100%;
transition: border-color .2s, box-shadow .2s;
```

Focus state (also already defined):
```css
border-color: #ff6b35;
box-shadow: 0 0 0 2px rgba(255,107,53,.35);
```

Add one home-specific rule to give the input slightly more presence than the default:

```css
.home-desc-input {
  font-size: 1rem;    /* slightly larger than the .9rem base — easier to read at landing */
  min-height: 4.5rem;
}
```

All other styling inherits from the `style.css` textarea rule. Do not introduce any new border color, background, or shape.

### Input field id and placeholder

- `id="homeDescInput"` — passed to `bindFields` (see Section 4)
- `placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"` — the canonical Character Description placeholder from `unified-inputs-header.md`

### Hint paragraph

```html
<p class="hint" id="homeDescHint">
  Describe your hero — this travels with you to every tool.
</p>
```

Uses the existing `.hint` class from `style.css` (`.72rem`, `var(--muted)`). The copy reinforces cross-tab persistence in kid-friendly language.

### input-wrap sizing

```css
.home-input-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: .4rem;          /* matches .control-group gap */
}
```

---

## 4. SharedInputs Wiring

### The bindFields call

`home.js` must call `SharedInputs.bindFields` inside an init function that runs after DOM ready — not at bare top-level. Scripts are loaded at the **end of `<body>`** (after `#homeDescInput` exists in the DOM), matching `character_generator.html` where both `shared_inputs.js` and the page script appear immediately before `</body>`. Do NOT place either script tag in `<head>`.

The recommended init structure mirrors `character_generator.js`, which wraps `bindFields` inside a named helper (`wireSharedInputListeners`) called from an async IIFE:

```js
// home.js
'use strict';

const API = '';   // same-origin

const statusDot   = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');

// ── Shared inputs ────────────────────────────────────────────────────────────
function wireSharedInputListeners() {
  SharedInputs.bindFields(
    { character: 'homeDescInput' },
    { debounce: 300 }
  );
}

// ── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() { /* see Section 8 */ }

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  wireSharedInputListeners();
})();

setInterval(checkHealth, 30_000);
```

- `character` is the only field bound on Home (no `story`, no `style`).
- `populate: true` is the default — the stored `character` value will be written into `#homeDescInput` on page load immediately.
- `debounce: 300` matches Character Generator and Figure Maker (the two other pages that are not Book Builder).
- Only the `character` key is passed in the map. `bindFields` skips any field whose id is absent from the map, so `story` and `style` are not affected by Home's listener registration.

### Cross-tab behavior the user observes

1. User arrives at Home with an empty store: `#homeDescInput` is blank.
2. User types "A curious dragon with purple scales" in `#homeDescInput`: after 300 ms, `SharedInputs.patch({ character: '…' })` writes to `localStorage['monkeyking_shared_inputs']`.
3. User opens Character Generator in another tab: on load, `bindFields({ character: 'cgDescInput', … }, { populate: true })` restores the stored value into `#cgDescInput`. The field is already filled.
4. User edits `#cgDescInput` in that tab: 300 ms later the store updates. The Home tab receives the `storage` event and `onExternalChange` fires, writing the new value into `#homeDescInput` directly (no synthetic input event — no echo back to the store).
5. No other shared field (`story`, `style`) is touched by Home. Their stored values are preserved through any visit to Home.

### Script load order

`shared_inputs.js` must be loaded as a plain (non-module) script BEFORE `home.js`, and both must be placed at the **end of `<body>`** — NOT in `<head>`. Placing them at end-of-body is the pattern used by all sibling pages (`character_generator.html` has both scripts as the last two lines before `</body>`). This guarantees that `#homeDescInput` and the status elements already exist in the DOM when the scripts execute, without needing a `DOMContentLoaded` listener.

```html
    <script src="shared_inputs.js"></script>
    <script src="home.js"></script>
  </body>
</html>
```

`home.js` is a plain script (not an ES module) — there is no three.js or import-map dependency on this page.

---

## 5. Nav Changes

### New nav link markup

Add a Home link as the **first child** of `.header-nav` on every page:

```html
<a href="home.html" class="nav-link">🏠 Home</a>
```

On `home.html` only, add the `active` class:

```html
<a href="home.html" class="nav-link active">🏠 Home</a>
```

### Complete nav block (canonical, for home.html)

```html
<nav class="header-nav" aria-label="Main navigation">
  <a href="home.html"                class="nav-link active">🏠 Home</a>
  <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
  <a href="book_builder.html"        class="nav-link">📖 Book Builder</a>
  <a href="figure_maker.html"        class="nav-link">🧩 Figure Maker</a>
  <a href="gallery.html"             class="nav-link">🖼 Gallery</a>
</nav>
```

Settings does not appear in `header-nav` — it is accessed only via the gear icon, which is the existing pattern and must not change.

### Files requiring nav propagation

The Home link (`<a href="home.html" class="nav-link">🏠 Home</a>`, without `active`) must be prepended to the `<nav class="header-nav">` block in every sibling page:

| File | Current first nav link | Action |
|---|---|---|
| `frontend/book_builder.html` | `🎭 Character Generator` | Prepend Home link (no `active`) |
| `frontend/character_generator.html` | `🎭 Character Generator` (active) | Prepend Home link (no `active`) |
| `frontend/figure_maker.html` | `🎭 Character Generator` | Prepend Home link (no `active`) |
| `frontend/gallery.html` | `🎭 Character Generator` | Prepend Home link (no `active`) |
| `frontend/settings.html` | `🎭 Character Generator` | Prepend Home link (no `active`) |

Settings already uses the gear icon `active` pattern for its own "active" indication; it does not mark any nav link active. No change to that pattern.

### Active state styling

`.nav-link.active` is already defined in `style.css`:
```css
.nav-link.active { background: var(--mustard); color: #0a0b1a; }
```
No new CSS needed for the active state.

### No settings.html nav change for Home's active state

Settings marks no nav link active (it marks the gear icon with class `active` instead). This asymmetry is pre-existing and correct — leave it unchanged.

---

## 6. Landing-Page Change

In `main.py`, the `GET /` route currently redirects to `book_builder.html`. Change the redirect target to `home.html`:

```python
# main.py — before
@app.get("/")
def root():
    return RedirectResponse(url="/book_builder.html")

# main.py — after
@app.get("/")
def root():
    return RedirectResponse(url="/home.html")
```

Note: the handler is and must remain synchronous (`def`, not `async def`). Only the redirect URL string changes.

This is the only backend change required by this feature. No new API endpoints, no new data models.

---

## 7. Head Block

`home.html` uses the identical `<head>` block pattern as all sibling pages:

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home · MonkeyKing</title>
  <meta name="color-scheme" content="dark">
  <meta name="theme-color" content="#0a0b1a">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="home.css">
</head>
```

Notes:
- `home.css` is a new file containing only the home-specific rules documented in this spec (`home-main`, `home-hero`, `home-robot-container`, `home-robot`, `home-headline`, `home-input-wrap`, `home-input-label`, `home-desc-input`, `@keyframes homeBounce`, and the `prefers-reduced-motion` override).
- No `importmap` block — `home.js` is a plain script with no three.js dependency.
- `Space Mono` is included in the font load because it is in the shared bundle and the `.hint` class may inherit it indirectly — consistent with all other pages.

---

## 8. Full Header Block (home.html)

The header is identical in structure to all siblings. The only differences from `character_generator.html` are: the page title, the skip-link anchor, and the nav active state.

```html
<a href="#homeMain" class="skip-link">Skip to main content</a>

<header>
  <div class="header-inner">
    <a href="settings.html" class="settings-gear" aria-label="Settings">
      <!-- identical gear SVG — copy from any sibling verbatim -->
    </a>
    <div class="header-title">
      <span class="title-zh">🤖</span>
      <span class="title-en">Monkey King Studios</span>
    </div>
    <nav class="header-nav" aria-label="Main navigation">
      <a href="home.html"                class="nav-link active">🏠 Home</a>
      <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
      <a href="book_builder.html"        class="nav-link">📖 Book Builder</a>
      <a href="figure_maker.html"        class="nav-link">🧩 Figure Maker</a>
      <a href="gallery.html"             class="nav-link">🖼 Gallery</a>
    </nav>
    <div class="server-status">
      <span class="status-dot" id="statusDot"></span>
      <span id="statusLabel">Connecting…</span>
    </div>
  </div>
</header>
```

The server-status block is included for consistency with siblings. `home.js` must implement a **simplified** `checkHealth()` — do NOT copy the function from `character_generator.js` verbatim.

The sibling version reads `data.loaded_model` from `/health`, but `/health` only returns `{"status":"ok"}` — there is no `loaded_model` field — so the model-name suffix is meaningless. On Home (which has no generation feature), the status label should show only "Connected" or "Server offline":

```js
async function checkHealth() {
  try {
    await fetch(`${API}/health`);
    statusDot.className = 'status-dot ok';
    statusLabel.textContent = 'Connected';
  } catch {
    statusDot.className = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}
```

Call `checkHealth()` on page load AND register `setInterval(checkHealth, 30_000)` for reconnect parity with siblings (matching the pattern in `character_generator.js` lines 403 and 413).

---

## 9. Accessibility

### Skip link

`<a href="#homeMain" class="skip-link">Skip to main content</a>` — uses the `.skip-link` class already defined in `style.css`. The `id="homeMain"` on `<main>` is the target. Pattern is identical to all sibling pages.

### Input labeling

`<label for="homeDescInput">` is an explicit `<label>` element with a `for` attribute pointing to the textarea `id`. The `aria-describedby="homeDescHint"` on the textarea links the hint paragraph as supplementary description. This matches the `control-group` pattern used throughout the app.

### Heading hierarchy

The page has one `<h1>` ("What will you build today?") — the correct hierarchy for a landing page. Other pages use `<h2>` inside `<main>` because they have step numbering or section headings below the header. Home has no sub-sections, so `<h1>` is correct here.

### Reduced motion

The `@media (prefers-reduced-motion: reduce)` rule disabling the bounce animation is required (see Section 2). The only animation on the page is the robot bounce, so this one rule covers the entire page.

### Color scheme and contrast

- `<meta name="color-scheme" content="dark">` — consistent with all siblings.
- All text uses `var(--ink)` (#ffffff) or `var(--muted)` (rgba(255,255,255,.50)) on `var(--paper)` (#0a0b1a). White on #0a0b1a exceeds WCAG AA for all text sizes. The `.hint` text at `.72rem` / `rgba(255,255,255,.50)` is borderline AA — this is the existing system-wide behavior, not introduced here.
- The `active` nav link uses `background: var(--mustard)` (#ff6b35) with `color: #0a0b1a`. #ff6b35 on #0a0b1a: contrast ratio ~3.5:1 (AA for large/bold text — the nav link is `.82rem font-weight: 700`, which qualifies as bold text under WCAG 2.1). This is the existing system-wide pattern for all active nav links.

### Keyboard navigation order

1. Skip link (visually hidden until focused)
2. Gear icon (Settings)
3. Header title (non-interactive)
4. Nav links: Home (focused/active) → Character Generator → Book Builder → Figure Maker → Gallery
5. `#homeDescInput` textarea
6. (End of interactive content)

The robot container is `aria-hidden="true"` and has no `tabindex`, so it is skipped by keyboard.

---

## 10. States

| State | Description |
|---|---|
| **Default / empty store** | `#homeDescInput` renders with placeholder text. Robot bounces. |
| **Store has a value** | On load, `bindFields` populates `#homeDescInput` with the stored `character` value. Textarea shows the text, no placeholder. |
| **Input focused** | Textarea border becomes `#ff6b35`, box-shadow `0 0 0 2px rgba(255,107,53,.35)`. Robot continues bouncing (unrelated). |
| **External update (another tab)** | `#homeDescInput` value updates silently. No flash, no focus change. |
| **Reduced motion** | Robot renders statically. All other states unchanged. |
| **Server offline** | Status dot shows red per existing pattern. No other change to the Home page — Home has no generation feature that depends on server availability. |

Home has no loading state, no error state, and no empty-result state — it is not a generation page.

---

## 11. CSS file summary

**Loading model:** every page loads `style.css` first, then exactly one per-page sheet. Home loads `style.css` + `home.css`.

- **`style.css`** (already exists, no changes needed) owns: shared design tokens (`--mustard`, `--teal`, `--paper`, `--ink`, `--muted`, `--ctrl-bg`, `--border`), base classes (`.skip-link`, `.hint`, `.nav-link`, `.nav-link.active`, `textarea` base, `.control-group label`).
- **`home.css`** (new file, `frontend/home.css`) owns all home-specific rules. Nothing in `style.css` or any sibling CSS file needs to change for this page.

```
home.css owns:
  .home-main              — flex centering container
  .home-hero              — centered column, max-width 560px
  .home-robot-container   — fixed 6rem×6rem box
  .home-robot             — 4.5rem emoji, animation applied
  .home-headline          — 1.75rem weight-900
  .home-input-wrap        — flex column, gap .4rem
  .home-input-label       — mirrors .control-group label
  .home-desc-input        — 1rem font-size override, min-height
  @keyframes homeBounce   — the bounce animation
  @media prefers-reduced-motion  — disables animation
  @media max-width:700px  — robot and headline size reductions
```

Flag to developer: `var(--mustard)` and `var(--teal)` both resolve to `#ff6b35` in the current token file (they are aliased to the same value). This is a pre-existing inconsistency in `style.css` — do not attempt to fix it in this PR. Use `var(--mustard)` for the active nav link state (matching the CSS already written for `.nav-link.active`) and make no reference to `var(--teal)` in `home.css`, since Home has no panel with a teal left-border accent.

---

## 12. Acceptance Criteria

1. **Landing page:** Navigating to `GET /` loads `home.html` (not `book_builder.html`). Verified by visiting the root URL in a browser and confirming the page title is "Home · MonkeyKing".

2. **Bounce animation:** On a default system (no reduced-motion preference), the 🤖 emoji bounces continuously with a visible up-and-float arc at `1.8s` period. The animation does not shift any surrounding layout.

3. **Reduced motion:** With `prefers-reduced-motion: reduce` set in the OS/browser, the robot is completely still. No animation of any kind plays.

4. **Character field sync — write from Home:** User types in `#homeDescInput` on Home. After 300 ms, `localStorage['monkeyking_shared_inputs']` contains the updated `character` value. Navigating to Character Generator shows the same value in `#cgDescInput`.

5. **Character field sync — read on Home:** User types in `#cgDescInput` on Character Generator. Switching to the Home tab (without reload) shows the updated value in `#homeDescInput` within 300 ms (storage event propagation).

6. **Character field sync — populate on load:** With a `character` value already stored, loading `home.html` from cold (new tab) populates `#homeDescInput` immediately on page load.

7. **No regression to `story`/`style` fields:** Editing `#homeDescInput` on Home updates only the `character` key in the store. The `story` and `style` keys are not touched. Verified by inspecting `localStorage['monkeyking_shared_inputs']` before and after.

8. **Nav present and active on Home:** The Home nav link renders with `class="nav-link active"` (orange pill background) on `home.html`. All other nav links are inactive.

9. **Nav present on all sibling pages:** All five existing pages (book_builder, character_generator, figure_maker, gallery, settings) show the 🏠 Home link as the first item in `header-nav`. On each sibling page, the Home link is NOT marked active.

10. **No regression to existing 3-field sync:** On Character Generator, Book Builder, and Figure Maker, all three fields (character, story, style) continue to sync correctly cross-tab, unaffected by the addition of the Home page.

11. **Accessibility:** `#homeDescInput` has a visible `<label for="homeDescInput">` and `aria-describedby="homeDescHint"`. The page has one `<h1>`. The skip link targets `#homeMain`. All verified by running an axe or similar audit on the rendered page.
