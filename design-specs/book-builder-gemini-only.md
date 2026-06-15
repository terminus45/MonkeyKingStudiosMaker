# Book Builder — Gemini-Only Migration Spec

**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`
**Precedent:** `design-specs/cg-model-to-settings-and-fullwidth.md` (Character Generator model migration, already implemented).

---

## 0. Prerequisite Observation: Two Style Fields Are a Latent Bug

Before describing what changes, a correctness issue must be flagged.

The current Book Builder has **two distinct style fields** that appear to do the same thing:

- `#stylePromptInput` — the canonical Shared Inputs field at the top of the page (synced via `shared_inputs.js`). This is what ALL generate calls actually read (`style_prompt: stylePromptInput.value.trim()` at lines 571, 707, 912, 1035, 1095). It is also persisted to `monkeyking_shared_inputs` and to the project JSON (`project.style_prompt`).
- `#genStylePrompt` — a second style textarea inside Step 3 `.gen-controls`, with its own preset pills. It is saved to `monkeyking_gen_settings.stylePrompt` but is **never sent to the API** — none of the generate payload builders use it.

`#genStylePrompt` is effectively dead UI: it accumulates a value, saves it to localStorage, and displays style presets, but its value has no effect on any generation. This spec removes it. The style-preset buttons must move to point at the already-functional `#stylePromptInput`.

This should be the first thing verified before the developer-agent begins implementation.

---

## 1. Product Recommendation: Option B — Move Model to Settings, Keep AR on Page

**Recommendation: Option B.**

Rationale:

- **Consistency is the primary driver.** The Character Generator migration was completed one commit ago on this exact branch: model moved to Settings, aspect ratio kept in a per-page tab-controls card. Doing the same for Book Builder means the Settings "Generation Settings" card becomes the single place a user configures their Gemini model across all image-generation pages. A user who picks "Imagen 4 Ultra" once gets that choice honored everywhere.
- **Book Builder is not meaningfully different from Character Generator for this decision.** Both produce a single Gemini generate call per item (page vs. portrait). The model choice is a user preference, not a per-book or per-page parameter.
- **Aspect ratio is genuinely page-layout-specific.** A user building a square-format book vs. a landscape-format book needs a different AR. That is a per-project decision that belongs on the Book Builder page. Character Generator already exposes AR in its tab-controls card — the pattern is established.

### How Book Builder reads the shared model

Book Builder will read `gemini_model` from `localStorage['monkeyking_cg_draft']`, the same key used by Character Generator and written by Settings. Key resolution at generate time:

```
const raw    = localStorage.getItem('monkeyking_cg_draft');
const draft  = raw ? JSON.parse(raw) : {};
const model  = draft.model || 'imagen-4.0-generate-001';
```

This is the identical pattern introduced in Character Generator's generate handler when the CG model select was removed. The fallback `'imagen-4.0-generate-001'` matches the first hardcoded option in `settings.html`.

### Naming note on `monkeyking_cg_draft`

The key is named for the Character Generator by historical accident, but it now holds cross-page preferences (`model`, `ar`). This spec does NOT rename the key (that would require coordinated migration across three pages). Future cleanup may rename it to something like `monkeyking_gen_prefs`, but that is out of scope here.

---

## 2. Controls to Remove from Book Builder

### From `book_builder.html` — elements to delete entirely

