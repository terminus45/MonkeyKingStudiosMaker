# Check Readings — Design Spec

**Feature:** "Check readings" — per-book pinyin / romaji / romanization correction in Book Builder.
**Status:** Spec only — implementation by developer-agent.
**Branch context:** `feature/figure-maker-settings-gallery-split`
**Parallel work:** `POST /recheck-readings` backend endpoint (being designed separately). This spec assumes that endpoint exists and returns the same shape as `POST /decompose` (full `DecomposeResponse`-compatible page array: native text, reading string, re-aligned `characters[]`).

---

## 1. Trigger Control

### Placement

The button belongs in **Step 2** (`#step2`), immediately below the `#step2` `.step-header` and above `#pageGrid`. It is NOT placed in Step 3 (which owns image generation) and NOT placed beside the decompose buttons (which own story creation). Step 2 is the readings-editing surface and is the only step where this action is semantically meaningful.

Insert a new `div.check-readings-row` between `.step-header` / `#bookTitleSub` and `#pageGrid`:

```
section#step2 (.builder-step)
  div.step-header
    span.step-num ②
    h2#bookTitleDisplay
  p.section-sub#bookTitleSub
  ── NEW ──────────────────────────────────────────
  div.check-readings-row
    button#checkReadingsBtn  (.settings-btn .settings-btn--accent)
    p.hint-text#checkReadingsHint
  ─────────────────────────────────────────────────
  div.page-grid#pageGrid
```

### Button

**Element id:** `checkReadingsBtn`
**Class:** `settings-btn settings-btn--accent`

The `.settings-btn--accent` class already exists in `style.css` (lines 355–369). It renders as a small pill button using the `--mustard` / `#ff6b35` accent, visually distinct from the primary orange `generate-btn` used for Decompose and image generation. This correctly signals "secondary, editorial action" without competing with the page's primary CTA hierarchy.

**Label (default):** `✦ Check Readings`
(The `✦` character is already used on the Decompose button for "Claude is working" connotation; reusing it here signals the same AI-assisted nature consistently.)

**Size / shape:** matches existing `.settings-btn` geometry — `min-height: 36px`, `border-radius: 10px`, `font-size: .82rem`. This is intentionally smaller than `.generate-btn` to reinforce the secondary-action hierarchy.

### Enabled / Disabled Logic

| Condition | State |
|---|---|
| `storyData` is `null` (no story yet) | `disabled` — Step 2 is hidden anyway, but guard JS-side too |
| Decompose is running (`setDecomposeLoading(true)`) | `disabled` |
| Image queue is running (`setQueueLoading(true)`) | `disabled` |
| Recheck is running | `disabled` (button shows loading state, see Section 2) |
| Story exists and no conflicting operation | `enabled` |

The existing `setDecomposeLoading` and `setQueueLoading` functions already toggle `decomposeBtn.disabled` / `queueBtn.disabled`. The developer should add `checkReadingsBtn.disabled = on` inside both of those functions so the three primary operations are mutually exclusive. The single-page regeneration button (`thumb-regen-btn`) does NOT need to block the check — it is a fast per-card operation.

### Hint line

A `<p class="hint-text" id="checkReadingsHint"></p>` sits immediately below the button (mirrors the existing `#decomposeHint` pattern). It starts empty, shows progress text during the call, and shows error text on failure. It clears on a successful check (the preview panel takes over communication). Use the same `.hint-text` class (defined in `book_builder.css` — `font-size: .8rem; color: var(--muted); margin-top: .5rem; min-height: 1.2em`).

---

## 2. Loading State

The check is a single Claude round-trip (~15–25 s for 10 pages).

**During the call:**

- Button label changes to: `Checking…` (no icon, plain text — matches the pattern of `decomposeLabel` changing to `Writing…`)
- A `.spinner` element is appended inside the button (reuse the existing `.spinner` / `hidden` toggle pattern)
- `checkReadingsHint` shows: `Claude is checking your readings… this usually takes ~20 seconds.`
- Button is disabled (see Section 1)
- The page-grid cards remain fully visible and editable — the user can read / scroll but should not start the image queue

**After the call (success):**

- Button re-enables with default label
- `checkReadingsHint` clears
- Preview panel appears (see Section 3)

**After the call (failure):**

- Button re-enables with default label
- `checkReadingsHint` shows the error string (same pattern as `decomposeHint` on failure: `Error: <message>`)

Suggested HTML skeleton for the button (developer implements):

