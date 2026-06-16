# Unified Inputs — Collapsible "More Options" Spec

**Scope:** Restructure the shared "Your Story" inputs panel on Character Generator, Book Builder, and Figure Maker so that the block is literally identical HTML (no `{{token}}` substitutions). Character Description is always visible; Story Prompt and Style Prompt are hidden inside a collapsible section, collapsed by default.
**Status:** Spec only — implementation by developer-agent.
**Supersedes:** The canonical block in `design-specs/unified-inputs-header.md` Section A/B. All other sections of that spec (layout placement, JS unification, preset removal, CSS retirement, accessibility) remain authoritative and are not repeated here.
**Branch context:** `feature/figure-maker-settings-gallery-split`

---

## 1. Decision: `<details>/<summary>` vs. button-toggle

**Decision: use `<details>/<summary>`.**

Rationale:
- The app has an existing CSS precedent for this exact interaction — the now-removed import section used `.import-section` / `.import-summary` with a rotating `▸` marker, and `style.css` already has `.toggle-label` / `.toggle-arrow` with a `transform: rotate(90deg)` rule on `.toggle-label.open`. The `<details>` pattern is the native version of that pattern with zero JS required for open/close.
- `<details>` provides built-in keyboard operability (Space/Enter on `<summary>` toggles), correct `open` attribute semantics that CSS can hook, and correct screen-reader announcements (the element is discoverable and its expanded/collapsed state is conveyed without any `aria-expanded` bookkeeping).
- The button-toggle with `aria-expanded`/`aria-controls` is strictly more code for the same result on this particular case. There is no need to control the open state from JS on user interaction — JS only needs to force-open on load when content exists (see Section 4). Calling `detailsEl.open = true` is simpler than toggling an `aria-expanded` attribute and a CSS class.
- The only trade-off: `<details>` open/close animation requires a CSS workaround (it cannot animate `height: auto` natively). The spec addresses this with a `max-height` transition in Section 8.

---

## 2. ID Standardization — the prerequisite for a literal identical block

The current block uses per-page IDs for the three textarea fields. For the block to be copy-paste identical, those IDs must be unified.

### Old → new mapping

| Page | Field | Old element ID | Old group ID | New element ID | New group ID |
|---|---|---|---|---|---|
| Character Generator | Character | `cgDescInput` | `cgDescGroup` | `sharedCharacterInput` | `sharedCharacterGroup` |
| Character Generator | Story | `cgStoryInput` | `cgStoryGroup` | `sharedStoryInput` | `sharedStoryGroup` |
| Character Generator | Style | `cgStyleInput` | `cgStyleGroup` | `sharedStyleInput` | `sharedStyleGroup` |
| Figure Maker | Character | `fmPromptInput` | `fmPromptGroup` | `sharedCharacterInput` | `sharedCharacterGroup` |
| Figure Maker | Story | `fmStoryInput` | `fmStoryGroup` | `sharedStoryInput` | `sharedStoryGroup` |
| Figure Maker | Style | `fmStyleInput` | `fmStyleGroup` | `sharedStyleInput` | `sharedStyleGroup` |
| Book Builder | Character | `characterInput` | `sharedCharacterGroup` | `sharedCharacterInput` | `sharedCharacterGroup` |
| Book Builder | Story | `conceptInput` | `sharedStoryGroup` | `sharedStoryInput` | `sharedStoryGroup` |
| Book Builder | Style | `stylePromptInput` | `sharedStyleGroup` | `sharedStyleInput` | `sharedStyleGroup` |

Hint paragraph IDs also standardize: `sharedCharacterHint`, `sharedStoryHint`, `sharedStyleHint`. The `<details>` toggle element gets `id="sharedMoreOptions"`.

**Implementation cost for the developer (flag for architect):**

Every JS reference to the old IDs must be updated. These are the sites:

