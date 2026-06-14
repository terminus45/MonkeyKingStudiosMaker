# Shared Inputs Panel — Design Spec
# BookBuilderBot · Cross-tab shared state UX

Status: Ready for developer-agent implementation
Files affected:
- `frontend/character_generator.html` — add Story Prompt field, restructure shared panel
- `frontend/book_builder.html` — add Character Description field, restructure shared panel
- `frontend/figure_maker.html` — add Style Prompt + Story Prompt, add style presets
- `frontend/style.css` — add `.shared-inputs-panel` and `.sync-badge` component classes
- `frontend/character_generator.css` — minor adjustment for new panel height in controls card
- `frontend/figure_maker.css` — add shared panel spacing rule inside `.fm-controls-card`

---

## 1. Mental model

A single shared store object — `window.sharedInputs = { character, style, story }` held in
`sessionStorage` under the key `mkb_shared_inputs` — is the source of truth. Every page reads
from it on load and writes to it on every input event. Because the three pages are separate HTML
documents (not a SPA), sync is via `sessionStorage` on every `input` event; a `storage` event
listener keeps two tabs in sync if the user has multiple tabs open simultaneously.

The UI communicates this shared nature through a distinct, consistently placed panel that appears
identically on all three pages.

---

## 2. Shared store data shape

```js
// key: "mkb_shared_inputs"
{
  character: "",   // Character Description free text
  style: "",       // Style Prompt free text (+ active preset suffix)
  story: ""        // Story Prompt free text
}
```

Field mapping from current ids to the shared store:

| Page | Current id | New id (spec) | Store key |
|---|---|---|---|
| Character Generator | `cgDescInput` | `sharedCharacterInput` | `character` |
| Character Generator | `cgStyleInput` | `sharedStyleInput` | `style` |
| Character Generator | *(missing)* | `sharedStoryInput` | `story` |
| Book Builder | `conceptInput` | `sharedStoryInput` | `story` |
| Book Builder | `stylePromptInput` | `sharedStyleInput` | `style` |
| Book Builder | *(missing)* | `sharedCharacterInput` | `character` |
| Figure Maker | `fmPromptInput` | `sharedCharacterInput` | `character` |
| Figure Maker | *(missing)* | `sharedStyleInput` | `style` |
| Figure Maker | *(missing)* | `sharedStoryInput` | `story` |

**Important for developer:** The ids `sharedCharacterInput`, `sharedStyleInput`, and
`sharedStoryInput` are the canonical ids used across all three pages. This makes cross-page
JS code (e.g. sessionStorage read/write helpers) reusable without per-page branching.

**Migration note for Book Builder JS:** `book_builder.js` reads `conceptInput` and
`stylePromptInput` throughout. The developer must update every reference in `book_builder.js`
to the new ids. Similarly, `character_generator.js` references to `cgDescInput` and
`cgStyleInput` must be updated. `figure_maker.js` references to `fmPromptInput` must be updated.

---

## 3. Shared Inputs Panel — component spec

### 3a. Visual description

A card that looks like a `.builder-step` card with a **teal** left border (`border-left: 5px solid var(--teal)`). Teal is used because it is the "tertiary" accent in the MCM system — already associated with step 3 / active / focus — and it reads as "connected/shared" rather than the per-step mustard/terracotta/olive accents.

At the top of the card, a small sync badge sits immediately below the `<h2>` heading. The three
textareas follow, each in a `.control-group`. Style Prompt has the preset pills beneath it.
A one-sentence per-tab emphasis note appears as a `.hint` paragraph directly below the card
heading, before the first field.

Visually: warm off-white card, teal left stripe, bold "Your Story" heading, faint teal-tinted sync
badge on a second row, then three labeled textareas stacked vertically, Style Prompt last with pill
row below it.

### 3b. HTML skeleton (identical structure on all three pages)