```html
<div class="check-readings-row">
  <button id="checkReadingsBtn" class="settings-btn settings-btn--accent" disabled>
    <span id="checkReadingsLabel">✦ Check Readings</span>
    <div class="spinner hidden" id="checkReadingsSpinner" aria-hidden="true"></div>
  </button>
  <p class="hint-text" id="checkReadingsHint" aria-live="polite"></p>
</div>
```

`aria-live="polite"` on the hint paragraph so screen readers announce the loading / error message without stealing focus.

---

## 3. Preview / Confirm Surface

### Modal vs. Inline Panel — Recommendation: Modal

**Rationale:** The single-column page already has a tall card grid (`#pageGrid`). An inline panel inserted into Step 2 would either push the grid far down (disorienting) or require the user to scroll past it to see the comparison and then scroll back to confirm. A modal overlays the existing page without reflowing it, keeps the before/after comparison in a focused, scrollable surface, and matches the weight of the action (a batch edit to up to 10 pages). The app does not currently have a shared modal component — the developer should create a minimal one following the existing dark-theme tokens.

### Modal structure (ASCII mockup)

```
┌─────────────────────────────────────────────────────────┐
│  ✦ Readings Check — 3 pages updated                     │  ← modal header
│                                                   [✕]   │     close btn (top-right)
├─────────────────────────────────────────────────────────┤
│  8 pages unchanged  ────────────────────────────────    │  ← summary chip/line
│                                                         │
│  ┌─ Page 2 ──────────────────────────────────────────┐  │
│  │  NATIVE     猴子王学会分享                          │  │  ← changed-page card
│  │  BEFORE     Hóuzi wáng xuéhuì fēnxiǎng            │  │
│  │  AFTER      Hóuzǐ wáng xué huì fēn xiǎng          │  │  ← highlighted diff
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Page 7 ──────────────────────────────────────────┐  │
│  │  NATIVE     一起走进新世界                          │  │
│  │  BEFORE     Yīqǐ zǒu jìn xīn shìjiè               │  │
│  │  AFTER      Yī qǐ zǒu jìn xīn shì jiè             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Page 9 ──────────────────────────────────────────┐  │
│  │  NATIVE     他找到了朋友                            │  │
│  │  BEFORE     Tā zhǎo dào le péngyǒu                 │  │
│  │  AFTER      Tā zhǎo dàole péngyǒu                  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [Apply 3 corrections]     [Cancel — keep current]      │  ← action footer
└─────────────────────────────────────────────────────────┘
```

### Modal markup spec

**Overlay:** `div#checkReadingsOverlay` — `position: fixed; inset: 0; background: rgba(10,11,26,.80); z-index: 100; display: flex; align-items: flex-start; justify-content: center; padding: 2rem 1rem; overflow-y: auto`

**Dialog box:** `div#checkReadingsDialog` — `role="dialog"; aria-modal="true"; aria-labelledby="checkReadingsDialogTitle"` — `background: #0f1129; border: 1px solid var(--border); border-radius: var(--radius); max-width: 600px; width: 100%; padding: 0` (internal sections carry their own padding)

**Header:** `div.cr-modal-header` — `display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 1.5rem 1rem; border-bottom: 1px solid var(--border)`
- `h2#checkReadingsDialogTitle` — title text e.g. `✦ Readings Check — 3 pages updated`; `font-size: 1rem; font-weight: 800`
- `button#checkReadingsCloseBtn` — `aria-label="Close preview"` — plain icon button using existing `.settings-btn` styling with an `✕` glyph, `min-height: 32px; padding: .2rem .55rem`

**Summary bar:** `p.cr-summary` — full-width, `padding: .75rem 1.5rem; font-size: .82rem; color: var(--muted); border-bottom: 1px solid var(--border)` — text: `N pages unchanged` (omit if all pages changed). When there are zero changed pages: show `No corrections needed — your readings look good!` and hide the changed-page cards.

**Scrollable body:** `div.cr-modal-body` — `padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; max-height: 60vh; overflow-y: auto`

**Per-changed-page card:** `div.cr-page-card`

```
div.cr-page-card
  p.cr-page-label          "Page N"
  div.cr-field
    span.cr-field-label    "NATIVE"          (the native sentence — zh/ja/ko)
    p.cr-field-value.cr-native  (text, native font)
  div.cr-field
    span.cr-field-label    "BEFORE"
    p.cr-field-value.cr-before  (old reading string)
  div.cr-field
    span.cr-field-label    "AFTER"
    p.cr-field-value.cr-after   (new reading string)
```

The AFTER row is the most important. Give it a left border accent: `border-left: 3px solid var(--mustard); padding-left: .5rem` (same pattern as `.shared-field-primary textarea`). This highlights the corrected value without adding color that could be missed by colorblind users — the `AFTER` label and the indented padding create a color-independent structural cue.

