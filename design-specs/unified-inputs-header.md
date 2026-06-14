# Unified Inputs Header — Design Spec

**Scope:** Canonical shared-inputs panel for Character Generator, Figure Maker, and Book Builder.
**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`

---

## Layout & Placement — full-width across all three tabs

**Requirement:** The shared panel must span the **full content width** at the **top** of every tab — clean, simple, kid-friendly — the way it reads on Book Builder today. It must NOT be confined to a narrow controls column.

**Current reality (the problem):**
- **Book Builder** — `.builder-main` is single-column, so the block is already full-width. ✅ (the target look)
- **Character Generator** — `.cg-layout` is a `340px 1fr` grid and the panel lives inside the 340px `.cg-controls-panel`, so it's cramped to ~340px. ✗
- **Figure Maker** — `.fm-layout` is a `7fr 4fr` grid and the panel lives inside `.fm-controls-panel`, so it's ~64% width. ✗

**Target placement:** On CG and FM, lift `#sharedInputsPanel` **out of the two-column grid** and make it a direct child of the page's `<main>`, positioned **above** the grid. The grid below then holds only the tab-specific controls + the output/viewer. Result: on all three tabs the panel is a full-width card at the top, flush with the content area beneath it — identical to Book Builder.

### Character Generator (`character_generator.html`)
```
<main class="cg-main">
  <!-- SHARED INPUTS PANEL (full-width, first content) -->  ← moved here, out of .cg-controls-panel
  <div class="shared-inputs-panel builder-step" id="sharedInputsPanel" …> … </div>

  <div class="cg-layout">                 ← 340px 1fr grid, now holds only tab controls + output
    <aside class="cg-controls-panel">      ← model/aspect/Generate only (shared panel removed)
      …
    </aside>
    <section …image output…> … </section>
  </div>
</main>
```

### Figure Maker (`figure_maker.html`)
```
<main class="fm-main">
  <div …mascot zone (bolt bubble)…> … </div>   ← stays at top as the kid-friendly greeting
  <!-- SHARED INPUTS PANEL (full-width) -->        ← moved here, out of .fm-controls-panel
  <div class="shared-inputs-panel builder-step" id="sharedInputsPanel" …> … </div>

  <div class="fm-layout">                 ← 7fr 4fr grid, now holds only tab controls + viewer
    <aside class="fm-controls-panel">      ← chips/Generate only (shared panel removed)
      …
    </aside>
    <section …3D viewer…> … </section>
  </div>
</main>
```
The mascot/bolt zone remains the first thing on Figure Maker (it's the page's character greeting); the full-width input panel sits directly beneath it, still above the two-column work area.

### Book Builder
Already full-width single-column — no layout lift needed. The Section C restructure (shared card first in Step 1) already delivers the full-width top placement.

### CSS for full-width placement
- The panel is a plain block child of `cg-main` / `fm-main`, so it spans the full content width those containers already define (same max-width/padding as the grid below it) — it lines up flush with the columns, matching Book Builder.
- Add spacing between the full-width panel and the grid beneath it: `margin-bottom: 1.5rem` (match the existing `gap` of `.cg-layout` / `.fm-layout`). Put this on `#sharedInputsPanel` when it sits directly in `cg-main`/`fm-main`, or via a small `.cg-main > .shared-inputs-panel { margin-bottom: 1.5rem }` rule in each page's CSS.
- No width overrides needed; do not set an explicit width on the panel.

This placement change is **HTML-move + minor CSS only** — element IDs are unchanged, so all JS (sync, generate, restore, reconciliation) is unaffected by the move itself.

---

## A. Canonical Markup Block

The block below is the single authoritative template. Copy it verbatim into all three pages, substituting the `{{...}}` tokens per the mapping table in Section B. Do not alter structure, class names, or heading text between pages.