`character_generator.js`:
- Line 9: `CG_FIELD_MAP` object — update all three values.
- Lines 15–17: `getElementById` calls for `cgDescInput`, `cgStoryInput`, `cgStyleInput` — rename the const names and IDs.
- Lines 211–213: `cgDescInput.value`, `cgStoryInput.value`, `cgStyleInput.value` reads — update const names.
- Lines 336–337: `.value` reads on save-to-gallery — update const names.
- Any validation that reads `cgDescInput` (focus on empty, border flash) — update.

`figure_maker.js`:
- Lines 19–21: `getElementById` calls for `fmPromptInput`, `fmStoryInput`, `fmStyleInput` — rename.
- `wireSharedInputListeners` inline map — update IDs.
- Lines referencing `fmPromptInput.value` for generation, validation, and `setInputsDisabled` calls — update const names. Note: the `maxlength="500"` attribute on the Character textarea stays in the shared HTML block on Figure Maker only — see Section 3 note below.
- `setInputsDisabled` function — update any direct `getElementById` calls or const references.

`book_builder.js`:
- Lines 39–41: `getElementById` calls for `conceptInput`, `characterInput`, `stylePromptInput` — rename consts.
- `bindFields` map at line 1050 — update IDs.
- All `conceptInput.value`, `characterInput.value`, `stylePromptInput.value` reads (there are many — `saveState`, `restoreProject`, `restoreState`, `restoreSharedInputs`, `SharedInputs.patch` blocks in init, `autoGenBtn` click handler) — update const names.
- Line 998–999 in `saveState`: `concept: conceptInput.value.trim()` key name may stay `concept` in the saved JSON schema (that is a data key, not a DOM ID) — only the DOM const name changes.

**Breadth note:** The BB rename is the highest-risk part. `characterInput`, `conceptInput`, and `stylePromptInput` appear approximately 34 times across `book_builder.js`. The architect should consider whether a simple find-replace-const approach is safe or whether a line-by-line audit is warranted given `conceptInput` → `sharedStoryInput` is a semantic rename (the underlying store key `concept`/`story` is separate from the DOM ID).

### Consequence: bindFields maps become identical

With standardized IDs, every page's `bindFields` call becomes:
```js
SharedInputs.bindFields(
  { character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' },
  { /* page-specific opts */ }
);
```
The per-page maps no longer differ in keys or values. The opts (`debounce`, `populate`) remain per-page as today.

---

## 3. The Canonical Markup Block

This block is the single source of truth. It replaces the current per-page blocks verbatim. There are NO substitution tokens — copy it identically into all three pages.

The only per-page HTML differences that survive are:
- The `<p class="hint shared-tab-hint">` text (the tab hint line below the "Your Story" heading) — this one line differs by page; see Section 6.
- `maxlength="500"` on `#sharedCharacterInput` — present on Figure Maker only (Meshy API constraint). The other two pages omit it.