Do NOT show character-by-character diffs inside the modal. The reading strings are short (~10–30 characters); the complete before/after is easier to scan than an inline diff and avoids a complex diff implementation.

**Footer:** `div.cr-modal-footer` — `display: flex; gap: .75rem; padding: 1rem 1.5rem; border-top: 1px solid var(--border); flex-wrap: wrap`
- `button#checkReadingsApplyBtn` — `.generate-btn` — `Apply N corrections` (use actual count in the label, e.g. `Apply 3 corrections`)
- `button#checkReadingsCancelBtn` — `.generate-btn` style with `background: rgba(255,255,255,.10); color: #ffffff; border: 1px solid rgba(255,255,255,.10)` — `Cancel — keep current` (same ghost-button treatment as `auto-gen-btn`)

When there are zero changes, show only `Close` (a single `.settings-btn`), omit Apply / Cancel.

### Apply behavior

On Apply:
1. For each changed page, write the corrected native text, reading string, and `characters[]` back into `storyData.pages[i]`
2. For each changed page, update the corresponding card textareas in the DOM (`data-field="zh"` / `data-field="pinyin"` / etc.) with the corrected values
3. Mark those cards as "staleness cleared" (remove any staleness hint — see Section 4)
4. Close the modal
5. Call `saveState()` so the corrections persist to localStorage

On Cancel / Close (✕ / Escape): dismiss without mutating anything.

### Empty-result state (no changes needed)

When the API returns pages that are identical to the current card values across all pages:

The modal opens but shows only:

```
✦ Readings Check — all good!
──────────────────────────────
  Your readings look correct — no corrections found.
──────────────────────────────
[ Close ]
```

No Apply / Cancel. Focus goes to the Close button.

---

## 4. Staleness Hint (Per-Card)

After a successful check, if the user edits a **native-sentence textarea** on a card (`data-field="zh"` / `data-field="ja"` / `data-field="ko"`), the `characters[]` for that page is now stale. Spec for this:

### Trigger

Wire an `input` event listener on each native-field textarea (delegated from `#pageGrid`). When a native textarea is edited after a successful check has been applied to that page, set a `data-readings-stale="true"` attribute on the `.page-card` element for that page.

A separate boolean `lastCheckApplied` (JS module-level) gates whether the staleness logic is active at all — it is set `true` when Apply is clicked, and `false`/reset when Decompose runs or Clear is called.

### Visual treatment

Inside `.card-body`, after the reading textarea and before the English textarea, conditionally render a hint element:

```html
<p class="card-readings-stale-hint hidden" id="readings-stale-${pg.page}">
  ⚠ Reading may be out of date — run Check Readings to correct.
</p>
```

**Styling (`book_builder.css` addition):**

```css
.card-readings-stale-hint {
  font-size: .72rem;
  color: rgba(255,185,90,.85);   /* warm amber — distinct from error red and muted grey */
  font-style: italic;
  margin-top: -.2rem;
  line-height: 1.4;
}
.card-readings-stale-hint.hidden { display: none; }
```

Amber is used (not the error red `#e5484d`) because this is a non-blocking informational hint, not an error. It is also color-independent: the `⚠` glyph provides a semantic cue, and the italic style and placement (between the reading and English fields) provide structural context.

The hint is single-line on most cards. It does not add a button — the user's path is to click the top-level "Check Readings" button, not a per-card action. Keep it passive.

### Clearing the hint

- Clear on: Apply (for the affected cards), Decompose/re-decompose (for all cards), Clear project, Load project.
- Do NOT auto-clear when the user edits the reading field manually — the `characters[]` in `storyData` would still be stale even if the user typed a new reading string.

### Decided behavior: drop stale annotations at save/export (not a hard gate)

The staleness hint is the user-facing nudge, but it is **not** the data-integrity guarantee. The guarantee: when a card is flagged `data-readings-stale="true"`, the save/export path (`readCard` carry-forward) must **drop that page's `characters[]` (set it to `null`)** rather than ship the stale array. This makes a stale page degrade to "no annotation" — falling back to the deterministic zh syllable splitter or plain native text in `renderRubyText` — exactly as books behave today, instead of rendering a *wrong* reading over the right character. The user keeps editing freely (no export block); a re-run of Check Readings repopulates the array and clears the stale flag.

---

## 5. Error and Empty States

### No Anthropic API key