```html
<!-- ═══════════════════════════════════════════════════════════════
     CANONICAL SHARED INPUTS PANEL — COPY VERBATIM INTO ALL 3 PAGES
     Substitute {{...}} tokens per the per-tab mapping table.
     Keep this comment marker so the block is easy to locate.
     ═══════════════════════════════════════════════════════════════ -->
<div class="shared-inputs-panel builder-step" id="sharedInputsPanel"
     style="border-left: 5px solid var(--teal)">

  <div class="step-header">
    <h2>Your Story</h2>
    <span class="sync-badge" tabindex="0"
          title="Editing here updates Character Generator, Book Builder, and Figure Maker"
          aria-label="Synced across Character Generator, Book Builder, and Figure Maker">
      <svg class="sync-icon" aria-hidden="true" focusable="false"
           width="13" height="13" viewBox="0 0 24 24"
           fill="none" stroke="currentColor"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      Synced across tabs
    </span>
  </div>

  <p class="hint shared-tab-hint" id="sharedTabHint">
    {{TAB_HINT}}
  </p>

  <!-- CHARACTER DESCRIPTION -->
  <div class="control-group {{CHARACTER_PRIMARY_CLASS}}" id="{{CHARACTER_GROUP_ID}}">
    <label for="{{CHARACTER_ID}}">Character Description</label>
    <textarea
      id="{{CHARACTER_ID}}"
      rows="3"
      placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
      aria-describedby="{{CHARACTER_HINT_ID}}"
    ></textarea>
    <p class="hint" id="{{CHARACTER_HINT_ID}}">Who is the hero? Describe their look, personality, and any props.</p>
  </div>

  <!-- STORY PROMPT -->
  <div class="control-group {{STORY_PRIMARY_CLASS}}" id="{{STORY_GROUP_ID}}" style="margin-top: .9rem">
    <label for="{{STORY_ID}}">Story Prompt <span class="hint">{{STORY_LABEL_SUFFIX}}</span></label>
    <textarea
      id="{{STORY_ID}}"
      rows="{{STORY_ROWS}}"
      placeholder="A brave monkey king learns to share kindness with the forest…"
      aria-describedby="{{STORY_HINT_ID}}"
    ></textarea>
    <p class="hint" id="{{STORY_HINT_ID}}">The adventure or scenario your story is about.</p>
  </div>

  <!-- STYLE PROMPT -->
  <div class="control-group {{STYLE_PRIMARY_CLASS}}" id="{{STYLE_GROUP_ID}}" style="margin-top: .9rem">
    <label for="{{STYLE_ID}}">Style Prompt <span class="hint">{{STYLE_LABEL_SUFFIX}}</span></label>
    <textarea
      id="{{STYLE_ID}}"
      rows="2"
      placeholder="Soft watercolor, children's book art, warm pastel tones…"
      aria-describedby="{{STYLE_HINT_ID}}"
    ></textarea>
    <p class="hint" id="{{STYLE_HINT_ID}}">The visual art style used across all illustrations.</p>
  </div>

</div>
<!-- END CANONICAL SHARED INPUTS PANEL -->
```

### Canonical label text (reconciled across tabs)

| Field | Canonical label | Sub-label / suffix |
|---|---|---|
| Character Description | `Character Description` | _(none — always fully shown)_ |
| Story Prompt | `Story Prompt` | `(optional — sets scene context)` on CG and FM; _(no suffix)_ on BB |
| Style Prompt | `Style Prompt` | `(applied to all illustrations)` on BB; `(optional)` on CG and FM |

### Canonical placeholder strings (one per field, identical on all three pages)

| Field | Canonical placeholder |
|---|---|
| Character Description | `A brave young monkey king with golden fur, red cape, and a mischievous grin…` |
| Story Prompt | `A brave monkey king learns to share kindness with the forest…` |
| Style Prompt | `Soft watercolor, children's book art, warm pastel tones…` |