```html
<!-- ═══════════════════════════════════════════════════════════════
     CANONICAL SHARED INPUTS PANEL — IDENTICAL ON ALL 3 PAGES
     Character Description is always visible.
     Story Prompt + Style Prompt are inside the collapsible <details>.
     The only per-page difference: the .shared-tab-hint text.
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

  <!-- TAB HINT — only this line differs per page; see Section 6 for each page's text -->
  <p class="hint shared-tab-hint" id="sharedTabHint">
    {{TAB_HINT — see Section 6}}
  </p>

  <!-- CHARACTER DESCRIPTION — always visible, primary field -->
  <div class="control-group shared-field-primary" id="sharedCharacterGroup">
    <label for="sharedCharacterInput">Character Description</label>
    <textarea
      id="sharedCharacterInput"
      rows="3"
      placeholder="A brave young monkey king with golden fur, red cape, and a mischievous grin…"
      aria-describedby="sharedCharacterHint"
    ></textarea>
    <p class="hint" id="sharedCharacterHint">Who is the hero? Describe their look, personality, and any props.</p>
  </div>

  <!-- COLLAPSIBLE: Story Prompt + Style Prompt -->
  <details class="shared-more-options" id="sharedMoreOptions">
    <summary class="shared-more-summary">
      <span class="shared-more-arrow" aria-hidden="true">▸</span>
      More options
      <span class="shared-more-label-detail">(story &amp; style)</span>
    </summary>

    <div class="shared-more-body">

      <!-- STORY PROMPT -->
      <div class="control-group" id="sharedStoryGroup">
        <label for="sharedStoryInput">Story Prompt <span class="hint">(optional)</span></label>
        <textarea
          id="sharedStoryInput"
          rows="3"
          placeholder="A brave monkey king learns to share kindness with the forest…"
          aria-describedby="sharedStoryHint"
        ></textarea>
        <p class="hint" id="sharedStoryHint">The adventure your story is about — leave blank and Claude will invent one.</p>
      </div>

      <!-- STYLE PROMPT -->
      <div class="control-group" id="sharedStyleGroup">
        <label for="sharedStyleInput">Style Prompt <span class="hint">(optional)</span></label>
        <textarea
          id="sharedStyleInput"
          rows="2"
          placeholder="Soft watercolor, children's book art, warm pastel tones…"
          aria-describedby="sharedStyleHint"
        ></textarea>
        <p class="hint" id="sharedStyleHint">The visual art style used across all illustrations.</p>
      </div>

    </div><!-- /.shared-more-body -->
  </details>

</div>
<!-- END CANONICAL SHARED INPUTS PANEL -->
```

**Note on `maxlength`:** The developer must add `maxlength="500"` to `#sharedCharacterInput` on `figure_maker.html` only, after the paste. This is the sole attribute that diverges.

**Note on Story `rows`:** The previous spec used `rows="4"` for Book Builder's Story field. With Story now collapsed and optional everywhere (including BB, per the new backend behavior), `rows="3"` is used uniformly — the collapsed state means the space saved by 4 vs 3 rows is irrelevant, and 3 rows is adequate for the optional/supplementary role Story now plays.

---

## 4. Field Emphasis — `shared-field-primary` Placement

**Decision: Character Description carries `shared-field-primary` on all three pages.**

This is already true for CG and FM. The change affects Book Builder only, where Story Prompt currently carries `shared-field-primary`.

Because Story Prompt is now hidden behind the collapsible by default, applying `shared-field-primary` to it would be invisible on load. Character is the always-visible field and the starting point for all three workflows — it is the correct primary on all pages. The `.shared-field-primary` class (bold label, orange left border on the textarea) stays on `#sharedCharacterGroup` in the identical block above.

The previous spec noted BB's emphasis on Story was intentional (Story drives decomposition). That reasoning holds for the *workflow*, but the *visual emphasis* must match the *visible* primary field. BB's generate button is already the action that commits the Story value to Claude; the primary-field marker on the Character textarea is not misleading.

**No new CSS is needed.** The `.shared-field-primary` rules already exist in `style.css` (lines 483–491).

---

## 5. Auto-Expand When Content Exists

### Rule

After the shared inputs are populated on load, check whether `#sharedStoryInput` or `#sharedStyleInput` has a non-empty `.value`. If either does, set `document.getElementById('sharedMoreOptions').open = true`. This ensures users are never misled into thinking those fields are empty when they contain synced or restored content.

### Where the check runs

A small helper function is needed — call it `autoExpandIfContent()`. It reads `.value` on both textareas and sets `.open` if either is non-empty:

```js
function autoExpandIfContent() {
  var story = document.getElementById('sharedStoryInput');
  var style = document.getElementById('sharedStyleInput');
  var details = document.getElementById('sharedMoreOptions');
  if (details && ((story && story.value.trim()) || (style && style.value.trim()))) {
    details.open = true;
  }
}
```

### When to call it — per page

**Character Generator and Figure Maker:** Call `autoExpandIfContent()` immediately after `SharedInputs.bindFields(...)` returns (which populates the fields if `populate !== false`). These pages have no reconciliation branches — population is synchronous, so one call at the end of `wireSharedInputListeners()` (or directly after it in the init flow) is sufficient.