| Element / group | Current location | Reason for removal |
|---|---|---|
| `.provider-toggle` div containing both `.provider-btn` buttons | Top of `.gen-controls` | Provider is always Gemini; no toggle needed |
| `#geminiModelSelect` `<select>` and its `.gemini-opt` wrapper | `.gemini-only` control group | Model moves to Settings `#settingsBbModel` (see §4) |
| `#modelSelect` `<select>` (SD model) and its `.control-group.sd-only` | `.gen-controls` | SD removed |
| `#sizePresets` preset group, `#widthInput`, `#heightInput`, `.size-dims-row`, `.size-dims-x/.size-dims-px` spans | `.control-group.sd-only` "Canvas Size" | Replaced by AR picker (see §3) |
| `#steps` range, `#stepsVal`, `#cfg` range, `#cfgVal`, `.sliders.sd-only` wrapper | `.gen-controls` | SD removed |
| `#samplerSelect` and its `.control-group.sd-only` | `.gen-controls` | SD removed |
| `#clipSkipSelect` and its `.control-group.sd-only` | `.gen-controls` | SD removed |
| `#genNegPrompt` textarea, `#negToggle` label, their `.control-group.sd-only` | `.gen-controls` | SD removed |
| `#loraSelect`, `#loraScaleRow`, `#loraScale`, `#loraScaleVal` and their wrapper | `.control-group.sd-only` | SD removed |
| `#loraSelect2`, `#loraScaleRow2`, `#loraScale2`, `#loraScaleVal2` and their wrapper | `.control-group.sd-only` | SD removed |
| `#genStylePrompt` textarea and its `.control-group` | `.gen-controls` | Dead UI (see §0); style now comes exclusively from `#stylePromptInput` (Shared Inputs) |
| `#genStylePresets` preset pill buttons | `.gen-controls` | Relocate to point at `#stylePromptInput` (see §5) |

### From `book_builder.html` — class attributes to clean up

- Remove `class="gemini-only hidden"` and `class="sd-only"` attributes throughout (these visibility-toggle classes become meaningless when provider is always Gemini).
- The `#geminiAspectPresets` div and its `.gemini-opt` wrapper are **kept but restructured** (see §3).

### From `book_builder.js` — code to remove

- `let provider = 'sd'` state variable (line 45).
- `let canvasW = 512, canvasH = 512` state variables (line 44) — replaced by `let geminiAR`.
- All DOM refs for removed elements: `modelSel`, `genNegPrompt`, `negToggle`, `stepsEl`, `stepsVal`, `cfgEl`, `cfgVal`, `samplerSel`, `clipSkipSel`, `geminiModelSel`, `loraSelect`, `loraScaleRow`, `loraScaleEl`, `loraScaleVal`, `loraSelect2`, `loraScaleRow2`, `loraScaleEl2`, `loraScaleVal2`, `genStylePrompt`, `widthInput`, `heightInput`.
- `loadModels()` function and its call.
- `loadLoras()` function and its call.
- All LoRA event listeners (`loraSelect.addEventListener`, `loraScaleEl.addEventListener`, etc.).
- `setProvider()` function and the `.provider-btn` click listeners.
- The `negToggle` click listener.
- `setCanvasSize()` function, the `#sizePresets` click listener, `onDimInput()` function, and the `widthInput`/`heightInput` change listeners.
- The SD slider listeners (`stepsEl`, `cfgEl`).
- Inside `saveGenSettings()`: all SD-related keys — `modelNum`, `canvasW`, `canvasH`, `steps`, `cfg`, `negPrompt`, `loraNum`, `loraScale`, `loraNum2`, `loraScale2`, `sampler`, `clipSkip`, `provider`, `geminiModel`. Only `geminiAR` (renamed to `ar`) and the style preset state (if moved here) remain. See §6 for the new schema.
- Inside `restoreGenSettings()`: all corresponding restore branches for the removed keys.
- Inside `resetGenSettingsBtn` handler: all SD reset lines.
- The `showCardProgress(pageNum, 0, provider === 'sd' ? parseInt(stepsEl.value) : 1)` calls — simplify to `showCardProgress(pageNum, 0, 1)` (Gemini always reports a single step).
- In `saveGenSettings()` change listener array: `[modelSel, loraSelect, loraScaleEl, loraSelect2, loraScaleEl2, samplerSel, clipSkipSel, geminiModelSel]` — remove all these; only `genStylePrompt` (now gone) was there for style; no change listener needed for `geminiAR` since it is already saved inside the AR click handler.

### What to NOT remove

- `#geminiAspectPresets` and its click handler (restructured, see §3).
- The `geminiAR` state variable and the AR-save logic inside `saveGenSettings()`.
- The `#genStylePresets` preset buttons — **moved**, not deleted (see §5).
- The `settings-row` div with Save / Load / Reset settings buttons — keep; it still makes sense for the remaining `geminiAR` setting.
- All project-related logic: `saveProjectBtn`, `loadProjectFile`, `clearProjectBtn`, `saveState()`, `restoreState()` — unchanged.

