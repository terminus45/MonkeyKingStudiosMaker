# Character Generator — Model Selector Migration + Full-Width Layout Refactor

**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`
**Precedent page:** `figure_maker.html` / `figure_maker.css` (already refactored to the target pattern — treat it as the reference implementation, not something to change).

---

## Summary of Changes

| Part | What changes |
|---|---|
| 1 | Remove `#cgModelSelect` from Character Generator; add a Gemini Generation Settings card to the Settings page |
| 2 | Flatten Character Generator from a two-column `340px 1fr` grid to a single-column full-width layout matching Figure Maker |
| 3 | Apply 50px side gutters to `.cg-image-frame` and its empty/loading states so they mirror the Figure Maker viewer frame treatment |

---

## Persistence Decision — Recommendation: Option A (localStorage)

**Recommendation: Option A — `localStorage` via the existing `monkeyking_cg_draft` key.**

Rationale: The model preference is user-device-local by nature (a creative choice, not a credential). `monkeyking_cg_draft` already saves `model` and `ar` from the Character Generator; the Settings page simply becomes a second write site for the `model` field in that same store. No backend change, no new API endpoint, and the Character Generator already has a working `restoreCgDraft()` / `saveCgDraft()` cycle. Option B would add a new `config.json` field (a backend change) for a preference that is less sensitive than an API key and has no value surviving across browsers.

The `monkeyking_cg_draft` localStorage key is the shared contract:
- **Settings page** writes `{ model: <selectedId> }` to the draft on change (merges, does not overwrite `ar`).
- **Character Generator** reads it at load via `restoreCgDraft()` as today; also writes it on change as today.
- Both read-after-write and write-from-settings must do a partial merge (read existing draft, update `model`, write back) so the `ar` key is not lost when Settings updates the model, and vice versa.

---

## Part 1 — Settings Page: Gemini Generation Settings Card

### Card placement

The Settings page currently has one `.settings-card` (`API Keys`). Add a second `.settings-card` **below** the API Keys card, separated by `gap: 1.5rem` on `.settings-main` (currently `padding` only — add `display: flex; flex-direction: column; gap: 1.5rem` to `.settings-main` instead of the current padding gap, or simply give the new card `margin-top: 1.5rem`).

Visual result: a second card with an orange left border (`border-left: 3px solid #ff6b35`, matching the API Keys card), titled "Generation Settings". The model select lives inside it as a single row with the same visual rhythm as a `.settings-key-row` but simpler (no password input, no eye/clear buttons).

### New card structure

```
.settings-card  (second card, below API Keys)
  .settings-card-header
    h2  "Generation Settings"
    p.settings-card-sub  "Preferences are saved locally in your browser."

  .settings-key-list
    .settings-key-row  (reuse existing class for consistent row padding/border)
      .settings-key-label-group
        label.settings-key-label[for="settingsCgModel"]  "Gemini Model"
        span.settings-key-hint  "Default model for the Character Generator"
      .settings-model-select-group  (new class — see CSS below)
        select#settingsCgModel  (options populated from GET /gemini/models; hardcoded fallback)
          option  Imagen 4
          option  Imagen 4 Fast
          option  Imagen 4 Ultra
          option  Gemini 2.5 Flash
        span.settings-status-chip#settingsCgModelStatus  aria-live="polite"
          (shows "Saved" briefly after change — see States below)
```

Note: The `label` element must use `for="settingsCgModel"` pointing to the select's `id`. Do not use `settings-key-label` as a `cursor: default` label — the existing CSS sets `cursor: default` on `.settings-key-label`; this is fine for a `<select>` because the `<select>` itself gets pointer. Use the `<label for>` association regardless.

### `.settings-model-select-group` CSS (new rule in `settings.css`)

```css
.settings-model-select-group {
  display: flex;
  align-items: center;
  gap: .65rem;
  flex-wrap: wrap;
}

.settings-model-select-group select {
  /* Inherit base select/textarea styling from style.css */
  flex: 1;
  min-width: 200px;
  max-width: 340px;
  font-size: .9rem;
}
```

This parallels `.settings-key-input-group` but without the `position: relative` wrapper (no overlay buttons needed).

### States for the model select row