**Inconsistencies resolved:** Character Generator used `"A brave young monkey king…"` for Character but `"e.g. Standing at the entrance of a magic cave…"` for Story. Figure Maker used `"A roaring T-Rex…"` for Character and `"e.g. A jungle adventure story…"` for Story. Book Builder used `"Sun Wukong learns to share…"` for Story and `"Describe the visual style for all illustrations…"` for Style. The canonical placeholders above adopt the monkey-king theme consistently (matching the app's identity) and remove the `"e.g."` prefix pattern, which was inconsistent.

---

## B. Per-Tab Token Mapping

### Character Generator

| Token | Value |
|---|---|
| `{{TAB_HINT}}` | `Character Generator uses Character most — Story adds scene context, Style sets the art.` |
| `{{CHARACTER_ID}}` | `cgDescInput` |
| `{{CHARACTER_GROUP_ID}}` | `cgDescGroup` |
| `{{CHARACTER_HINT_ID}}` | `cgDescHint` |
| `{{CHARACTER_PRIMARY_CLASS}}` | `shared-field-primary` |
| `{{STORY_ID}}` | `cgStoryInput` |
| `{{STORY_GROUP_ID}}` | `cgStoryGroup` |
| `{{STORY_HINT_ID}}` | `cgStoryHint` |
| `{{STORY_PRIMARY_CLASS}}` | _(empty — no class added)_ |
| `{{STORY_LABEL_SUFFIX}}` | `(optional — sets scene context)` |
| `{{STORY_ROWS}}` | `2` |
| `{{STYLE_ID}}` | `cgStyleInput` |
| `{{STYLE_GROUP_ID}}` | `cgStyleGroup` |
| `{{STYLE_HINT_ID}}` | `cgStyleHint` |
| `{{STYLE_PRIMARY_CLASS}}` | _(empty)_ |
| `{{STYLE_LABEL_SUFFIX}}` | `(optional)` |

**Per-tab emphasis:** Character Description carries `shared-field-primary`.

### Figure Maker

| Token | Value |
|---|---|
| `{{TAB_HINT}}` | `Figure Maker uses Character most — it drives what Bolt builds. Style and Story add detail.` |
| `{{CHARACTER_ID}}` | `fmPromptInput` |
| `{{CHARACTER_GROUP_ID}}` | `fmPromptGroup` |
| `{{CHARACTER_HINT_ID}}` | `fmPromptHint` |
| `{{CHARACTER_PRIMARY_CLASS}}` | `shared-field-primary` |
| `{{STORY_ID}}` | `fmStoryInput` |
| `{{STORY_GROUP_ID}}` | `fmStoryGroup` |
| `{{STORY_HINT_ID}}` | `fmStoryHint` |
| `{{STORY_PRIMARY_CLASS}}` | _(empty)_ |
| `{{STORY_LABEL_SUFFIX}}` | `(optional — adds context)` |
| `{{STORY_ROWS}}` | `2` |
| `{{STYLE_ID}}` | `fmStyleInput` |
| `{{STYLE_GROUP_ID}}` | `fmStyleGroup` |
| `{{STYLE_HINT_ID}}` | `fmStyleHint` |
| `{{STYLE_PRIMARY_CLASS}}` | _(empty)_ |
| `{{STYLE_LABEL_SUFFIX}}` | `(optional)` |

**Per-tab emphasis:** Character Description carries `shared-field-primary`.

**Note on `maxlength`:** The current `fmPromptInput` has `maxlength="500"`. Retain this attribute on the substituted `{{CHARACTER_ID}}` in Figure Maker only — it is a Meshy API constraint, not a shared concern.

### Book Builder

| Token | Value |
|---|---|
| `{{TAB_HINT}}` | `Book Builder uses Story most — it drives the whole storybook. Character keeps art consistent across pages.` |
| `{{CHARACTER_ID}}` | `characterInput` |
| `{{CHARACTER_GROUP_ID}}` | `sharedCharacterGroup` |
| `{{CHARACTER_HINT_ID}}` | `sharedCharacterHint` |
| `{{CHARACTER_PRIMARY_CLASS}}` | _(empty)_ |
| `{{STORY_ID}}` | `conceptInput` |
| `{{STORY_GROUP_ID}}` | `sharedStoryGroup` |
| `{{STORY_HINT_ID}}` | `sharedStoryHint` |
| `{{STORY_PRIMARY_CLASS}}` | `shared-field-primary` |
| `{{STORY_LABEL_SUFFIX}}` | _(empty — no suffix span)_ |
| `{{STORY_ROWS}}` | `4` |
| `{{STYLE_ID}}` | `stylePromptInput` |
| `{{STYLE_GROUP_ID}}` | `sharedStyleGroup` |
| `{{STYLE_HINT_ID}}` | `sharedStyleHint` |
| `{{STYLE_PRIMARY_CLASS}}` | _(empty)_ |
| `{{STYLE_LABEL_SUFFIX}}` | `(applied to all illustrations)` |

**Per-tab emphasis:** Story Prompt carries `shared-field-primary` (it drives decomposition).

**Inconsistency resolved:** Book Builder currently places Story first and Character second, reversing the field order from the other two tabs. The canonical block enforces Character → Story → Style on all three pages. Because the JS refs use IDs (not position), `conceptInput`, `characterInput`, and `stylePromptInput` remain fully functional after reordering — no JS changes needed for the order swap itself.

---

## C. Book Builder Step 1 Restructure

### Current structure of `#step1` (before)

```
section#step1  (.builder-step)
  div.step-header
    span.step-num ①
    h2 "Story Concept"
    div.project-actions        ← Save/Load/Clear buttons inline in header
  div.control-group            ← Language toggle, no card wrapper
  div.shared-inputs-inline     ← Flat wrapper, no card/border
    p.shared-tab-hint
    div.sync-badge-row         ← Separate row just for the badge
      span.sync-badge
    div.control-group (Story)  ← shared-field-primary
    div.control-group (Character) ← shared-field-primary
    div.control-group (Style)
      div#stylePresets         ← style preset pills
  div.decompose-btn-row
  ...
```

### Target structure of `#step1` (after)

```
section#step1  (.builder-step)
  div.step-header                     ← contains ONLY step number + title
    span.step-num ①
    h2 "Story Concept"

  ──────────────────────────────────
  div.shared-inputs-panel.builder-step  ← CANONICAL BLOCK (first interactive content)
    (border-left: 5px solid var(--teal))
    div.step-header
      h2 "Your Story"
      span.sync-badge                 ← badge lives in step-header, margin-left: auto
    p.shared-tab-hint
    div.control-group (Character)     ← field order: Character first
    div.control-group (Story)         ← shared-field-primary
    div.control-group (Style)
  ──────────────────────────────────

  div.bb-tab-controls.builder-step    ← NEW: tab-specific card, matches cgTabControls/fmTabControls pattern
    (border-left: 5px solid var(--mustard))
    div.control-group                 ← Language toggle
      label "Language"
      div.lang-toggle
    div.project-actions-group         ← Save/Load/Clear, reparented here
      button#saveProjectBtn
      label[for=loadProjectFile]
      input#loadProjectFile
      button#clearProjectBtn

  div.decompose-btn-row               ← unchanged position (after both cards)
  ...
```

**Project actions:** Currently these live inside the `step-header` flex row via `margin-left: auto`. In the new structure they move into the `bb-tab-controls` card. The `project-actions` div and `project-btn` class remain — they just sit inside the new card rather than the header. The `saveProjectBtn` `disabled` state is unchanged.

**Classes to retire from `style.css` and usage:**

| Class | Action |
|---|---|
| `.shared-inputs-inline` | Remove from HTML and CSS (replaced by `.shared-inputs-panel.builder-step` on BB) |
| `.sync-badge-row` | Remove from HTML and CSS (badge now lives inside `.step-header` with `margin-left: auto`, matching CG/FM) |
| `.shared-style-presets` | Remove from CSS once the preset `div` elements are deleted (see Section D). Verify nothing else in the codebase uses this class before deleting the rule. |

---

## I. JS Unification — `SharedInputs.bindFields` (Option D, approved)

To remove the ~110 lines of triplicated, divergent sync logic (each page re-implements `restoreSharedInputs()` + `wireSharedInputListeners()` + an `onExternalChange` handler), the sync layer is consolidated into ONE configurable function on the existing `shared_inputs.js` global. Element IDs are **not** changed — pages pass their own IDs in.

### API (add to `shared_inputs.js`)
```js
// map  = { character: '<id>', story: '<id>', style: '<id>' }
// opts = { debounce: 300, populate: true, onRemote: (vals) => {} }
// returns { repopulate }
SharedInputs.bindFields(map, opts)
```
Behavior:
- Resolves each field's element by id.
- If `populate !== false`: read the store and assign each `.value` directly (the "restore" step).
- Attaches an `input` listener per field that `patch()`es that field — debounced by `opts.debounce` ms, or immediate when `debounce === 0`.
- Registers ONE `onExternalChange` that assigns each `.value` **directly** (never dispatches synthetic `input` events), then calls `opts.onRemote(vals)` if provided.
- Returns `{ repopulate() }` so a page can re-apply the store after its own load logic.

### Per-tab usage
| Tab | Call | Notes |
|---|---|---|
| Character Generator | `SharedInputs.bindFields(CG_FIELD_MAP, { debounce: 300 })` | Finally *uses* the already-declared (dead) `CG_FIELD_MAP`. Replaces `restoreSharedInputs`/`wireSharedInputListeners`. No `onRemote` (presets gone). |
| Figure Maker | `window.SharedInputs.bindFields({ character:'fmPromptInput', story:'fmStoryInput', style:'fmStyleInput' }, { debounce: 300 })` | The chip-deactivation `input` listener on `fmPromptInput` stays local (separate listener). |
| Book Builder | `SharedInputs.bindFields({ character:'characterInput', story:'conceptInput', style:'stylePromptInput' }, { debounce: 0, populate: false })` | `debounce:0` preserves the no-debounce navigation guarantee. `populate:false` because BB populates via its own branch logic (restoreProject/restoreState/restoreSharedInputs); attach the live listener AFTER reconciliation, as today. |

### Required guardrails (must hold)
1. **Book Builder `debounce: 0`** — preserve "value persisted before navigation" (current behavior at the un-debounced listeners).
2. **Repopulate assigns `.value` directly** — no synthetic `input` events (would echo into the store / wipe Figure Maker chips).
3. **`.disabled` stays page-owned** — Figure Maker's `setInputsDisabled` keeps toggling `disabled`; `bindFields` never touches it.
4. **Reconciliation before listen** — Book Builder runs `sharedConflictsWithSaved` / gallery_id / Save-Load-Clear on the raw store and only attaches the live listener afterward.

This composes with the markup work below: markup stays as three hand-copied blocks (with the canonical comment marker); only the JS sync is consolidated. (A future PR may inject the markup from JS — deferred.)

---

## D. Style-Preset Removal

### Elements to delete from HTML

| Tab | Element to delete |
|---|---|
| Character Generator | `<div class="presets shared-style-presets" id="cgStylePresets" …>` and all its `<button>` children |
| Figure Maker | `<div class="presets shared-style-presets" id="fmStylePresets" …>` and all its `<button>` children |
| Book Builder (Step 1) | `<div class="presets shared-style-presets" id="stylePresets" …>` and all its `<button>` children |

Note: Book Builder Step 3's `#genStylePresets` (inside `#genStylePrompt`'s control group) is **out of scope** — do not touch it.