---

## 3. Resulting Step 3 Generation Settings Card Layout

### Visual result

Step 3 (`#step3`, bordered left with `1px solid rgba(255,255,255,.10)` per `book_builder.css`) will contain:

```
Step 3 header: "③ Generate Images"

[ Aspect Ratio label ]
[ 1:1 ] [ 16:9 ] [ 9:16 ] [ 4:3* ] [ 3:4 ]    ← pill group, *4:3 is default

[ ⚡ Generate All Images ]  [ ■ Stop ]
[ progress bar ]
```

That is the entire visible content of Step 3. Clean, kid-friendly, two interactive elements.

### HTML structure for the controls area

```
<div class="gen-controls-gemini">

  <div class="control-group" id="bbAspectGroup">
    <label id="bbAspectLabel">Page Shape</label>
    <div class="presets" id="geminiAspectPresets"
         role="group"
         aria-labelledby="bbAspectLabel">
      <button class="preset ar-btn" data-ar="1:1">1:1</button>
      <button class="preset ar-btn" data-ar="16:9">16:9</button>
      <button class="preset ar-btn" data-ar="9:16">9:16</button>
      <button class="preset ar-btn active" data-ar="4:3">4:3</button>
      <button class="preset ar-btn" data-ar="3:4">3:4</button>
    </div>
    <p class="hint" id="bbAspectHint">
      4:3 is the classic storybook shape. Use 16:9 for landscape spreads.
    </p>
  </div>

</div>
```

Replace the entire existing `<div class="gen-controls">` with the above `<div class="gen-controls-gemini">`. The `#geminiAspectPresets` id is kept to avoid JS refactoring (the click handler references `document.getElementById('geminiAspectPresets')`).

### Default aspect ratio recommendation

**Default: 4:3.** Rationale: 4:3 matches the proportions of a physical children's book page at landscape orientation; it aligns with how print-formatted picture books are designed; it gives illustrations wide enough framing to show scene and character together. The current default is 1:1 (square) which was acceptable for SD512 but is not optimised for storybook page layouts. The AR restores from `monkeyking_gen_settings.ar` if the user has a saved preference, otherwise 4:3 applies.

### The `genStylePrompt` textarea removal + style-preset relocation

The step-3 style textarea (`#genStylePrompt`) is removed. The style-preset buttons (`#genStylePresets`) are moved into the Shared Inputs card, directly below `#stylePromptInput` (the canonical style textarea), replacing the `#genStylePresets` reference. The presest buttons will set `stylePromptInput.value` instead of `genStylePrompt.value`. This makes the preset pills visually adjacent to the field they modify. The hint text below `#stylePromptInput` can be updated to note that the style applies to all illustrations.

Flag: the style-preset buttons currently live in step 3 and required scrolling down to reach them. Moving them to the always-visible Shared Inputs card is a UX improvement regardless of the SD migration.

---

## 4. Settings Page — Add Book Builder Model Row

### Recommendation: Extend the existing `#settingsCgModel` row to serve both pages

Rather than adding a separate `#settingsBbModel` select, Book Builder will **read the same `draft.model` key** that Character Generator writes and Settings manages. No new settings row is needed.

**Rationale:** The Gemini model is a user-level preference ("I always use Imagen 4 Ultra"). There is no compelling reason to have separate model choices for Book Builder vs. Character Generator. One unified model select reduces UI surface area and cognitive load.

**One change is needed in `settings.html`:** update the hint text on the `#settingsCgModel` row from:

```
"Default model for the Character Generator"
```

to:

```
"Default Gemini model for image generation (Character Generator and Book Builder)"
```

This is the only Settings file change required.

---

## 5. `localStorage['monkeyking_gen_settings']` — Schema After Cleanup

### Keys that remain

| Key | Type | Default | Notes |
|---|---|---|---|
| `ar` | string | `'4:3'` | Gemini aspect ratio for storybook pages. Renamed from `geminiAR` to `ar` for brevity; the old key `geminiAR` is also accepted during restore for back-compat (see migration below). |