| State | Visual |
|---|---|
| **Default / loading** | Select shows first hardcoded option; `#settingsCgModelStatus` hidden (`data-state="unknown"`, `visibility: hidden`) |
| **Options loaded from API** | Select rebuilt with API data; saved value restored from `monkeyking_cg_draft.model` |
| **Value changed by user** | Draft updated immediately; `#settingsCgModelStatus` shows "Saved" with `data-state="set-config"` styling (`background: rgba(74,222,128,.15); color: #4ade80`) for 2 seconds then reverts to hidden — matches the feel of the API key save feedback without requiring a button click |
| **API fetch failed** | Hardcoded fallback options remain; no error shown (silent, matching how `character_generator.js` handles it today) |

### How the model select loads its options

Same pattern as `loadModels()` in `character_generator.js`:
1. On page load, `settings.js` fetches `GET /gemini/models`.
2. If successful, rebuild `#settingsCgModel` options from `data.models`.
3. After building options, read `monkeyking_cg_draft` from localStorage and set `#settingsCgModel.value` to `draft.model` (if it exists and matches an available option); otherwise leave default (first imagen item, same logic as `loadModels()`).
4. If fetch fails, leave the hardcoded `<option>` elements in place — identical to CG behavior.

### How the model select persists on change

```
settingsCgModel.addEventListener('change', () => {
  // Read existing draft, update only model, write back
  const raw   = localStorage.getItem('monkeyking_cg_draft');
  const draft = raw ? JSON.parse(raw) : {};
  draft.model = settingsCgModel.value;
  localStorage.setItem('monkeyking_cg_draft', JSON.stringify(draft));
  // Show brief "Saved" chip feedback
  showModelSavedChip();
});
```

The `showModelSavedChip()` helper sets `settingsCgModelStatus.dataset.state = 'set-config'`, sets text "Saved", then clears after 2000 ms (set `data-state="unknown"`).

### Accessibility — Settings model select

- `<label for="settingsCgModel">` with visible text "Gemini Model" — explicit label association.
- `<span class="settings-key-hint">` provides supplementary context but is NOT wired to `aria-describedby` on the select (consistent with how the existing key-hint spans work in the API key rows — they are purely visual).
- The `#settingsCgModelStatus` chip uses `aria-live="polite"` so the "Saved" confirmation is announced without interruption.
- The `<select>` is natively keyboard-accessible; no additional ARIA needed.

---

## Part 2 — Character Generator: Single-Column Full-Width Layout

### Target layout (mirrors Figure Maker exactly)

```
<main class="cg-main">

  <!-- 1. Shared inputs panel (full-width, unchanged markup) -->
  <div class="shared-inputs-panel builder-step" id="sharedInputsPanel" ...> ... </div>

  <!-- 2. Tab-specific controls card (aspect ratio only — model selector removed) -->
  <div class="builder-step" id="cgTabControls" style="border-left: 5px solid var(--mustard)">
    <div class="control-group" id="cgAspectGroup">
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

  <!-- 3. Generate button + error (full-width, directly below controls) -->
  <div class="cg-actions">
    <button class="generate-btn" id="cgGenerateBtn" style="width: 100%" aria-live="polite">
      <span id="cgGenerateLabel">🎭 Generate Character</span>
      <div class="spinner hidden" id="cgSpinner" aria-hidden="true"></div>
    </button>
    <p class="cg-error hidden" id="cgErrorMsg" role="alert" aria-live="assertive"></p>
  </div>

  <!-- 4. Result area (full-width, 50px side gutters on the image frame) -->
  <section class="cg-result-area" aria-label="Generated character portrait">
    <div class="cg-image-frame" id="cgImageFrame" aria-live="polite">
      ...empty/loading/image states...
    </div>
    <div class="cg-action-row hidden" id="cgActionRow">
      ...download / use as cover buttons...
    </div>
  </section>

  <!-- 5. Session strip (full-width, unchanged) -->
  <section class="cg-strip-section hidden" id="cgStrip" ...> ... </section>

</main>
```

### What is removed from Character Generator HTML