```html
<!-- SHARED INPUTS PANEL -->
<div class="shared-inputs-panel builder-step" id="sharedInputsPanel">

  <div class="step-header">
    <h2>Your Story</h2>
    <!-- Sync badge — sits in the header row, pushed to the right -->
    <span class="sync-badge" id="syncBadge" aria-label="These fields are shared across Character Generator, Book Builder, and Figure Maker">
      <svg class="sync-icon" aria-hidden="true" focusable="false" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      Shared across tabs
    </span>
  </div>

  <!-- Per-tab emphasis note (content varies per page — see section 5) -->
  <p class="hint shared-tab-hint" id="sharedTabHint"><!-- per-tab copy --></p>

  <!-- FIELD 1: Character Description -->
  <div class="control-group shared-field-primary" id="sharedCharacterGroup">
    <label for="sharedCharacterInput">
      Character Description
      <!-- Per-tab primary badge on the emphasized tab(s) — see section 5 -->
    </label>
    <textarea
      id="sharedCharacterInput"
      rows="3"
      placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
      aria-describedby="sharedCharacterHint"
    ></textarea>
    <p class="hint" id="sharedCharacterHint">Appearance, personality, and any props or outfit details.</p>
  </div>

  <!-- FIELD 2: Story Prompt -->
  <div class="control-group shared-field-story" id="sharedStoryGroup" style="margin-top: .9rem">
    <label for="sharedStoryInput">Story Prompt</label>
    <textarea
      id="sharedStoryInput"
      rows="3"
      placeholder="Sun Wukong learns to share with the forest animals — a story about kindness and sharing…"
      aria-describedby="sharedStoryHint"
    ></textarea>
    <p class="hint" id="sharedStoryHint">The scenario, adventure, or concept your story is about.</p>
  </div>

  <!-- FIELD 3: Style Prompt + presets -->
  <div class="control-group shared-field-style" id="sharedStyleGroup" style="margin-top: .9rem">
    <label for="sharedStyleInput">Style Prompt</label>
    <textarea
      id="sharedStyleInput"
      rows="2"
      placeholder="Soft watercolor, children's book art, warm pastel tones…"
      aria-describedby="sharedStyleHint"
    ></textarea>
    <p class="hint" id="sharedStyleHint">The visual art style applied to all generated images.</p>
    <!-- Style preset pills (identical data-suffix values on all three pages) -->
    <div class="presets shared-style-presets" id="sharedStylePresets" role="group" aria-label="Style presets" style="margin-top: .4rem">
      <button class="preset" data-suffix="Black and white ink line art, manga linework, chibi storybook illustration, white background, no color">Ink &amp; Manga</button>
      <button class="preset" data-suffix="Traditional Chinese ink painting, brush strokes, Sumi-e style, monochrome">Sumi-e</button>
      <button class="preset" data-suffix="Vibrant cinematic illustration, detailed painterly, storybook art, rich colors">Cinematic</button>
      <button class="preset" data-suffix="Soft watercolor illustration, children's book art, delicate washes, pastel tones">Watercolor</button>
      <button class="preset" data-suffix="">Clear</button>
    </div>
  </div>

</div>
<!-- END SHARED INPUTS PANEL -->
```

### 3c. Field order rationale

Order: Character → Story → Style.

- Character comes first because it is the conceptual anchor — who the story is about.
- Story second — what happens.
- Style last — how it looks — and anchored to the preset pills below it so the pills read as
  directly attached to the field.

This order is consistent on all three pages. The per-tab emphasis treatment (section 5) uses
a visual highlight, not reordering, so the field positions are always predictable.

---

## 4. Sync badge — component spec

### 4a. Visual description

A small inline badge that sits in the `.step-header` flex row, pushed to the right via
`margin-left: auto`. It contains a chain-link SVG icon (16 × 16, `stroke-width: 2.5`) and the
text "Shared across tabs". Color: teal (`var(--teal)`) text and icon on a teal-tinted background
`rgba(58,125,122,.10)`. Rounded pill shape, 12 px font, no border — the tinted background gives
it enough presence without competing with field labels.

On hover, a native browser `title` tooltip reveals the full copy:
"Editing here updates Character Generator, Book Builder, and Figure Maker"

On focus (keyboard navigation to the badge — it is a `<span>` with `tabindex="0"`), a teal
focus ring appears.