### JS handlers and restore logic to remove — flagged for architect/developer

The following JS is tightly coupled to the deleted DOM elements. All references must be removed. Leaving any of them will cause `querySelector`/`getElementById` to return `null` and throw at runtime.

**`character_generator.js`:**
- Line 18: `const cgStylePresets = document.getElementById('cgStylePresets');` — delete the declaration.
- Lines 99–118: The entire `cgStylePresets.addEventListener('click', …)` handler block — delete it.
- Lines 175–177 inside `restoreSharedInputs()`: The `cgStylePresets.querySelectorAll('.preset').forEach(…)` loop that restores the active pill — delete these lines.
- Lines 204–207 inside `wireSharedInputListeners()` → `SharedInputs.onExternalChange()` callback: The `cgStylePresets.querySelectorAll('.preset').forEach(…)` loop — delete these lines.

**`figure_maker.js`:**
- Line 22: `const fmStylePresets = document.getElementById('fmStylePresets');` — delete the declaration.
- Lines 261–276: The entire `fmStylePresets.addEventListener('click', …)` handler block — delete it.
- Lines 224–226 inside `restoreSharedInputs()`: The `fmStylePresets.querySelectorAll('.preset').forEach(…)` loop — delete these lines.
- Lines 254–257 inside `wireSharedInputListeners()` → `SharedInputs.onExternalChange()` callback: The `fmStylePresets.querySelectorAll('.preset').forEach(…)` loop — delete these lines.
- `saveFmDraft()` at line 169: This function does **not** currently save the style pill (it only saves `chip` — the quick-idea chips). No change needed here.