- The entire `<div class="cg-layout">` wrapper element (and its closing tag).
- The `<aside class="cg-controls-panel">` wrapper element (and its closing tag).
- The `<section class="cg-result-area">` wrapper does NOT move — it stays, but is now a direct child of `cg-main` instead of the right column of `.cg-layout`.
- `<div class="gemini-opt">` containing `<label for="cgModelSelect">` and `<select id="cgModelSelect">` — the entire model select group is removed.
- The `<div class="gemini-options-row">` flex wrapper may be removed too since only one option remains (aspect ratio). The `#cgGeminiGroup` control-group div may be renamed or simplified to `#cgAspectGroup` for clarity, though the ID change is optional — the JS references `cgAspectPresets` directly, not `cgGeminiGroup`.
- The `.cg-controls-panel` `<aside>` is gone entirely; the generate button and error message move into the new `.cg-actions` div (see above).

### CSS changes in `character_generator.css`

**Rules to remove:**

```css
/* DELETE — no longer used */
.cg-layout { ... }            /* the 340px 1fr grid */
.cg-controls-panel { ... }   /* the sticky left panel */
```

**Rules to add:**

```css
/* Mirrors .fm-actions in figure_maker.css */
.cg-actions {
  display: flex;
  flex-direction: column;
}

/* 50px side gutters on the image frame — mirrors .fm-viewer-frame */
.cg-image-frame {
  /* keep existing: background, border, border-radius, min-height, display, overflow, position */
  margin-left: 50px;
  margin-right: 50px;
}

/* Empty state must match the frame's gutters so nothing shifts on state change */
/* (currently .cg-empty-state is inside .cg-image-frame — it already inherits the frame's geometry) */
/* No change to .cg-empty-state or .cg-loading-state needed because they live inside .cg-image-frame */
/* The gutters are on the frame itself, not on the inner states */
```

Note on empty and loading states: Both `.cg-empty-state` and `.cg-loading-state` are children of `.cg-image-frame`. Because the 50px margins are applied to the frame (not to the inner states), all three states (empty, loading, portrait) automatically share the same horizontal position. This is exactly how the Figure Maker handles it for `.fm-viewer-empty` and `.fm-progress-state` — the comment in `figure_maker.css` says "match the viewer frame's side gutters so nothing shifts on state change." For Character Generator the frame-level margin achieves this automatically without duplicating the margin on every child state.

**Rules to update — responsive breakpoint:**

```css
@media (max-width: 700px) {
  /* DELETE: .cg-layout and .cg-controls-panel rules — those elements are gone */

  .cg-image-frame {
    min-height: 280px;
    margin-left: 16px;   /* reduce gutters on narrow screens */
    margin-right: 16px;
  }

  .cg-main {
    padding: 1rem .75rem 3rem;
    gap: 1.5rem;
  }
}
```

**Rationale for 16px on mobile:** At `max-width: 700px`, the `cg-main` already has `.75rem` horizontal padding (≈12px). Setting `margin-left/right: 16px` on the image frame gives a modest additional inset that maintains the visual language of "the portrait has breathing room" without eating into already-narrow viewport width. The Figure Maker has no explicit narrow-screen override for its 50px gutters — this is a **flag**: at 375px wide, the Figure Maker 3D viewer frame would be `375 - 100 = 275px` wide, which is very tight. The spec recommends the Character Generator add the explicit 16px narrow-screen override and flags this as a potential fix needed in `figure_maker.css` too (out of scope for this PR).

### `.cg-result-area` — minor update

Remove the `display: flex; flex-direction: column; gap: 1rem` from the `cg-result-area` rule only if it conflicts (it should not — keep it). The section is now a direct child of `cg-main` which has `gap: 2rem`, providing spacing above it. The `cg-action-row` below the image frame already has its own spacing.

---

## Part 3 — Image Frame: 50px Side Gutters (Detail)

### Visual result

The character portrait frame (`#cgImageFrame`) will have 50px of horizontal breathing room from the edges of the content column, identical to how the Figure Maker 3D viewer is inset. At 1200px content max-width with 1rem page padding on each side, the effective frame width is approximately `1200 - 32 - 100 = 1068px`. The portrait image fills this frame at `object-fit: contain`, letterboxing within the aspect ratio as before.

The `min-height: 420px` on `.cg-image-frame` is retained (currently `420px` on desktop, `280px` on mobile). This is larger than the Figure Maker's minimum of `360px` for the empty/progress states — that difference is fine, as portrait images warrant more vertical space than a placeholder empty state.

### State consistency across empty / loading / portrait