### Keys that are removed

`modelNum`, `canvasW`, `canvasH`, `steps`, `cfg`, `stylePrompt`, `negPrompt`, `loraNum`, `loraScale`, `loraNum2`, `loraScale2`, `sampler`, `clipSkip`, `provider`, `geminiModel`.

### Back-compat migration in `restoreGenSettings()`

Users currently have the fat object in localStorage. The new `restoreGenSettings()` must not crash on old data. The safe approach:

```
function restoreGenSettings() {
  let s;
  try { s = JSON.parse(localStorage.getItem(GEN_KEY) || 'null'); } catch { return; }
  if (!s) return;

  // Accept both old key name (geminiAR) and new key (ar) for back-compat
  const savedAR = s.ar || s.geminiAR;
  if (savedAR) {
    geminiAR = savedAR;
    document.querySelectorAll('.ar-btn').forEach(
      b => b.classList.toggle('active', b.dataset.ar === savedAR)
    );
  }
  // All other keys (modelNum, canvasW, steps, etc.) are silently ignored —
  // no crash because restoreGenSettings() only touches elements that exist.
}
```

No explicit migration or localStorage.removeItem call is needed. The old keys are simply ignored. Over time the old data will be replaced by the new slim object when `saveGenSettings()` next writes.

### New `saveGenSettings()` output

```js
function saveGenSettings() {
  localStorage.setItem(GEN_KEY, JSON.stringify({ ar: geminiAR }));
}
```

### Impact on Save/Load Settings buttons

The "Save Settings" download and "Load Settings" file-import buttons remain. After the migration, the exported JSON will only contain `{ "ar": "4:3" }`. Importing a legacy settings file (fat SD object) will not crash — `restoreGenSettings()` will read `ar` or `geminiAR` and ignore unknown keys. The "Reset" button simplifies to:

```js
document.getElementById('resetGenSettingsBtn').addEventListener('click', () => {
  if (!confirm('Reset generation settings to defaults?')) return;
  localStorage.removeItem(GEN_KEY);
  geminiAR = '4:3';
  document.querySelectorAll('.ar-btn').forEach(
    b => b.classList.toggle('active', b.dataset.ar === '4:3')
  );
});
```

---

## 6. Generate Payload Shape

Both `generateSinglePage()` and the queue loop in `queueBtn.addEventListener` will send the same simplified body:

```js
const genBody = {
  prompt:              current.image_prompt,
  style_prompt:        stylePromptInput.value.trim(),   // from Shared Inputs
  provider:            'gemini',                        // hardcoded; no provider field needed
  gemini_model:        (() => {
    try {
      const d = JSON.parse(localStorage.getItem('monkeyking_cg_draft') || '{}');
      return d.model || 'imagen-4.0-generate-001';
    } catch { return 'imagen-4.0-generate-001'; }
  })(),
  gemini_aspect_ratio: geminiAR,
};
```

Fields no longer sent:
- `width`, `height` — not applicable to Gemini (API uses aspect ratio, not pixel dimensions)
- `negative_prompt`, `model_num`, `steps`, `guidance_scale`, `seed`, `sampler`, `clip_skip`, `lora_num`, `lora_num_2`, `lora_scale`, `lora_scale_2`

The `provider: 'gemini'` field is included for clarity and because `POST /generate/stream` still accepts and routes on the `provider` field server-side. It is hardcoded as a constant string, not read from state.

### Aspect ratio vs. width/height

The page thumbnail (`#card-thumb-wrap`) currently has `aspect-ratio: 1 / 1` in `.card-thumb-wrap` CSS. This should update to reflect the user's chosen AR. However, because the card layout is injected by JS (`renderPages()`), and the AR can be 4:3 or 16:9 or 3:4, the simplest approach is to keep `.card-thumb-wrap` as `aspect-ratio: unset` and rely on the generated image's intrinsic dimensions (via `object-fit: cover`). Alternatively, the developer-agent can wire `geminiAR` changes to update `card-thumb-wrap` CSS. This is a nice-to-have: the spec recommends the developer-agent implement a simple approach (leave `aspect-ratio: 1 / 1` on `.card-thumb-wrap` unchanged for now — the thumbnail is a preview, not a print-faithful representation) and note it as a future enhancement.