Also call it inside the `onRemote` callback passed to `bindFields`, so that if Story/Style arrive from another tab while the page is open, the section auto-expands then too:

```js
SharedInputs.bindFields(
  { character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' },
  {
    debounce: 300,
    onRemote: function() { autoExpandIfContent(); }
  }
);
autoExpandIfContent(); // after bindFields populates
```

**Book Builder:** BB uses `populate: false` and populates via its own reconciliation branches (`restoreProject`, `restoreState`, `restoreSharedInputs`). Call `autoExpandIfContent()` at the end of EACH reconciliation branch — specifically at any point where values are assigned to the Story/Style fields. The four branches in the init IIFE are:

1. Gallery load success (`restoreProject` completes) — call after `restoreProject(project)` resolves.
2. Gallery load failure fallback → `restoreSharedInputs()` — call after `restoreSharedInputs()`.
3. Conflict kept previous (`restoreState(savedState)` + `SharedInputs.patch`) — call after `restoreState`.
4. Conflict discarded → `restoreSharedInputs()` — call after.
5. No conflict, saved state → `restoreState(savedState)` — call after.
6. No conflict, no saved state → `restoreSharedInputs()` — call after.

Additionally, call it inside the `onRemote` callback (same as CG/FM) so cross-tab updates auto-expand at runtime.

**Risk for the architect:** BB's `populate: false` means `bindFields` itself does not call `autoExpandIfContent()` via a post-populate hook. The developer must remember to call it after every branch that writes Story/Style values. A missed branch leaves Story/Style content invisible to the user. The safest implementation is to call `autoExpandIfContent()` once at the very end of the init IIFE, after `wireSharedInputListeners()` — at that point all branches have completed and `.value` reflects the final state. This is simpler and safer than per-branch calls.

---

## 6. Unified Copy

### Tab hint line (the one surviving per-page difference)

| Page | Text |
|---|---|
| Character Generator | `Character Generator uses Character most — Story and Style are optional extras.` |
| Figure Maker | `Figure Maker uses Character most — it drives what gets built. Story and Style add detail.` |
| Book Builder | `Book Builder works from all three fields — Character keeps art consistent, Story drives the plot, Style sets the look.` |

### Field labels and hints (identical across all pages)

| Field | Label | Sub-label suffix | Hint paragraph |
|---|---|---|---|
| Character Description | `Character Description` | _(none)_ | `Who is the hero? Describe their look, personality, and any props.` |
| Story Prompt | `Story Prompt` | `(optional)` | `The adventure your story is about — leave blank and Claude will invent one.` |
| Style Prompt | `Style Prompt` | `(optional)` | `The visual art style used across all illustrations.` |

### Changes from the previous spec (`unified-inputs-header.md`)

The previous spec kept per-tab label suffix variations (`"(optional — sets scene context)"` on CG, `"(optional — adds context)"` on FM, `"(applied to all illustrations)"` on BB for Style). With a fully identical block, only one label is possible per field. The unified `(optional)` on both Story and Style is accurate on all three pages: Story is optional everywhere (new backend behavior), and Style was already optional on CG/FM. The richer suffix context is now carried by the hint paragraph text (`"leave blank and Claude will invent one"`) which is more descriptive anyway.

### Collapsible summary label

```
▸ More options (story & style)
```

- "More options" is the action word — brief, neutral, not page-specific.
- "(story & style)" tells the user what's inside without opening it.
- The `▸` rotates to `▾` when expanded (CSS-driven, see Section 8).
- The label does not say "optional" — that's already on the field labels inside.
- All-lowercase `story & style` matches the conversational, kid-friendly tone of the app.

---

## 7. Visual Layout — ASCII Mockup

### Collapsed state (default on load with empty fields)