| State | Element | Frame margins applied? |
|---|---|---|
| Empty | `.cg-empty-state` inside `.cg-image-frame` | Yes — gutters on frame, inner state stays centered |
| Loading | `.cg-loading-state` inside `.cg-image-frame` | Yes — same frame |
| Portrait shown | `.cg-portrait` inside `.cg-image-frame` | Yes — same frame |

No additional margin or width CSS is needed on the inner state elements. The frame's `overflow: hidden` and `border-radius` remain intact.

---

## Aspect Ratio Control — Standalone Appearance

With the model select removed, the `#cgTabControls` card now contains only the aspect ratio pill group. The `gemini-options-row` flex wrapper (which arranged model select + aspect ratio side by side) is no longer needed. The simplified interior:

```
.builder-step#cgTabControls  (border-left: 5px solid var(--mustard))
  .control-group#cgAspectGroup
    label  "Aspect Ratio"
    .presets#cgAspectPresets[role="group"][aria-label="Aspect ratio"]
      button.preset.ar-btn[data-ar="1:1"]   1:1
      button.preset.ar-btn.active[data-ar="3:4"]  3:4
      button.preset.ar-btn[data-ar="4:3"]   4:3
      button.preset.ar-btn[data-ar="9:16"]  9:16
      button.preset.ar-btn[data-ar="16:9"]  16:9
```

The `.gemini-options-row` and `.gemini-opt` wrappers are removed from HTML. Check whether `.gemini-options-row` and `.gemini-opt` have rules in `character_generator.css` — if so, delete those rules. If these classes exist only as HTML attributes with no CSS rule backing them, simply removing them from HTML is sufficient.

The `label "Aspect Ratio"` remains associated with the `role="group"` div via the group's `aria-label` attribute (the `<label>` element itself labels the group visually but has no `for` — `<div>` cannot be a `for` target). This is the existing pattern and is acceptable; screen readers reach the group via `aria-label="Aspect ratio"` on the div.

---

## JS Changes in `character_generator.js`

### Lines to remove

- `const cgModelSelect = document.getElementById('cgModelSelect');` — delete the DOM ref.
- The entire `loadModels()` function body (the function that fetches `GET /gemini/models` and rebuilds the select) — delete it.
- The `cgModelSelect.addEventListener('change', saveCgDraft);` listener — delete it.
- Inside `saveCgDraft()`: the `model: cgModelSelect.value` line — delete it (or change to `model: undefined` and then remove the key). Since `monkeyking_cg_draft` will now receive `model` from the Settings page, `saveCgDraft()` in CG should stop writing `model` so it does not overwrite the Settings preference when the user adjusts aspect ratio. Simplest: `saveCgDraft()` writes only `{ ar: getSelectedAR() }` going forward.
- Inside `restoreCgDraft()`: the model-restore block — delete it (Settings page will have set the model on load; CG no longer owns model restoration).
- The `loadModels()` call in the init block — delete it.

### What stays in `character_generator.js`

- `cgAspectPresets` event listener and `getSelectedAR()` — unchanged.
- `saveCgDraft()` — simplified to write only `ar`.
- `restoreCgDraft()` — simplified to restore only `ar`.
- The `const model = cgModelSelect.value` line inside the generate handler — change to read from `monkeyking_cg_draft` in localStorage instead:
  ```
  const raw   = localStorage.getItem('monkeyking_cg_draft');
  const draft = raw ? JSON.parse(raw) : {};
  const model = draft.model || 'imagen-4.0-generate-001';
  ```
  This is the same default-fallback logic as `loadModels()` uses today.

### JS changes in `settings.js`

Add a new init section after the existing `loadKeys()` call:

1. `loadGeminiModels()` — fetches `GET /gemini/models`, rebuilds `#settingsCgModel`, restores value from `monkeyking_cg_draft.model`.
2. `#settingsCgModel` change listener — merges `model` into `monkeyking_cg_draft` and shows the brief "Saved" chip.

No changes to `KEY_ROWS`, `settingsSaveAll`, or the eye/clear button logic — those are API-key concerns only.

---

## Responsive Behavior Summary

| Breakpoint | Character Generator | Settings |
|---|---|---|
| > 700px | Single column, 50px image frame gutters | Two stacked cards, max-width 680px centered |
| <= 700px | Single column (no change — already single-column), image frame gutters shrink to 16px | Cards stack vertically, `.settings-card-header` padding reduced per existing rules; model select row follows `.settings-key-row` padding reduction (`padding: 1rem 1rem` per the existing `@media (max-width: 600px)` rule) |