---

## 7. `book_builder.js` Additional Changes (Not Covered Above)

### `loadModels()` and `loadLoras()` calls in the init block

Locate the init block (near the end of the file, roughly after `restoreGenSettings()`) that calls `checkHealth()`, `loadModels()`, `loadLoras()`. Remove the `loadModels()` and `loadLoras()` calls entirely. `checkHealth()` stays (it still shows server status; `data.loaded_model` reference in the health display is benign — if the SD model is gone the field will be null and the existing null-coalescing `?? 'unknown'` handles it).

### `showCardProgress(pageNum, 0, provider === 'sd' ? parseInt(stepsEl.value) : 1)`

There are two call sites of this. Both become:

```js
showCardProgress(pageNum, 0, 1);
```

### `const provider = 'sd'` (module-level state removal)

Remove the `let provider = 'sd'` state variable. Where `provider` is currently used to branch SD vs. Gemini logic, the branch is resolved in favor of Gemini unconditionally. The variable simply disappears.

---

## 8. CSS Changes

### `book_builder.css` — rules to remove

- `.gen-controls { display: grid; grid-template-columns: 1fr 1fr 1fr; ... }` — delete (the new `.gen-controls-gemini` is a simple `display: flex; flex-direction: column; gap: 1.25rem`).
- Any rules targeting `.provider-btn`, `.sd-only`, `.gemini-only` — delete.
- Rules for `#sizePresets .size-btn`, `.size-dims-row`, `.size-dims-x`, `.size-dims-px` — delete.
- Rules for the negative-prompt toggle: `.toggle-label`, `.toggle-arrow`, `textarea.collapsed` — delete if no other page uses them.
- Slider-specific rules (`.slider-row`, `.lora-scale-row`) — delete if not referenced elsewhere.

Check `style.css` and `character_generator.css` for any of these class names before deleting; the spec notes `.slider-row` may be defined in `style.css` and shared — verify before removing from `book_builder.css`.

### `book_builder.css` — rules to add

```css
/* Replaces the 3-column .gen-controls grid */
.gen-controls-gemini {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
```

### Responsive update

The existing `@media (max-width: 700px)` rule includes `{ .gen-controls { grid-template-columns: 1fr; } }`. Remove that grid-template override — it targets the old `.gen-controls` class. No new responsive rule is needed for `.gen-controls-gemini` (it is already single-column at all widths).

---

## 9. Accessibility + Responsive Notes

### Accessibility

| Element | Requirement |
|---|---|
| `#geminiAspectPresets` AR pill group | Add `role="group"` and `aria-labelledby="bbAspectLabel"` (the `<label>` element is not `for`-connected to a `<div>`, so the group label must use `aria-labelledby`). Current markup lacks these. |
| Removed provider toggle | Skip-link and focus order unaffected — the toggle was not in the skip-link target. |
| `#queueBtn` | Retains `disabled` state until `storyData` is populated — no change. |
| Page-card regen buttons (`.thumb-regen-btn`) | No change; the `_regenActive` guard continues to prevent double-tap races. |
| Removed LoRA/steps/sampler controls | No screen-reader announcements were associated with these; no aria cleanup needed. |
| Style preset buttons (moved) | They gain `aria-label` implicitly from their text content ("Ink & Manga", "Watercolor", etc.); no additional ARIA needed. |

### Responsive

The three-column `.gen-controls` grid at desktop collapses to one-column at 700px via the existing media query. After migration the new `.gen-controls-gemini` is always one-column, making the media query override moot. The AR pill group wraps naturally on narrow screens using `flex-wrap` from the `.presets` base rule (confirm this is set in `style.css`; it is the pattern used on all other pill groups throughout the app).

The `.queue-btn-row` and `.progress-wrap` are unchanged and already handle narrow viewports correctly.

---

## 10. File-by-File Change List