### 4b. CSS additions for `.shared-inputs-panel` and `.sync-badge` (add to `style.css`)

```css
/* ── Shared Inputs Panel ── */
.shared-inputs-panel {
  /* Inherits all .builder-step styles (background, border, radius, shadow, padding).
     The teal left border is set inline on the element: style="border-left: 5px solid var(--teal)"
     This matches the existing pattern for step-specific borders in book_builder.css. */
}

.shared-tab-hint {
  margin-top: -.5rem;   /* pull up under the step-header margin-bottom (1.1rem) */
  margin-bottom: .9rem;
  font-size: .8rem;
  color: var(--muted);
  font-style: italic;
  font-weight: 400;
}

/* ── Sync badge ── */
.sync-badge {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
  margin-left: auto;
  background: rgba(58,125,122,.10);
  color: var(--teal);
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .03em;
  padding: .28rem .65rem;
  border-radius: 20px;
  cursor: default;
  white-space: nowrap;
  /* no border — tinted bg is sufficient */
}
.sync-badge:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}
.sync-icon {
  flex-shrink: 0;
  /* stroke color inherited from .sync-badge color: var(--teal) */
}

/* ── Per-tab field emphasis (primary highlight) ── */
/*
  The .shared-field-primary class is added per-page to the control-group(s)
  that are most relevant to that tab's output. It applies a subtle left highlight bar
  and a slightly bolder label color. No color is changed — only weight and a 3px
  teal-tinted left inset border on the textarea.
*/
.shared-field-primary label {
  color: var(--ink);           /* darkened from var(--muted) */
  font-weight: 800;
}
.shared-field-primary textarea {
  border-left-color: var(--teal);   /* teal left edge on the textarea itself */
  border-left-width: 3px;
}

/* Mobile reflow */
@media (max-width: 700px) {
  .sync-badge {
    font-size: .68rem;
    padding: .22rem .5rem;
  }
}
```

**Flag:** The `.builder-step` class is defined in `book_builder.css`, not `style.css`. The
Character Generator already redeclares equivalent styles in `character_generator.css` under
`.cg-controls-panel .builder-step`. The Figure Maker uses `.fm-controls-card` with identical
values. For the shared panel to use `.builder-step` safely on all three pages, either:

(a) Move `.builder-step` definition to `style.css` (recommended — it is already a cross-page
    pattern), or
(b) Keep the redundant declarations in `character_generator.css` and `figure_maker.css` and
    add a `.shared-inputs-panel` rule there that mirrors the card look.

**Recommendation: move `.builder-step` to `style.css`** so all pages can use it without
re-declaration. The developer should audit `book_builder.css` and remove the now-duplicate
definition there (keeping the step-specific border-left rules, which reference `#step1`,
`#step2`, etc. and are fine to leave in `book_builder.css`).

---

## 5. Per-tab placement and emphasis

### 5a. Character Generator (`character_generator.html`)

**Placement:** The shared panel replaces the existing `#cgControlCard` content. The controls
card becomes the shared panel card. After it, the Gemini-specific controls (model select,
aspect ratio pills) remain in a separate `<div class="control-group" id="cgGeminiGroup">` that
is still inside the `.cg-controls-panel` aside but outside the shared panel div. The generate
button lives below both, still inside the aside.