**`book_builder.js`:**
- Line 120: `const step1StylePresets = document.getElementById('stylePresets');` — delete the declaration.
- Lines 215–225: The entire `step1StylePresets.addEventListener('click', …)` handler block — delete it.
- Lines 1162–1164 inside `restoreSharedInputs()`: The `step1StylePresets.querySelectorAll('.preset').forEach(…)` loop — delete these lines.
- Lines 1173–1175 inside `wireSharedInputListeners()` → `SharedInputs.onExternalChange()` callback: The `step1StylePresets.querySelectorAll('.preset').forEach(…)` loop — delete these lines.

**`saveCgDraft` audit:** The function at line 137 of `character_generator.js` does not save pill state — it only saves `model` and `ar`. No change needed.

---

## E. States

### Textarea states (apply to all three fields across all three tabs)

| State | Visual |
|---|---|
| **Default / empty** | `background: var(--ctrl-bg)` (`#0f1129`), `border: 1px solid var(--border)` (`rgba(255,255,255,.10)`), placeholder text in `var(--muted)` (`rgba(255,255,255,.50)`) |
| **Filled / idle** | Same border as default; text in `var(--ink)` (`#ffffff`) |
| **Hover** | No border change at rest (the current CSS does not define a distinct hover on textareas — this is acceptable; do not introduce a new hover rule) |
| **Focus** | `border-color: #ff6b35; box-shadow: 0 0 0 2px rgba(255,107,53,.35)` — already defined in `style.css` |
| **Primary emphasis (`shared-field-primary`)** | Label upgrades to `color: var(--ink); font-weight: 800`. Textarea gains `border-left-color: #ff6b35; border-left-width: 3px`. These rules already exist. |
| **Disabled (Figure Maker only)** | `figure_maker.js` calls `setInputsDisabled(true)` during a job, which sets `disabled` on the textareas. Disabled textareas receive browser-default reduced opacity. No new CSS needed — the existing `opacity` reduction from the browser is sufficient and consistent. |

