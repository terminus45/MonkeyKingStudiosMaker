# Viewer Fullscreen / Maximize Toggle — Design Spec

**Scope:** Figure Maker inline viewer (`#fmViewerFrame`) and Gallery 3D model modal viewer (`#modelViewerCanvas`).  
**Status:** Ready for architect review.  
**Author:** design-agent  
**Date:** 2026-06-21

---

## 1. Problem Statement

The 3D model viewer in both locations is constrained in height:

- **Figure Maker** — inline panel, `height: clamp(460px, 60svh, 600px)`, 50 px side gutters. Intricate models are hard to inspect at this size.
- **Gallery** — already a modal overlay (`max-width: 760px`, `max-height: 90vh`). The canvas itself is further limited by the header and footer chrome. Users cannot fill the screen with the model.

A fullscreen toggle lets users examine the model in detail without changing the page architecture.

---

## 2. Scope Boundaries

| Question | Decision |
|---|---|
| What enters fullscreen? | The **canvas container element** only (the `#fmViewer` / `#modelViewerCanvas` div plus the overlaid exit button and hint pill). NOT the whole page or modal. |
| Does the Gallery modal also enter fullscreen, or just the canvas inside it? | The **canvas fills the viewport** via a CSS overlay approach or the Fullscreen API — the modal chrome (header, footer) is hidden in fullscreen. The architect-agent will choose the mechanism. |
| Is fullscreen available during loading/error states? | No. The button is hidden until a model is confirmed loaded (GLB parse success). |
| Does Escape dismiss fullscreen, close the modal, or both? | Fullscreen is dismissed first; Escape on the (now normal-sized) modal then closes the modal. See §7. |

---

## 3. The Toggle Button

### 3.1 Glyph and Label

| State | Glyph | `aria-label` |
|---|---|---|
| Enter fullscreen | `⛶` | "Enter fullscreen" |
| Exit fullscreen | `⛶` with an inset rotation (or a distinct glyph `⤡`) | "Exit fullscreen" |

**Recommendation:** use a single glyph `⛶` in both states; swap only the `aria-label` and a CSS modifier class (`.is-fullscreen`) that applies a subtle visual treatment (e.g. rotated or filled variant). The glyph itself is universally understood and matches the playful-but-readable tone. If `⛶` renders poorly on a target device, fall back to a simple `[ ]` (enter) / `[×]` (exit) text pair — but do not introduce a custom SVG icon that isn't already in the codebase.

**Explicitly avoid** using ✕ for this button — that glyph is already the Gallery modal close button and the two must remain visually distinct.

### 3.2 Placement

**Both viewers: top-right corner of the canvas container, as an absolutely-positioned overlay button.**

This is consistent across both contexts because:
- The top-right corner is the established "dismiss/control" corner in the Gallery modal (the close button `✕` is top-right of the modal chrome, not the canvas). By placing fullscreen in the top-right of the canvas itself, it is within reach but does not compete with the modal's close button.
- The bottom of the canvas already contains the "Drag to rotate · Scroll to zoom" hint pill. The top-right corner is clear.

Exact position:
```
top: .6rem
right: .6rem
z-index: 4   /* above the canvas (z-index: auto), below fmViewerError (z-index: 3 → raise error to 5) */
```

Note: `fmViewerError` currently sits at `z-index: 3`. The fullscreen button at `z-index: 4` would be above it. Raise `fmViewerError` to `z-index: 5` so the error overlay still covers the button. The button is hidden during error state anyway (see §6), so this is belt-and-suspenders.

### 3.3 Visual Design

The button follows the existing `.model-viewer-close` pattern from `gallery.css` (not `.settings-btn`) because it is a canvas overlay control, not an in-flow row action.

```
Proposed class: .viewer-fullscreen-btn

background:   rgba(15, 17, 41, 0.72)   /* --paper-dark at 72% opacity */
border:       1px solid rgba(255,255,255,.15)
border-radius: 8px
padding:      .35rem .4rem
font-size:    1rem
color:        rgba(255,255,255,.70)
cursor:       pointer
min-width:    36px
min-height:   36px
display:      flex; align-items: center; justify-content: center;
transition:   color .15s, background .15s, border-color .15s
```

**Hover state:**
```
color:      #ffffff
background: rgba(15, 17, 41, 0.90)
border-color: rgba(255,255,255,.35)
```