Revised aside structure:
```html
<aside class="cg-controls-panel" aria-label="Character generation controls">

  <!-- SHARED PANEL -->
  <div class="shared-inputs-panel builder-step" id="sharedInputsPanel"
       style="border-left: 5px solid var(--teal)">
    <div class="step-header">
      <h2>Your Story</h2>
      <span class="sync-badge" tabindex="0"
            title="Editing here updates Character Generator, Book Builder, and Figure Maker"
            aria-label="These fields sync across all three tabs">
        <!-- chain-link SVG -->
        Shared across tabs
      </span>
    </div>
    <p class="hint shared-tab-hint" id="sharedTabHint">
      Character Generator mainly uses Character and Style — Story adds optional scene context.
    </p>

    <!-- Character field: PRIMARY emphasis -->
    <div class="control-group shared-field-primary" id="sharedCharacterGroup">
      <label for="sharedCharacterInput">Character Description</label>
      <textarea id="sharedCharacterInput" rows="3"
        placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
        aria-describedby="sharedCharacterHint"></textarea>
      <p class="hint" id="sharedCharacterHint">Appearance, personality, and any props or outfit details.</p>
    </div>

    <!-- Story field: secondary (no primary class) -->
    <div class="control-group" id="sharedStoryGroup" style="margin-top: .9rem">
      <label for="sharedStoryInput">Story Prompt <span class="hint">(optional — sets scene context)</span></label>
      <textarea id="sharedStoryInput" rows="2"
        placeholder="e.g. Standing at the entrance of a magic cave at sunrise…"
        aria-describedby="sharedStoryHint"></textarea>
      <p class="hint" id="sharedStoryHint">The scenario or setting for the portrait.</p>
    </div>

    <!-- Style field: PRIMARY emphasis -->
    <div class="control-group shared-field-primary" id="sharedStyleGroup" style="margin-top: .9rem">
      <label for="sharedStyleInput">Style Prompt</label>
      <textarea id="sharedStyleInput" rows="2"
        placeholder="Soft watercolor, children's book art, warm pastel tones…"
        aria-describedby="sharedStyleHint"></textarea>
      <p class="hint" id="sharedStyleHint">The visual art style for the portrait.</p>
      <div class="presets shared-style-presets" id="sharedStylePresets"
           role="group" aria-label="Style presets" style="margin-top: .4rem">
        <!-- 5 preset buttons — identical to section 3b -->
      </div>
    </div>
  </div>
  <!-- END SHARED PANEL -->

  <!-- TAB-SPECIFIC: Gemini model + aspect ratio (unchanged from current) -->
  <div class="builder-step" id="cgTabControls"
       style="border-left: 5px solid var(--mustard); margin-top: 1rem">
    <div class="control-group" id="cgGeminiGroup">
      <div class="gemini-options-row">
        <!-- model select + aspect ratio pills unchanged -->
      </div>
    </div>
  </div>

  <!-- Generate button (outside both cards, full width) -->
  <button class="generate-btn" id="cgGenerateBtn"
          style="width: 100%; margin-top: 1rem" aria-live="polite">
    <span id="cgGenerateLabel">Generate Character</span>
    <div class="spinner hidden" id="cgSpinner" aria-hidden="true"></div>
  </button>
  <p class="cg-error hidden" id="cgErrorMsg" role="alert" aria-live="assertive"></p>

</aside>
```

**Emphasis:** Character Description and Style Prompt both receive `.shared-field-primary`
(both are directly used to build the generation prompt). Story Prompt is de-emphasized with
`rows="2"` and an `(optional)` hint in the label.

### 5b. Book Builder (`book_builder.html`)

**Placement:** Step 1 currently contains the language toggle, concept textarea, style prompt,
and decompose buttons. The shared panel replaces the concept + style textarea section and adds
Character Description. The language toggle and action buttons stay in the step-header area.