| File | Change |
|---|---|
| `frontend/book_builder.html` | Remove `.provider-toggle`, all `.sd-only` control groups, `#geminiModelSelect` and its wrapper, the `#genStylePrompt` + `#genStylePresets` control group. Restructure the remaining AR control into `<div class="gen-controls-gemini">` with `#geminiAspectPresets`. Move style-preset buttons above or below `#stylePromptInput` in the Shared Inputs panel. Add `role="group"` and `aria-labelledby` to `#geminiAspectPresets`. Default active AR pill set to `data-ar="4:3"`. |
| `frontend/book_builder.js` | Remove `provider` state, `canvasW`/`canvasH` state, all SD DOM refs, `loadModels()`, `loadLoras()`, `setProvider()`, `setCanvasSize()`, `onDimInput()`, all LoRA/slider listeners, `negToggle` listener. Slim down `saveGenSettings()` to write only `{ ar }`. Slim down `restoreGenSettings()` to restore only `ar` (with `geminiAR` back-compat alias). Slim down `resetGenSettingsBtn` handler. Update both generate payload builders to read model from `monkeyking_cg_draft` localStorage. Hardcode `provider: 'gemini'`. Remove the two `showCardProgress(..., provider === 'sd' ? ... : 1)` calls — replace with `showCardProgress(..., 1)`. Move style-preset click handler to target `stylePromptInput` instead of `genStylePrompt`. Remove `loadModels()` and `loadLoras()` from init. |
| `frontend/book_builder.css` | Delete `.gen-controls` grid rule and its media-query override. Delete `.provider-btn`, `.sd-only`, `.gemini-only` rules (if present). Delete canvas-size, slider, LoRA-row, negative-prompt-toggle rules (`.toggle-label`, `.toggle-arrow`, `textarea.collapsed`, `.slider-row`, `.lora-scale-row`, `.size-dims-row`, `.size-dims-x`, `.size-dims-px`). Add `.gen-controls-gemini` single-column flex rule. |
| `frontend/settings.html` | Update hint text on `#settingsCgModel` row to mention both Character Generator and Book Builder. No structural change. |
| `frontend/settings.js` | No code changes. The model is already written to `monkeyking_cg_draft.model` by the existing change listener. |

Backend files (`main.py`, `generator.py`, `gemini_generator.py`, `config.py`, `settings_store.py`) are **not changed by this spec.** The `/generate/stream` endpoint already handles `provider: 'gemini'` with `gemini_model` and `gemini_aspect_ratio` fields. The `/models` and `/loras` endpoints remain (they may still be used by other internal tooling), but the Book Builder no longer calls them.

---

## 11. Design System Consistency Notes

1. **Flag — `.card-thumb-wrap` hardcoded 1:1 aspect ratio.** The page card thumbnails are currently square (`aspect-ratio: 1 / 1` in `.card-thumb-wrap`). After this migration the generated image AR may be 4:3 or 16:9. The `object-fit: cover` on the thumbnail `<img>` will crop to square, which is acceptable as a preview treatment. If the developer-agent wishes to sync thumbnail AR to the selected AR, they should update `geminiAR` state changes to call a helper that updates all `.card-thumb-wrap` elements with the matching `aspect-ratio` CSS property inline. This is a nice-to-have, not a blocker.

2. **`#genStylePrompt` dead code.** This is the most important correctness fix in this spec. The style textarea in Step 3 has never affected any generated image; all generate calls read `#stylePromptInput`. The developer-agent must verify this by grepping generate call bodies before implementing, in case a future change wired them together.

3. **`monkeyking_gen_settings` is no longer "shared with Image Studio"** (per the comment on line 284 of `book_builder.js`). That comment implies a now-removed Image Studio page was reading the same localStorage key. The comment should be removed.

4. **The Settings "Generation Settings" card hint text is currently CG-only.** After this migration two pages read the model from that card. The hint must be updated to avoid user confusion when the Book Builder behaves according to what they set in Settings.

5. **No new design tokens, component classes, or color values are introduced by this spec.** All changes are subtractive (removing SD controls) plus one additive class (`.gen-controls-gemini`) that follows the exact same pattern as existing flex column wrappers throughout the codebase.