```
┌─────────────────────────────────────────────────────┐
│ Your Story                         [⟳ Synced across tabs] │
│ Character Generator uses Character most — Story and Style are optional extras. │
│                                                       │
│  CHARACTER DESCRIPTION                               │
│  ┌───────────────────────────────────────────────┐  │
│  │ A brave young monkey king with golden fur…    │  │
│  └───────────────────────────────────────────────┘  │
│  Who is the hero? Describe their look, personality,  │
│  and any props.                                      │
│                                                       │
│  ▸ More options (story & style)                      │  ← collapsed, user can click
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Expanded state (after click, or auto-expanded when content exists)

```
┌─────────────────────────────────────────────────────┐
│ Your Story                         [⟳ Synced across tabs] │
│ Character Generator uses Character most — Story and Style are optional extras. │
│                                                       │
│  CHARACTER DESCRIPTION                               │
│  ┌───────────────────────────────────────────────┐  │
│  │ A brave young monkey king with golden fur…    │  │
│  └───────────────────────────────────────────────┘  │
│  Who is the hero? Describe their look, personality,  │
│  and any props.                                      │
│                                                       │
│  ▾ More options (story & style)                      │  ← expanded
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│                                                       │
│  STORY PROMPT (optional)                             │
│  ┌───────────────────────────────────────────────┐  │
│  │ A brave monkey king learns to share kindness… │  │
│  └───────────────────────────────────────────────┘  │
│  The adventure your story is about — leave blank     │
│  and Claude will invent one.                         │
│                                                       │
│  STYLE PROMPT (optional)                             │
│  ┌───────────────────────────────────────────────┐  │
│  │ Soft watercolor, children's book art…         │  │
│  └───────────────────────────────────────────────┘  │
│  The visual art style used across all illustrations. │
│                                                       │
└─────────────────────────────────────────────────────┘
```

The `▸` / `▾` arrow is the only visual indicator that the section is expandable. There is no button border, no chevron icon, no underline — this matches the conversational style of the app. The summary row sits flush with the panel text (not inset or indented) so it reads as a natural continuation of the field stack.

---

## 8. CSS — Collapsible Rules

Add to `style.css` in the `/* ── Shared Inputs Panel ── */` block (after line 491 where `.shared-field-primary textarea` ends):

```css
/* ── Shared inputs collapsible (details/summary) ── */
.shared-more-options {
  margin-top: 1rem;
}

/* Remove the browser's default disclosure triangle on all engines */
.shared-more-options > summary {
  list-style: none;
}
.shared-more-options > summary::-webkit-details-marker {
  display: none;
}

.shared-more-summary {
  display: flex;
  align-items: center;
  gap: .4rem;
  cursor: pointer;
  user-select: none;
  font-size: .8rem;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: .04em;
  text-transform: uppercase;
  padding: .35rem 0;
  border-radius: 6px;
  /* No background — sits flush with panel text */
  transition: color .15s;
}
.shared-more-summary:hover {
  color: var(--ink);
}
.shared-more-summary:focus-visible {
  outline: 2px solid #ff6b35;
  outline-offset: 3px;
}

.shared-more-arrow {
  display: inline-block;
  font-size: .75rem;
  transition: transform .2s ease;
  /* ▸ at rest — rotates to point down when open */
}
.shared-more-options[open] .shared-more-arrow {
  transform: rotate(90deg);
}

.shared-more-label-detail {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  font-size: .78rem;
  color: var(--muted);
  opacity: .75;
}

/* Content area — animated reveal */
.shared-more-body {
  display: flex;
  flex-direction: column;
  gap: .9rem;
  padding-top: .75rem;
  /* Soft separator between the summary and the first field */
  border-top: 1px solid var(--border);
  margin-top: .35rem;

  /* Reveal animation via max-height trick.
     <details> cannot animate height:auto natively; max-height is the standard workaround.
     The closed state is handled by the browser hiding the <details> body when [open] is absent —
     we only need to animate the open direction. */
  animation: sharedMoreOpen .2s ease;
}