The Settings page responsive breakpoint is `max-width: 600px` (not 700px — see `settings.css`). The model select row will inherit the same padding reduction as the API key rows automatically via `.settings-key-row` — no new media query needed in `settings.css`.

---

## Accessibility Summary

| Element | Requirement |
|---|---|
| `#settingsCgModel` | `<label for="settingsCgModel">` with text "Gemini Model" |
| `#settingsCgModelStatus` | `aria-live="polite"` — announces "Saved" on change |
| `#cgAspectPresets` | Retain `role="group"` and `aria-label="Aspect ratio"` — unchanged |
| `#cgImageFrame` | Retain `aria-live="polite"` — unchanged |
| `#cgErrorMsg` | Retain `role="alert"` and `aria-live="assertive"` — unchanged |
| `#cgGenerateBtn` | Retain `aria-live="polite"` — unchanged |
| Skip link | `<a href="#cgMain">` continues to target the correct main element |
| Focus order (CG) | Skip link → header nav → `#sharedInputsPanel` (first textarea) → `#cgTabControls` (aspect ratio group) → `#cgGenerateBtn` → `#cgImageFrame` content → `#cgActionRow` buttons → `#cgStrip` |

---

## Files That Will Change

| File | Why |
|---|---|
| `frontend/character_generator.html` | Remove `.cg-layout` grid, `.cg-controls-panel` aside, `#cgModelSelect` and model opt group; add `.cg-actions` div; flatten to single-column direct children of `cg-main` |
| `frontend/character_generator.css` | Delete `.cg-layout` and `.cg-controls-panel` rules; add `.cg-actions`; add `margin-left/right: 50px` to `.cg-image-frame`; update `@media (max-width: 700px)` |
| `frontend/character_generator.js` | Remove `cgModelSelect` DOM ref, `loadModels()` function, model-change listener, model lines in `saveCgDraft`/`restoreCgDraft`; update generate handler to read model from `monkeyking_cg_draft` localStorage |
| `frontend/settings.html` | Add second `.settings-card` ("Generation Settings") with `#settingsCgModel` select row below the API Keys card |
| `frontend/settings.css` | Add `.settings-model-select-group` rule; add `display: flex; flex-direction: column; gap: 1.5rem` to `.settings-main` (or `margin-top: 1.5rem` on the new card) |
| `frontend/settings.js` | Add `loadGeminiModels()` init call; add `#settingsCgModel` change listener with localStorage merge logic; add `showModelSavedChip()` helper |

No backend changes. `main.py`, `gemini_generator.py`, `settings_store.py`, and `shared_inputs.js` are all unchanged.

---

## Design System Consistency Notes

1. The `.cg-actions` div mirrors `.fm-actions` in `figure_maker.css` exactly — same `display: flex; flex-direction: column` pattern. Name it `.cg-actions` (not `.fm-actions`) to keep it page-scoped, matching the existing naming convention.

2. The 50px margin on `.cg-image-frame` directly matches the identical rule on `.fm-viewer-frame`, `.fm-viewer-empty`, and `.fm-progress-state`. This is an established visual convention: "full-width interactive/result frames get 50px breathing room so the user can scroll past them." The spec brings Character Generator into alignment.

3. The second `.settings-card` reuses all existing settings classes (`.settings-card`, `.settings-card-header`, `.settings-card-sub`, `.settings-key-list`, `.settings-key-row`, `.settings-key-label-group`, `.settings-key-label`, `.settings-key-hint`, `.settings-status-chip`). The only new class is `.settings-model-select-group`, needed because the model row has a `<select>` instead of the password-input + eye/clear button trio in `.settings-key-input-group`. Introducing this one class is appropriate — it avoids repurposing the input-wrap pattern for a control it was not designed for.

4. **Flag — Figure Maker 50px gutters on narrow screens:** `figure_maker.css` has no `@media` override for the `margin-left/right: 50px` on `.fm-viewer-frame`, `.fm-viewer-empty`, or `.fm-progress-state`. At 375px viewport, after the 1rem page padding (`~16px each side`), the frame would be only `375 - 32 - 100 = 243px` wide. This spec adds the 16px narrow-screen override to Character Generator; a matching fix in `figure_maker.css` is recommended as a follow-up and should be flagged to the developer-agent.