### Sync badge

The badge is informational, not interactive in the functional sense. It uses `tabindex="0"` so keyboard users can reach it and read the `title`/`aria-label`. It does not change state dynamically. Visually: pill shape, `background: rgba(255,107,53,.15)`, text color `#ff6b35`, focus ring via `:focus-visible` with `outline: 2px solid #ff6b35`.

### Panel as a whole

The panel has no loading or error state of its own. It reflects whatever the textareas contain. The `aria-live` announcements for generation status belong to the downstream result areas (already implemented per page), not this panel.

---

## F. Accessibility

### Label associations
Every textarea has a `<label for="…">` pointing to its `id`. This is already the case in all three pages and must be preserved in the canonical block. The `<span class="hint">` inside the label (for optional suffix text) is acceptable — it is read as part of the label text by screen readers.

### Sub-labels / hint paragraphs
Each textarea has `aria-describedby="{{FIELD_HINT_ID}}"` pointing to the `<p class="hint">` below it. This provides supplementary context without polluting the label. Keep these associations in the canonical block.

### Heading / landmark
The panel's `<h2>Your Story</h2>` inside `.step-header` gives it a heading landmark. Because the panel is a `<div>` (not a `<section>`), it does not create its own sectioning context — it inherits the page's `<main>` landmark. With the full-width placement (see Layout & Placement), the panel is now a top-level block at the top of `<main>` (not nested in a controls column) — which makes it even more clearly the page's first content. Keep it a `<div>`; do not add `role="region"` or `aria-labelledby`.

### Focus order
The panel must be the first interactive content after the skip link and header navigation. On Book Builder, the current Step 1 opens with the step header then immediately the language toggle. After restructuring, focus order becomes: skip link → header nav → `#step1` heading (non-interactive) → `sharedInputsPanel` (first textarea: `{{CHARACTER_ID}}`) → subsequent fields → then the `bb-tab-controls` card (language toggle, project actions). This is the correct reading and tab order: the shared inputs are the most important content and appear first.