Revised Step 1 inner structure:
```html
<section class="builder-step" id="step1">
  <div class="step-header">
    <span class="step-num">①</span>
    <h2>Story Concept</h2>
    <div class="project-actions"><!-- save/load/clear buttons unchanged --></div>
  </div>

  <!-- Language toggle (tab-specific, stays at top) -->
  <div class="control-group">
    <label>Language</label>
    <div class="lang-toggle" id="langToggle"><!-- unchanged --></div>
  </div>

  <!-- SHARED PANEL (embedded inside step 1, not a separate card) -->
  <!-- Note: on Book Builder, the shared panel uses NO separate card wrapper —
       it sits as a flat group inside step1 to avoid nested cards.
       It still uses the shared ids and classes on the fields themselves. -->
  <div class="shared-inputs-inline" id="sharedInputsPanel" style="margin-top: .75rem">

    <p class="hint shared-tab-hint" id="sharedTabHint">
      Book Builder mainly uses Story and Character — Style applies to all illustrations.
    </p>

    <!-- sync badge as a standalone row here (not in a step-header) -->
    <div class="sync-badge-row">
      <span class="sync-badge" tabindex="0"
            title="Editing here updates Character Generator, Book Builder, and Figure Maker"
            aria-label="These fields sync across all three tabs">
        <!-- chain-link SVG -->
        Shared across tabs
      </span>
    </div>

    <!-- Story field: PRIMARY emphasis -->
    <div class="control-group shared-field-primary" id="sharedStoryGroup" style="margin-top: .6rem">
      <label for="sharedStoryInput">Story Prompt</label>
      <textarea id="sharedStoryInput" rows="4"
        placeholder="Sun Wukong learns to share with the forest animals — a tale about kindness…"
        aria-describedby="sharedStoryHint"></textarea>
      <p class="hint" id="sharedStoryHint">The concept, adventure, or scenario your storybook is about.</p>
    </div>

    <!-- Character field: PRIMARY emphasis -->
    <div class="control-group shared-field-primary" id="sharedCharacterGroup" style="margin-top: .9rem">
      <label for="sharedCharacterInput">Character Description</label>
      <textarea id="sharedCharacterInput" rows="3"
        placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
        aria-describedby="sharedCharacterHint"></textarea>
      <p class="hint" id="sharedCharacterHint">Who is the main character? Appearance, personality, key props. Used to keep art consistent across all pages.</p>
    </div>

    <!-- Style field: secondary (no primary class) -->
    <div class="control-group" id="sharedStyleGroup" style="margin-top: .9rem">
      <label for="sharedStyleInput">Style Prompt <span class="hint">(applied to all illustrations)</span></label>
      <textarea id="sharedStyleInput" rows="2"
        placeholder="Describe the visual style for all illustrations…"
        aria-describedby="sharedStyleHint"></textarea>
      <p class="hint" id="sharedStyleHint">The art style used for every page image.</p>
      <div class="presets shared-style-presets" id="sharedStylePresets"
           role="group" aria-label="Style presets" style="margin-top: .4rem">
        <!-- 5 preset buttons — identical to section 3b -->
      </div>
    </div>

  </div>
  <!-- END SHARED INPUTS (inline) -->

  <!-- Decompose buttons and CSV import stay below, unchanged -->
  <div class="decompose-btn-row"><!-- unchanged --></div>
  <!-- ... -->
</section>
```

**Note on the Book Builder embedding pattern:** The shared panel on Book Builder does NOT use
a nested `.builder-step` card (which would create a visually awkward card-within-card). Instead,
it uses a plain `<div class="shared-inputs-inline">` wrapper that provides only spacing
(no border, background, or shadow). The field `id` attributes and `shared-field-primary` classes
are still applied — JS can use those regardless of wrapper. The sync badge is placed as a
standalone row (`sync-badge-row`) instead of inside a `step-header` flex row.

Add to `style.css`:
```css
.shared-inputs-inline {
  display: flex;
  flex-direction: column;
}
.sync-badge-row {
  display: flex;
  margin-bottom: .5rem;
}
```

**Emphasis:** Story and Character are both `.shared-field-primary`. Style is secondary.

### 5c. Figure Maker (`figure_maker.html`)

**Placement:** The shared panel replaces the existing `#fmControlCard` header section (which
currently has only `fmPromptInput`). It slots in as a `.shared-inputs-panel builder-step` card
above the quick-pick chips and generate button, inside the `.fm-controls-panel` aside. The quick-
pick chips become a tab-specific section below the shared panel.