@keyframes sharedMoreOpen {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

**Design rationale for the summary styling:**
- Uppercase, muted, `.8rem` matches the label style on `.control-group label` (see `style.css` line 138) — the summary reads visually as a "field-category" row, consistent with the existing label treatment.
- The hover `color: var(--ink)` lift gives a clear affordance without adding a background box that would create a visual break in the panel card.
- `focus-visible` with the orange ring matches every other interactive element in the app.
- The `▸` character (U+25B8) was already used in the removed import section (`.import-summary` pattern) — reuse is consistent.

**Note on the `.control-group` `margin-top: .9rem` inline style:** The existing Story and Style groups had `style="margin-top: .9rem"` inline. Inside `.shared-more-body`, the `gap: .9rem` replaces those inline styles — remove the inline `style` attributes from both groups when they move inside the `<details>`. This is cleaner and the gap produces the same spacing.

---

## 9. Accessibility

### `<details>/<summary>` semantics

- `<details>` has an implicit ARIA role of `group`; `<summary>` has role `button` with `aria-expanded` inferred from the `[open]` attribute. This is native, correct, and requires no manual ARIA.
- Screen readers will announce something like "More options (story & style), collapsed, button" when the element is focused. Activating it (Enter or Space) toggles it.
- The collapsed textareas (`#sharedStoryInput`, `#sharedStyleInput`) remain in the DOM at all times, as required for sync and populate to work. They are hidden by the browser's default `display: none` on content inside a closed `<details>` — this means they are also removed from the accessibility tree when collapsed, so screen readers will not encounter them until the section is opened. This is the correct behavior and matches user expectation.
- `bindFields` in `shared_inputs.js` assigns `.value` directly, regardless of whether the element is inside an open or closed `<details>`. This is safe — DOM writes to hidden elements work normally in all browsers, and the value will be visible once the user opens the section (or once `autoExpandIfContent()` opens it on load).

### Keyboard navigation

Focus order inside the panel:
1. `#sharedCharacterInput` textarea (first interactive element after the sync badge)
2. `<summary>` of `#sharedMoreOptions` (next in tab order after the character hint paragraph)
3. When expanded: `#sharedStoryInput`, then `#sharedStyleInput`

The `<summary>` is natively keyboard-operable (Space and Enter toggle). No `tabindex` changes needed.

### Focus after expand

When the user keyboard-activates the summary to expand the section, focus remains on the `<summary>` element (browser default). The textareas inside become reachable by subsequent Tab presses. This is correct — no JS focus management is needed.

### Screen reader notes

- The `▸` arrow character is marked `aria-hidden="true"` so it is not read aloud.
- The visible text "More options (story & style)" is the accessible name of the summary/button — it is descriptive enough that no additional `aria-label` is needed.
- The hint paragraphs (`#sharedStoryHint`, `#sharedStyleHint`) are still connected to their textareas via `aria-describedby` — this works even when the elements are collapsed because the association is resolved at the time the user focuses the textarea (which can only happen once the section is open).

---

## 10. Interaction States Summary

| State | Trigger | Visual |
|---|---|---|
| **Collapsed (default)** | Page load with empty Story + Style | Character textarea visible; summary row shows `▸ More options (story & style)` in muted uppercase |
| **Auto-expanded on load** | Story or Style has content on populate | `<details open>` set before first paint (no animation jank — set via JS before render completes) |
| **Hovered (summary)** | Mouse over summary | `color` lifts from `var(--muted)` to `var(--ink)` |
| **Focused (summary)** | Keyboard tab to summary | Orange `outline: 2px solid #ff6b35` ring, `outline-offset: 3px` |
| **Expanded (user action)** | Click or Space/Enter on summary | `▸` rotates 90deg to `▾`; `.shared-more-body` fades in with 200ms opacity+translateY animation |
| **Collapsed (user action)** | Click or Space/Enter on open summary | `▾` rotates back; browser hides body instantly (no closing animation — acceptable) |
| **Auto-expanded (runtime)** | `onRemote` callback fires with Story/Style content from another tab | `details.open = true` set; if already open, no change |
| **Textarea focus** | Tab into or click any textarea | Orange border + glow (existing `style.css` rules) |
| **Character empty, generate clicked** | Validation (page-specific) | Character border flashes `var(--terracotta)`, focus moves to `#sharedCharacterInput` (unchanged from current behavior) |

---

## 11. Risks and Open Questions for the Architect

1. **ID rename breadth.** `conceptInput` appears in approximately 34 places in `book_builder.js` including the `saveState` JSON key name `concept`. The JSON key `concept` in the persisted `LS_KEY` state is a data schema concern, not a DOM concern — the developer must rename the const (`conceptInput` → `sharedStoryInput`) but NOT rename the JSON key `concept` in `saveState`/`restoreState` (that would break existing saved books in localStorage). These are different things and must not be conflated.

2. **BB `populate: false` + auto-expand timing.** Because Book Builder populates fields via its own async reconciliation (including an `await fetch(...)` for the gallery path), `autoExpandIfContent()` cannot be called synchronously after `bindFields`. The recommended approach (call once at the end of the init IIFE, after all branches and after `wireSharedInputListeners()`) relies on the init IIFE being the last thing that modifies the field values. Confirm this is true — specifically, check whether `restoreProject` or `restoreState` do any async post-processing that sets Story/Style values after the IIFE's `await` chain completes.

3. **`<details>` animation limitation.** Closing the `<details>` has no CSS animation (the browser hides the body instantly when `[open]` is removed). Adding a close animation requires JS (listening to the `toggle` event, preventing default, running a CSS animation, then programmatically closing). This complexity is not justified for this use case — the instant close is acceptable. If a future designer wants a close animation, this is the place to note it as a known limitation.

4. **Figure Maker `setInputsDisabled`.** This function currently disables all three textareas by ID. After the rename, it must target `sharedCharacterInput`, `sharedStoryInput`, `sharedStyleInput`. If the function uses `document.querySelectorAll` or loops over IDs from the field map, the rename flows naturally. If IDs are hardcoded, they must be updated.

5. **`shared_inputs.js` FIELDS array.** The store keys (`character`, `story`, `style`) are not DOM IDs — they are the keys in `localStorage['monkeyking_shared_inputs']`. These do not change. Only the DOM IDs change. The `bindFields` map connects store keys to DOM IDs. No change to `shared_inputs.js` itself is needed.

6. **BB `saveState` JSON schema.** The Book Builder saves `concept: conceptInput.value.trim()`. After the rename, this becomes `concept: sharedStoryInput.value.trim()` (same JSON key, new const name). Confirm the developer understands the distinction between the const name and the JSON key — they must NOT change `concept` to `sharedStory` in the saved state object or all existing gallery books and localStorage restores break.

---

## 12. Files Touched by Implementation

| File | Change |
|---|---|
| `frontend/character_generator.html` | Replace shared-inputs block with canonical block; update tab hint text |
| `frontend/figure_maker.html` | Replace shared-inputs block with canonical block; update tab hint text; add `maxlength="500"` to `#sharedCharacterInput` |
| `frontend/book_builder.html` | Replace shared-inputs block with canonical block; update tab hint text |
| `frontend/style.css` | Add collapsible CSS block (Section 8) in the Shared Inputs Panel section |
| `frontend/character_generator.js` | Update `CG_FIELD_MAP`, all `cgDescInput`/`cgStoryInput`/`cgStyleInput` consts and reads; add `autoExpandIfContent()`; update `wireSharedInputListeners` / `bindFields` call with `onRemote` |
| `frontend/figure_maker.js` | Update `fmPromptInput`/`fmStoryInput`/`fmStyleInput` consts and all reads; update `setInputsDisabled`; update `bindFields` call with `onRemote`; add `autoExpandIfContent()` |
| `frontend/book_builder.js` | Update `conceptInput`/`characterInput`/`stylePromptInput` consts and all reads (~34 sites); update `bindFields` map; add `autoExpandIfContent()` called at end of init IIFE and in `onRemote` |
| `frontend/shared_inputs.js` | No changes required |