**Focus-visible state (keyboard):**
```
outline: 2px solid #ff6b35    /* --mustard */
outline-offset: 2px
```

**In-fullscreen modifier** (when `.is-fullscreen` is on the button or ancestor):
```
background: rgba(255,255,255,.12)
border-color: rgba(255,255,255,.30)
```

This is a **new class** (`.viewer-fullscreen-btn`), not an extension of `.settings-btn`, because it is an overlay control that must work against the 3D canvas background. Flagging this: the `.settings-btn` family is sized for in-flow rows; it is inappropriate as an absolute overlay without modification.

### 3.4 Touch Target

Minimum tap target is 44 × 44 px. The `min-width: 36px / min-height: 36px` visual size is met; ensure the clickable area reaches 44 px by adding:
```
padding: .45rem .5rem    /* bumped on touch devices */
```
or a `::after` pseudo-element that extends the hit area without affecting layout. Prefer the padding approach for simplicity.

---

## 4. Placement in Each Viewer

### 4.1 Figure Maker (`#fmViewerFrame`)

The button sits inside `#fmViewerFrame` (`position: relative; overflow: hidden`), absolutely positioned at `top: .6rem; right: .6rem`.

DOM insertion point: directly inside `#fmViewerFrame`, as a sibling of `#fmViewer`, `#fmViewerHint`, and `#fmViewerError`. Place it after `#fmViewerHint` in source order so screen readers encounter the canvas description (`#fmViewer`'s `role="img"` aria-label) first, then the hint, then the control.

```html
<!-- Inside #fmViewerFrame, after #fmViewerHint -->
<button
  class="viewer-fullscreen-btn hidden"
  id="fmFullscreenBtn"
  type="button"
  aria-label="Enter fullscreen"
  aria-pressed="false"
>⛶</button>
```

The button starts hidden and is revealed only after successful model load (same trigger that reveals `#fmDownloadStlBtn`). See §6.

### 4.2 Gallery Modal (`#modelViewerCanvas`)

`#modelViewerCanvas` is `position: relative; overflow: hidden`. The button is an absolutely-positioned child inside the canvas container, not inside the modal header.

```html
<!-- Inside #modelViewerCanvas, as the last child -->
<button
  class="viewer-fullscreen-btn hidden"
  id="modalFullscreenBtn"
  type="button"
  aria-label="Enter fullscreen"
  aria-pressed="false"
>⛶</button>
```

It is inserted and removed by `mountModalViewer` / `teardownModalViewer` alongside the three.js renderer, so it cleanly tracks the viewer lifecycle.

**Relationship to existing modal close button:** The modal close button (`#modelViewerClose`, `✕`) lives in `.model-viewer-header` — above the canvas, visually and in DOM order. The fullscreen button lives in the top-right corner of the canvas itself. They are separated by the header bar, so they do not collide.

---

## 5. Fullscreen Layout

### 5.1 What Is Visible

When fullscreen is active, the viewport is filled with the canvas. The following elements are visible:

| Element | Fullscreen visibility | Notes |
|---|---|---|
| The 3D canvas | Fills viewport | ResizeObserver on the container will handle resize |
| "Drag to rotate · Scroll to zoom" hint | Visible, same bottom-center position | Continues to fade on interaction |
| Fullscreen exit button (⛶ / "Exit fullscreen") | Visible, top-right corner | Stays on top via `z-index: 4` |
| Download buttons (STL / GLB) | Hidden in fullscreen | Not needed during inspection; accessible after exit |
| Print report card (Figure Maker only) | Hidden in fullscreen | Below the viewer in normal flow; not relevant |
| Modal header + footer (Gallery only) | Hidden in fullscreen | Chrome is not part of the immersive experience |
| Page scroll content | Scrolled behind / irrelevant | Viewport is consumed by fullscreen |

### 5.2 Canvas Resize

The existing `ResizeObserver` in both viewers already calls `renderer.setSize()` on container size change. No additional resize logic is needed as long as the fullscreen mechanism resizes the container element.

### 5.3 Background

Fullscreen background: `#0a0b1a` (`--paper`) — matches the existing canvas background in both viewers. No new token needed.

---

## 6. State Machine — When the Button Appears

```
EMPTY STATE        → button: hidden
GENERATING/LOADING → button: hidden
VIEWER ERROR       → button: hidden
MODEL LOADED       → button: visible (aria-pressed="false", aria-label="Enter fullscreen")
  FULLSCREEN ACTIVE  → button: visible (aria-pressed="true", aria-label="Exit fullscreen", .is-fullscreen)
  FULLSCREEN EXITED  → button: visible (aria-pressed="false", aria-label="Enter fullscreen")
```

The "model loaded" trigger for Figure Maker is the `gltf` success callback inside `mountViewer` — the same point where `fmDownloadStlBtn` is shown. For the Gallery, it is the equivalent point inside `mountModalViewer` after the GLTF is added to the scene.

The button must also be hidden again if `teardownViewer` / `teardownModalViewer` is called (model replaced or modal closed).

---

## 7. Exit Affordances and Escape Key Behavior

### 7.1 Figure Maker

Only one layer of state: the inline viewer.

- Visible exit button (⛶, top-right of canvas) — click exits fullscreen.
- `Escape` key — exits fullscreen. No modal to worry about; the existing page is behind.

### 7.2 Gallery — Two-Layer Escape Problem

The Gallery has two dismissible layers:
1. **Fullscreen** (innermost — the canvas filling the viewport)
2. **Modal** (outermost — `#modelViewerModal` overlay)

**Esc key priority rule: fullscreen is dismissed first; a second Esc dismisses the modal.**

Rationale: the user opened fullscreen intentionally from within the modal. Pressing Esc once should undo the most recent action (fullscreen), not both layers. This matches browser-native fullscreen API behavior where the browser dismisses fullscreen on Esc before the page's own keydown handler fires.

Implementation guidance for the developer-agent:

- If using the Fullscreen API: the browser handles the first Esc to exit fullscreen natively. The existing `keydown` listener for `Escape → closeModelViewer()` should be guarded: only call `closeModelViewer()` if `document.fullscreenElement === null`.
- If using a CSS-overlay approach (no Fullscreen API): the `keydown` handler must check its own `isFullscreen` state flag; if true, exit fullscreen and return; only close the modal if not in fullscreen.

The visible exit button in both cases is unambiguous: it always exits fullscreen only, not the modal.

---

## 8. Accessibility

### 8.1 ARIA

```html
<button
  type="button"
  aria-label="Enter fullscreen"   <!-- updated to "Exit fullscreen" when active -->
  aria-pressed="false"            <!-- updated to "true" when fullscreen is active -->
>⛶</button>
```

`aria-pressed` signals the toggle state to screen readers without requiring a role change. Do not use `aria-expanded` (which implies revealing hidden content) or `aria-haspopup`.

The glyph `⛶` is a Unicode character, not an image, so no `aria-hidden` wrapper is needed on the glyph itself; the `aria-label` on the button overrides what is announced.

### 8.2 Focus Management

**Entering fullscreen:**
- Focus remains on the fullscreen button (which is still visible in the fullscreen canvas). Do not move focus to the canvas — it has `role="img"` and is not interactive by keyboard.

**Exiting fullscreen:**
- Focus returns to the fullscreen button (it remains visible in the now-normal viewer).
- For Gallery: if the modal closes immediately after exiting fullscreen (e.g., user presses Esc twice quickly), focus must return to the trigger button that opened the modal (`lastViewBtn` — this is already tracked in `gallery.js`'s `closeModelViewer`).

### 8.3 Keyboard Operability

The button is a native `<button>` element: Enter and Space activate it. No additional key handling needed beyond the Escape behavior in §7.

The 3D canvas is not keyboard-operable (OrbitControls does not expose keyboard orbit by default). This is a pre-existing limitation and out of scope for this spec.

### 8.4 Reduced Motion

The button's own transitions are short (`.15s`) and below the threshold that typically causes vestibular discomfort. No `prefers-reduced-motion` override needed for the button itself.

The fullscreen enter/exit transition (if the implementation uses a CSS transition on the container) should be suppressed:
```css
@media (prefers-reduced-motion: reduce) {
  .viewer-fullscreen-btn,
  .fm-viewer-frame.is-fullscreen,
  .model-viewer-canvas.is-fullscreen {
    transition: none;
  }
}
```

### 8.5 Contrast

The button uses `rgba(255,255,255,.70)` on `rgba(15,17,41,.72)` background. Luminance contrast is approximately 4.8:1 — passes WCAG AA for normal text and UI components (threshold 3:1). In hover state (`#ffffff` on `rgba(15,17,41,.90)`) contrast exceeds 7:1.

---

## 9. Consistency Across Both Viewers

| Property | Figure Maker | Gallery Modal |
|---|---|---|
| Glyph | ⛶ | ⛶ |
| Position | `top: .6rem; right: .6rem` inside canvas container | `top: .6rem; right: .6rem` inside canvas container |
| Class | `.viewer-fullscreen-btn` | `.viewer-fullscreen-btn` (shared) |
| Visibility gating | hidden until GLTF load success | hidden until GLTF load success |
| `aria-label` | "Enter fullscreen" / "Exit fullscreen" | "Enter fullscreen" / "Exit fullscreen" |
| `aria-pressed` | false / true | false / true |
| Escape behavior | exits fullscreen | exits fullscreen only; second Esc closes modal |
| Download/chrome visibility in fullscreen | downloads hidden | modal header + footer hidden |

The `.viewer-fullscreen-btn` class is defined once in `style.css` (shared tokens layer) or in a new shared CSS file, not duplicated in `figure_maker.css` and `gallery.css`. Because this button pattern may be reused by future viewers (e.g., Book Builder cover preview), putting it in `style.css` is appropriate.

---

## 10. Flagged Inconsistencies with Existing Design System

1. **z-index conflict**: `fmViewerError` is at `z-index: 3` in `figure_maker.css`. The fullscreen button at `z-index: 4` would appear above an active error overlay. The developer-agent must raise `fmViewerError` to `z-index: 5` to restore intended layering — or gate the button's `z-index` lower and rely on the button being hidden in error state. The hidden-in-error-state approach is simpler and avoids touching the error overlay.

2. **`.settings-btn` misuse pattern**: The existing download links inside the viewer (`#fmDownloadGlbBtn`, `.settings-btn`) use the in-flow row button style. Using `.settings-btn` for an absolute-overlay control would look visually wrong (it has `border-radius: 10px`, padding for row layout, and no semi-transparent background suitable for a canvas overlay). The `.viewer-fullscreen-btn` spec above deliberately diverges from `.settings-btn` — this is intentional and should be documented in a code comment.

3. **`model-viewer-canvas` overflow**: `gallery.css` sets `.model-viewer-canvas { overflow: hidden }`. An absolutely-positioned child button inside it will be clipped if it falls outside the container bounds. With `top: .6rem; right: .6rem` and a 36 px button this should be fine, but the developer-agent should verify at the `min-height: 260px` (mobile) breakpoint.

---

## 11. Open UX Questions for Product / Architect Review

1. **Fullscreen API vs. CSS overlay** — The Fullscreen API gives native OS fullscreen (browser chrome hidden, covers taskbar) and handles Esc natively. A CSS overlay (fixed positioning, z-index, `inset: 0`) is simpler, more portable, but keeps the browser chrome visible and the Esc behavior is entirely custom. The choice affects §7's Escape implementation and the perceived "depth" of the fullscreen experience. This is deferred to the architect-agent.

2. **Gallery: should fullscreen also work on the whole modal, or only the canvas?** — This spec scopes fullscreen to the canvas area only (modal chrome disappears). An alternative is to make the entire modal go fullscreen (title stays visible). Canvas-only is recommended for the immersive feel, but stakeholder preference should be confirmed.

3. **Auto-hide the fullscreen button after a few seconds** (like the hint pill) — The hint fades after first interaction. Should the fullscreen button also fade and re-appear on mouse/touch activity? This would reduce visual clutter but adds complexity. Recommendation: do not auto-hide for now; the button is small and non-obtrusive in the top-right corner.

4. **Touch gesture to exit fullscreen** — On mobile, a two-finger-downward swipe to exit fullscreen is a familiar pattern. This is beyond scope for the initial implementation; the visible exit button covers the use case.

5. **Tablet landscape orientation** — At tablet width (768–1024 px), the Figure Maker viewer is already full-width between 50 px gutters. The fullscreen button provides meaningful value by hiding the page chrome. No special layout adjustment needed; confirm with product whether the 50 px gutters should be removed in fullscreen (they should — the viewer container fills the viewport).