Revised `.fm-controls-panel` aside structure:
```html
<aside class="fm-controls-panel" aria-label="Figure generation controls">

  <!-- SHARED PANEL -->
  <div class="shared-inputs-panel builder-step" id="sharedInputsPanel"
       style="border-left: 5px solid var(--teal)">
    <div class="step-header">
      <h2>Your Story</h2>
      <span class="sync-badge" tabindex="0"
            title="Editing here updates Character Generator, Book Builder, and Figure Maker"
            aria-label="These fields sync across all three tabs">
        <!-- chain-link SVG -->
        Shared across tabs
      </span>
    </div>
    <p class="hint shared-tab-hint" id="sharedTabHint">
      Figure Maker mainly uses Character — Style shapes how it looks; Story adds context.
    </p>

    <!-- Character field: PRIMARY emphasis -->
    <div class="control-group shared-field-primary" id="sharedCharacterGroup">
      <label for="sharedCharacterInput">Character Description</label>
      <textarea id="sharedCharacterInput" rows="4"
        placeholder="A roaring T-Rex with tiny arms and a friendly smile…"
        aria-describedby="sharedCharacterHint"
        maxlength="500"></textarea>
      <p class="hint" id="sharedCharacterHint">Describe what you want to build — this is what Bolt will design.</p>
    </div>

    <!-- Story field: secondary -->
    <div class="control-group" id="sharedStoryGroup" style="margin-top: .9rem">
      <label for="sharedStoryInput">Story Prompt <span class="hint">(optional — adds context)</span></label>
      <textarea id="sharedStoryInput" rows="2"
        placeholder="e.g. A jungle adventure story where the T-Rex is the hero…"
        aria-describedby="sharedStoryHint"></textarea>
      <p class="hint" id="sharedStoryHint">What story is this figure part of?</p>
    </div>

    <!-- Style field: secondary -->
    <div class="control-group" id="sharedStyleGroup" style="margin-top: .9rem">
      <label for="sharedStyleInput">Style Prompt <span class="hint">(optional)</span></label>
      <textarea id="sharedStyleInput" rows="2"
        placeholder="Soft watercolor, children's book art, warm pastel tones…"
        aria-describedby="sharedStyleHint"></textarea>
      <p class="hint" id="sharedStyleHint">The visual style (also used by Character Generator and Book Builder).</p>
      <div class="presets shared-style-presets" id="sharedStylePresets"
           role="group" aria-label="Style presets" style="margin-top: .4rem">
        <!-- 5 preset buttons — identical to section 3b -->
      </div>
    </div>
  </div>
  <!-- END SHARED PANEL -->

  <!-- TAB-SPECIFIC: Quick-pick chips -->
  <div class="fm-controls-card" id="fmTabControls"
       style="border-left: 5px solid var(--mustard); margin-top: 1rem">
    <div class="fm-controls-header">
      <h2>What do you want to build?</h2>
    </div>
    <!-- Quick-pick chips unchanged (id="fmChips") -->
    <div class="control-group" id="fmChipGroup" style="margin-top: .75rem">
      <label id="fmChipLabel">Quick ideas</label>
      <div class="presets" id="fmChips" role="group" aria-labelledby="fmChipLabel">
        <!-- chip buttons unchanged -->
      </div>
    </div>
    <!-- Quick-pick chips now populate sharedCharacterInput instead of fmPromptInput -->
  </div>

  <!-- Generate button + enhanced prompt reveal + error -->
  <button class="generate-btn" id="fmGenerateBtn"
          style="width: 100%; margin-top: 1rem">
    <span id="fmGenerateLabel">Build my figure!</span>
    <div class="spinner hidden" id="fmSpinner" aria-hidden="true"></div>
  </button>
  <div class="fm-enhanced-prompt hidden" id="fmEnhancedPromptBox" aria-live="polite">
    <p class="fm-enhanced-label">Bolt's version of your idea:</p>
    <p id="fmEnhancedPromptText"></p>
  </div>
  <p class="cg-error hidden" id="fmErrorMsg" role="alert" aria-live="assertive"></p>
  <button class="settings-btn hidden" id="fmResetBtn"
          style="width: 100%; margin-top: .75rem; justify-content: center;"
          aria-label="Clear and start over">↺ Make another</button>

</aside>
```

**Chips migration note:** The quick-pick chips currently set `fmPromptInput.value`. After the
rename they should set `sharedCharacterInput.value` and trigger an `input` event to persist to
the shared store.

**The Bolt mascot zone** (`#fmMascotZone`) remains above the layout grid, unchanged.

**Emphasis:** Only Character is `.shared-field-primary`. Story and Style are both secondary
with `(optional)` in the label.

---