### Sync badge ARIA
Current `aria-label`: `"These fields sync across all three tabs"`. Canonical value: `"Synced across Character Generator, Book Builder, and Figure Maker"`. This is more informative for screen reader users who may not know what "all three tabs" refers to. The `title` attribute (tooltip on hover for sighted users) keeps its current text.

### Contrast
All text uses `var(--ink)` (`#ffffff`) or `var(--muted)` (`rgba(255,255,255,.50)`) on `var(--ctrl-bg)` (`#0f1129`) or `var(--paper-dark)` (`#0f1129`). White on `#0f1129` exceeds WCAG AA by a large margin. Muted (`rgba(255,255,255,.50)`) on `#0f1129` renders approximately `#808080` on dark, which is borderline AA for normal text at `.72rem` — this is existing system behavior shared across all hint text in the app and is not introduced by this change. The `shared-field-primary` label at `color: var(--ink); font-weight: 800` improves contrast for the primary field labels specifically.

### Keyboard navigation inside the panel
Tab order within the panel: `h2` (non-interactive) → `sync-badge` (tabindex="0") → Character textarea → Story textarea → Style textarea. The sync badge receives focus before the textareas because it appears earlier in DOM order inside `.step-header`. This is acceptable — it is a brief informational stop and advances naturally with Tab.

---

## G. Responsive Behavior

The breakpoint is `@media (max-width: 700px)` across all three pages.

### Character Generator
With the full-width placement, the shared panel sits above `.cg-layout` and already spans full width, so mobile needs no special handling for it — it simply stays full-width as the two-column `.cg-layout` below collapses to single-column. The `.cg-controls-panel` (now holding only the tab controls) unsticks and scrolls naturally. The panel's internal layout is purely vertical (flex-column), so it reflows without a presets row. The removed presets row previously added approximately 40px of height and a wrapping flex row — its removal slightly reduces height on mobile, which is an improvement. `padding: 1.5rem` on `.builder-step` reduces to `padding: 1.1rem .9rem` via the existing BB mobile rule; CG/FM do not have a mobile-specific `.builder-step` padding override (they use `cg-main` and `fm-main` padding). This is an **existing inconsistency** — it is not introduced by this change and is out of scope to fix here. Flag for a future CSS audit.

### Figure Maker
With the full-width placement, the shared panel sits above `.fm-layout` (under the mascot) and spans full width at all breakpoints. The two-column `.fm-layout` (7fr 4fr) collapses to single-column below it; `.fm-controls-panel` gets `order: -1` (moves above the viewer on mobile). No special mobile treatment needed for the shared panel.

### Book Builder
`builder-main` is single-column (flex-column) at all widths; it already uses `gap: 2rem` between cards. The new `bb-tab-controls` card stacks below the shared-inputs-panel just as the `cgTabControls`/`fmTabControls` cards do in CG/FM. At mobile, `padding: 1.1rem .9rem` applies to all `.builder-step` elements via the existing rule. No new mobile rules needed for the shared panel or the new tab-controls card.

### Sync badge at mobile
`style.css` already reduces the badge to `font-size: .68rem; padding: .22rem .5rem` at `max-width: 700px`. No change needed.

---

## H. CSS Changes in `style.css`

### Rules to add

**None.** All required classes — `.shared-inputs-panel`, `.builder-step`, `.step-header`, `.sync-badge`, `.shared-tab-hint`, `.shared-field-primary`, `.control-group` — already exist in `style.css`. Book Builder's shared-inputs block currently uses `.shared-inputs-inline` instead of `.shared-inputs-panel.builder-step`; switching the HTML class is sufficient to apply the card styling.

### Rules to retire

| Rule(s) | Location | Action |
|---|---|---|
| `.shared-inputs-inline { display: flex; flex-direction: column; }` | `style.css` lines 476–479 | Delete — no longer used on any page |
| `.sync-badge-row { display: flex; margin-bottom: .5rem; }` | `style.css` lines 480–483 | Delete — element removed from all pages |
| `.sync-badge-row .sync-badge { margin-left: 0; }` | `style.css` lines 484–487 | Delete — element removed |
| `.shared-style-presets { … }` | If a dedicated rule exists — search `style.css` for `.shared-style-presets`. Currently the class appears only in HTML; the preset container uses the base `.presets` rule. If no separate `.shared-style-presets` rule exists in `style.css`, no deletion needed. The class attribute itself is removed with the deleted HTML elements. |