If the `/recheck-readings` call returns a **503** ("ANTHROPIC_API_KEY not set on server" — the same status `/decompose` returns for a missing key), mirror the pattern in `figure_maker.js` line 234 (`"Anthropic key missing — ask a grown-up to set it in Settings (⚙)"`):

`checkReadingsHint` shows: `No Anthropic key set — add it in Settings (⚙) to use this feature.`

The `⚙` glyph is consistent with the Figure Maker error copy. No navigation is forced — the user can click the gear icon in the header at their own pace.

Existing story is untouched.

### Claude error (API failure, forced-tool-use failure, etc.)

`checkReadingsHint` shows: `Error: <server error message>`

Mirrors the exact pattern of `decomposeHint` on failure. No modal opens. Existing story is untouched.

### Network timeout / server offline

Same as Claude error above. The `checkReadingsHint` can show a more specific message if the fetch throws a network error: `Could not reach the server — check your connection and try again.`

### Structural mismatch (server returns wrong page count)

If the response page count does not match `storyData.pages.length`, treat as an error: `checkReadingsHint` shows `Unexpected response — page count mismatch. Your story was not changed.` Do not attempt a partial apply.

In all error states: the `checkReadingsBtn` re-enables, the spinner hides, and `checkReadingsHint` shows the error text (with `aria-live="polite"` already on the hint paragraph, so screen readers announce it). The story is never mutated.

---

## 6. Accessibility

### Focus management (modal)

On modal open: move focus to `#checkReadingsDialog` itself (`tabindex="-1"` set on the dialog div, then `.focus()` called after inserting into DOM). This anchors screen-reader virtual cursor inside the dialog.

On modal close (Apply / Cancel / ✕ / Escape): return focus to `#checkReadingsBtn`.

Trap focus within the modal while it is open: keyboard Tab should cycle only through interactive elements inside `#checkReadingsDialog` (close button, apply, cancel). Implement a minimal focus-trap loop (keydown Tab / Shift+Tab on the dialog).

`Escape` key closes the modal with Cancel behavior (no mutation).

### ARIA

- `#checkReadingsDialog` — `role="dialog" aria-modal="true" aria-labelledby="checkReadingsDialogTitle"`
- `#checkReadingsDialogTitle` — the `<h2>` inside the modal header
- `#checkReadingsCloseBtn` — `aria-label="Close preview"`
- `#checkReadingsHint` — `aria-live="polite"` (already in Section 2 skeleton)
- Apply button label includes the count: `Apply 3 corrections` — this is descriptive enough without additional aria attributes

### Button disabled states

All three mutually-exclusive primary actions (Decompose, Queue, Check Readings) must convey their disabled state via `disabled` attribute (not just CSS opacity). The existing `.generate-btn:disabled { opacity: .40; cursor: not-allowed }` and `.settings-btn--accent:disabled { opacity: .45; cursor: not-allowed }` rules handle the visual.

### Color-independent change highlighting

The AFTER row uses a left border accent (`border-left: 3px solid var(--mustard)`) AND the `AFTER` label text AND indented padding to distinguish it from BEFORE. Colorblind users see a structural difference (indent + label), not only a color difference. Do not rely on background color alone.

The staleness hint uses a `⚠` glyph + italic style, not only the amber color.

### Contrast

- Modal background `#0f1129` (same as `--paper-dark`) against white text exceeds WCAG AA.
- Amber hint `rgba(255,185,90,.85)` on `#0f1129` — approximate computed value `#ffb95a` on `#0f1129`. Contrast ratio is approximately 6.4:1 against the dark background, exceeding WCAG AA for normal text.
- `BEFORE` / `AFTER` label text at `var(--muted)` (`rgba(255,255,255,.50)`) — this is an existing pattern for secondary labels across the app; it matches `card-field label` styling. Borderline for small text but consistent with system behavior. The developer should consider `color: var(--ink-soft)` (`rgba(255,255,255,.70)`) for these labels if the designer review finds the contrast insufficient.

### Screen-reader reading order in the modal

The logical reading order is: dialog title → summary → [for each changed page: page label → NATIVE → BEFORE → AFTER] → Apply → Cancel. The DOM order matches this. No `aria-describedby` cross-linking is needed beyond the standard `aria-labelledby` on the dialog.

---

## 7. CSS Additions (book_builder.css)

New rules to add. No existing rules are changed.