## 6. Sync badge copy

| Context | Text |
|---|---|
| Badge text (all pages) | "Shared across tabs" |
| `title` tooltip (all pages) | "Editing here updates Character Generator, Book Builder, and Figure Maker" |
| `aria-label` (all pages) | "These fields sync across all three tabs" |

The badge text omits emojis per the project's no-emoji-in-files convention (emoji are only in
nav links and buttons that already use them per existing HTML).

---

## 7. Style preset pills — canonical data-suffix values

All three pages must use these exact five buttons in this exact order with these exact
`data-suffix` values. No variation between pages.

```html
<button class="preset" data-suffix="Black and white ink line art, manga linework, chibi storybook illustration, white background, no color">Ink &amp; Manga</button>
<button class="preset" data-suffix="Traditional Chinese ink painting, brush strokes, Sumi-e style, monochrome">Sumi-e</button>
<button class="preset" data-suffix="Vibrant cinematic illustration, detailed painterly, storybook art, rich colors">Cinematic</button>
<button class="preset" data-suffix="Soft watercolor illustration, children's book art, delicate washes, pastel tones">Watercolor</button>
<button class="preset" data-suffix="">Clear</button>
```

The "Clear" button deactivates all others and clears `sharedStyleInput`. The active state
(`.preset.active`) must be synced when the page loads from the shared store — the developer
should match the current textarea value against each `data-suffix` to restore the active pill.

**Note:** Book Builder currently has two `id="stylePresets"` elements (one in step 1, one in
step 3 for the image generation controls). After this spec is implemented, step 1's presets
move into the shared panel with `id="sharedStylePresets"`. The step 3 presets (for per-page
regen) are a separate control and retain their existing id — this is not a conflict.

---

## 8. Combined prompt preview (v1 recommendation)

**Recommendation: defer to v1.1.**

A combined preview would show how the three fields merge into what is actually sent to the
generation endpoint. While valuable for power users, it adds implementation complexity
(the merge logic differs per tab and per endpoint) and visual noise in what is already a
controls-heavy sidebar. The shared panel already communicates purpose through field labels
and hints.

If the developer wants to add it later, the recommended treatment is a collapsible
`<details>` element at the bottom of the shared panel:

```html
<details class="shared-preview-details" style="margin-top: .9rem">
  <summary class="hint" style="cursor:pointer">Preview combined prompt</summary>
  <pre class="shared-preview-text" id="sharedPreviewText"
       style="font-size:.75rem; color:var(--muted); white-space:pre-wrap; margin-top:.4rem"></pre>
</details>
```

JS would update `#sharedPreviewText` on every input event. Collapsed by default.

---

## 9. Shared store JS — behaviour spec (not code)

The developer should implement a shared utility (either inlined or as a small `shared-inputs.js`
included on all three pages) that handles:

1. **On page load:** Read `sessionStorage.getItem("mkb_shared_inputs")`, parse JSON, and
   populate `sharedCharacterInput`, `sharedStoryInput`, and `sharedStyleInput`. Then restore
   the active preset pill by comparing `sharedStyleInput.value` against each `data-suffix`.

2. **On `input` event for any of the three textareas:** Write the updated value to the shared
   store in sessionStorage. Debounce by ~150 ms to avoid thrashing on fast typing.

3. **On style preset click:** Set `sharedStyleInput.value` to the clicked button's `data-suffix`
   (or clear for "Clear"), toggle `.active` class (only one active at a time), and write to the
   shared store.

4. **On `storage` event** (cross-tab sync): If `event.key === "mkb_shared_inputs"`, re-read
   and re-populate all three fields. This keeps two open tabs in sync.

5. **On page unload:** No action needed — sessionStorage persists for the browser session.

**Integration with existing page JS:**
- `book_builder.js` references `conceptInput` and `stylePromptInput` throughout its build flow.
  Both must be updated to `sharedStoryInput` and `sharedStyleInput`.
- `character_generator.js` references `cgDescInput` and `cgStyleInput` — update to
  `sharedCharacterInput` and `sharedStyleInput`.
- `figure_maker.js` references `fmPromptInput` — update to `sharedCharacterInput`.