### Rule to add in `book_builder.css`

The new `bb-tab-controls` card needs a class. Use the existing `.fm-controls-card` pattern as the model — but rather than copying that class (it is Figure Maker-specific), add a single shared modifier or name the element with a BB-scoped class:

```
/* book_builder.css — add */
.bb-tab-controls {
  /* All visual treatment comes from .builder-step (background, border, radius, padding).
     Only tab-specific overrides go here. */
  border-left: 5px solid var(--mustard);
  margin-top: 1rem;
}
```

Alternatively, the developer may apply the border inline as done for `cgTabControls` and `fmTabControls` (`style="border-left: 5px solid var(--mustard); margin-top: 1rem"`). Both are acceptable; the inline approach matches the existing CG/FM pattern exactly.

---

## Inconsistency Audit — Current vs. Canonical

The following divergences exist between the three current implementations. The canonical block resolves them all.

| # | Inconsistency | CG | FM | BB | Resolution |
|---|---|---|---|---|---|
| 1 | **Field order** | Character → Story → Style | Character → Story → Style | Story → Character → Style | Canonical: Character → Story → Style everywhere |
| 2 | **Story rows** | `rows="2"` | `rows="2"` | `rows="4"` | Keep `rows="4"` for BB (Story is the primary field there); `rows="2"` for CG and FM |
| 3 | **Character placeholder** | Monkey king | T-Rex | Monkey king | Canonical: monkey king (brand-consistent) |
| 4 | **Story placeholder** | "e.g. Standing at…" | "e.g. A jungle…" | "Sun Wukong learns…" | Canonical: "A brave monkey king learns…" (no "e.g." prefix, brand-consistent) |
| 5 | **Style placeholder** | "Soft watercolor…" | "Soft watercolor…" | "Describe the visual style…" | Canonical: "Soft watercolor, children's book art, warm pastel tones…" |
| 6 | **Style label suffix** | No label suffix (label is bare "Style Prompt") | `(optional)` | `(applied to all illustrations)` | Retain per-tab suffixes — they are contextually accurate |
| 7 | **Primary emphasis** | Character + Style both get `shared-field-primary` | Character only | Story + Character both get `shared-field-primary` | Canonical: one primary field per tab — CG: Character; FM: Character; BB: Story |
| 8 | **Sync badge position** | Inside `step-header` with `margin-left: auto` | Inside `step-header` with `margin-left: auto` | In a separate `.sync-badge-row` div below the header | Canonical: always inside `step-header` with `margin-left: auto` |
| 9 | **Card / border treatment** | `shared-inputs-panel builder-step` + teal left border | Same | `shared-inputs-inline` — no card, no border | Canonical: `shared-inputs-panel builder-step` + teal left border on all three |
| 10 | **Tab hint copy** | Mentions Character and Style, no Story emphasis | Mentions Character first | Mentions Story and Character | Per-tab hints retained (see Section B); wording updated to be consistent in voice |
| 11 | **`aria-label` on sync badge** | `"These fields sync across all three tabs"` | `"These fields sync across all three tabs"` | `"These fields sync across all three tabs"` | Canonical: `"Synced across Character Generator, Book Builder, and Figure Maker"` |
| 12 | **Style hint copy** | "The visual art style for the portrait." | "The visual style (also used by Character Generator and Book Builder)." | "The art style used for every page image." | Canonical: "The visual art style used across all illustrations." (neutral, works on all tabs) |
| 13 | **Character hint copy** | "Appearance, personality, and any props or outfit details." | "Describe what you want to build — this is what Bolt will design." | "Who is the main character? Appearance, personality, key props." | Canonical: "Who is the hero? Describe their look, personality, and any props." — FM note: retain a secondary line below via `aria-describedby` if the Bolt branding is important, but the visible label hint uses the canonical text |