```css
/* ── Check Readings trigger row (Step 2, above page grid) ── */
.check-readings-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  margin-bottom: .75rem;
}

/* ── Readings check modal ── */
.cr-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10,11,26,.80);
  z-index: 100;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2rem 1rem;
  overflow-y: auto;
}
.cr-modal-overlay.hidden { display: none; }

.cr-modal-dialog {
  background: #0f1129;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  max-width: 600px;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.cr-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem 1rem;
  border-bottom: 1px solid var(--border);
  gap: .75rem;
}
.cr-modal-header h2 {
  font-size: 1rem;
  font-weight: 800;
  color: var(--ink);
  flex: 1;
}

.cr-summary {
  padding: .65rem 1.5rem;
  font-size: .82rem;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  margin: 0;
}

.cr-modal-body {
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 60vh;
  overflow-y: auto;
}

.cr-page-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: .8rem 1rem;
  display: flex;
  flex-direction: column;
  gap: .45rem;
  background: rgba(255,255,255,.03);
}

.cr-page-label {
  font-size: .65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
  font-family: 'Space Mono', 'SFMono-Regular', Consolas, monospace;
  margin-bottom: .15rem;
}

.cr-field {
  display: flex;
  flex-direction: column;
  gap: .15rem;
}

.cr-field-label {
  font-size: .6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);
  font-family: 'Space Mono', 'SFMono-Regular', Consolas, monospace;
}

.cr-field-value {
  font-size: .88rem;
  color: var(--ink-soft);
  line-height: 1.45;
  margin: 0;
  word-break: break-word;
}
.cr-field-value.cr-native {
  font-size: 1rem;
  font-family: 'Noto Serif SC', 'SimSun', serif;  /* developer: apply lang-specific font per page */
  color: var(--ink);
}
.cr-field-value.cr-after {
  color: var(--ink);
  border-left: 3px solid var(--mustard);
  padding-left: .5rem;
  font-weight: 600;
}

.cr-modal-footer {
  display: flex;
  gap: .75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.cr-modal-footer .generate-btn {
  flex: 1 1 180px;
  max-width: 260px;
}
.cr-cancel-btn {
  background: rgba(255,255,255,.10) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255,255,255,.10) !important;
}
.cr-cancel-btn:hover:not(:disabled) {
  background: rgba(255,255,255,.20) !important;
}

/* ── Per-card staleness hint ── */
.card-readings-stale-hint {
  font-size: .72rem;
  color: rgba(255,185,90,.85);
  font-style: italic;
  line-height: 1.4;
}
.card-readings-stale-hint.hidden { display: none; }
```

**Note on `.cr-field-value.cr-native` font:** the developer should apply the correct lang-specific font dynamically (reading `currentLang`) when building the modal, using the same font-family values already in `.card-field.native-field`, `.card-field.native-field.lang-ja`, `.card-field.native-field.lang-ko`.

---

## 8. Interaction Flag — Existing Design System

**No new design patterns are introduced.** Every element uses existing tokens and class families:

| Element | Pattern used |
|---|---|
| Trigger button | `.settings-btn--accent` (already in `style.css`) |
| Spinner / loading label swap | Existing `decomposeLabel` / `decomposeSpinner` pattern |
| Hint paragraph | Existing `.hint-text` class |
| Modal overlay | New CSS but uses `var(--paper-dark)`, `var(--border)`, `var(--radius)` tokens |
| Changed-page highlight | Left border + label (same as `.shared-field-primary textarea` in `style.css`) |
| Staleness hint | New `.card-readings-stale-hint` — similar to `.card-error` but amber/italic instead of red/mono |
| Apply button | `.generate-btn` (primary) |
| Cancel button | `.generate-btn` + ghost override (same as `.auto-gen-btn`) |

One flag: the `.cr-cancel-btn` override uses `!important` to override `.generate-btn`'s orange background. If the developer prefers, they can instead use the `auto-gen-btn` class directly (it already applies `background: rgba(255,255,255,.10)`) rather than a new modifier. Either approach is acceptable — the `auto-gen-btn` reuse is slightly more consistent and avoids `!important`.

---

## 9. Responsive Behavior

The modal is `max-width: 600px; width: 100%` — on narrow screens it fills most of the viewport width. At `max-width: 700px` (existing breakpoint):

- The `.cr-modal-overlay` padding reduces to `padding: 1rem .5rem`
- The footer buttons stack (`flex-wrap: wrap` already specified, each flex `1 1 100%` at mobile)
- The scrollable body `max-height: 60vh` is retained — the user scrolls within the modal, not the page

Add to the existing `@media (max-width: 700px)` block in `book_builder.css`:

```css
@media (max-width: 700px) {
  .cr-modal-overlay { padding: 1rem .5rem; }
  .cr-modal-footer .generate-btn { max-width: 100%; flex: 1 1 100%; }
}
```