---

## 10. Accessibility

- All three textareas have associated `<label for="…">` with matching `id` values.
- Each textarea has `aria-describedby` pointing to its `.hint` paragraph.
- The sync badge is a `<span tabindex="0">` — it is informational, not interactive, but is
  keyboard-reachable for screen-reader users via `tabindex="0"` and has a descriptive
  `aria-label`. The `title` attribute provides the tooltip for pointer users.
- Field minimum tap/click target height: textareas are `rows="2"` minimum, which with
  line-height and padding exceeds 44 px.
- `.hint` paragraphs: `color: var(--muted)` = `#8c8070` on `#faf7f2` background. Contrast
  ratio approximately 3.8:1. This falls below WCAG AA for body text but is acceptable for
  supplementary hint text (WCAG allows 3:1 for large text / UI components). If the team
  decides to meet AA strictly for hints, use `--ink-soft` (`#5a4a38`, ~6.2:1) instead.
- `.sync-badge` text: teal `#3a7d7a` on `rgba(58,125,122,.10)` tinted background ≈ near-white
  effective background. Contrast ratio ~4.5:1 — meets WCAG AA for small text.
- `.shared-field-primary label` uses `color: var(--ink)` = `#2c2416` on `#faf7f2` ≈ 11:1 —
  well above AA.
- The preset pill group has `role="group"` and `aria-label="Style presets"`. Individual buttons
  are `<button>` elements with visible text — no additional ARIA needed.

### Keyboard navigation order (controls panel)

Character Description → Story Prompt → Style Prompt → Style preset pills (tab through each)
→ [tab-specific controls] → Generate button.

The sync badge (`tabindex="0"`) falls between the `<h2>` and the first textarea in DOM order,
which is correct — it is contextual metadata, not an action.

---

## 11. Mobile reflow (≤ 700 px)

At or below the existing 700 px breakpoint all layouts already collapse to a single column.
The shared panel is a vertical stack of labeled textareas — it reflowing to single column
requires no additional breakpoint rules. Existing rules handle:

- `.cg-layout` → single column (character_generator.css)
- `.fm-layout` → single column, controls first (figure_maker.css)
- `.builder-main` is already single-column (book_builder.css)

The only mobile-specific addition is the `.sync-badge` font-size reduction already noted in
section 4b.

The style preset pills use `flex-wrap: wrap` (from `.presets` in `style.css`) — on mobile
they wrap to two or three rows as needed, which is the existing behavior and acceptable.

---

## 12. Consistency flags for developer

1. **`.builder-step` lives in `book_builder.css`** — this class is referenced by
   `character_generator.css` via `.cg-controls-panel .builder-step`. Moving the base rule to
   `style.css` removes the duplication and lets the shared panel use it cleanly. Flag this to
   the architect-agent before implementation.

2. **Figure Maker uses `.fm-controls-card`** (defined in `figure_maker.css`) rather than
   `.builder-step`. After this spec the tab-specific section in Figure Maker keeps
   `.fm-controls-card` (it is already styled correctly) while the shared panel uses
   `.shared-inputs-panel builder-step`. If `.builder-step` is not moved to `style.css`, the
   developer must add the card styles to `figure_maker.css` for the shared panel.

3. **Duplicate `id="stylePresets"` in Book Builder** — pre-existing issue noted in
   `design-specs/character-generator.md` section 11. This spec resolves it for step 1
   (which becomes `id="sharedStylePresets"`). The step 3 presets are unaffected.

4. **The `conceptInput` textarea has no `<label for="…">`** in the current `book_builder.html`
   (line 64 — the textarea exists inside `.concept-row` without an associated label). This is
   an existing accessibility gap. After the migration the field gets a proper label
   (`<label for="sharedStoryInput">Story Prompt</label>`).

5. **`fmPromptInput` has `maxlength="500"`** in the current HTML. This attribute should be
   carried over to `sharedCharacterInput` on the Figure Maker page specifically. The same
   attribute is not needed on the Character Generator or Book Builder versions of the field
   (those have no backend length restriction at this time).
