# Design Review — MCM Consistency Audit
# BookBuilderBot frontend (all pages)

Review date: 2026-06-13
Audited files: `style.css`, `book_builder.css`, `character_generator.css`, `gallery.css`, `figure_maker.html` (placeholder), `book_builder.html`, `character_generator.html`, `gallery.html`

---

## Finding 1 — `.cg-error` is page-local but used (or needed) everywhere

**Severity: Medium**
**Files:** `character_generator.css` (defined), `figure-maker.md` spec (copied), `gallery-split.md` spec (implicitly needed), `settings.md` spec (referenced)

`.cg-error` (terracotta inline error block) is defined only in `character_generator.css`. Every other page that needs inline error messaging copies it or works around it. The pattern is clearly a shared utility.

**Fix:** Move the 9-line `.cg-error` rule block from `character_generator.css` into `style.css`. Remove the copy from `character_generator.css` — it inherits from `style.css` already. All new page CSS files (`figure_maker.css`, `settings.css`, `gallery.css`) then get it for free. Also add the teal `.settings-success-msg` variant to `style.css` at the same time as a named `.inline-success` utility.

```css
/* To add to style.css */
.inline-error {
  margin-top: .6rem;
  font-size: .82rem;
  color: var(--terracotta);
  background: rgba(196,81,58,.07);
  border: 1px solid rgba(196,81,58,.28);
  border-radius: 10px;
  padding: .45rem .65rem;
  line-height: 1.45;
}
.inline-error.hidden { display: none; }

.inline-success {
  margin-top: .6rem;
  font-size: .82rem;
  color: var(--teal-dark);
  background: rgba(58,125,122,.07);
  border: 1px solid rgba(58,125,122,.28);
  border-radius: 10px;
  padding: .45rem .65rem;
  line-height: 1.45;
}
.inline-success.hidden { display: none; }
```

Keep `.cg-error` as an alias in `character_generator.css` for backward compatibility during the transition, then remove it once the developer confirms no JS references it by that class name (the JS uses `.cg-error` as a selector string — a grep confirms: `cgErrorMsg` gets `className = 'cg-error hidden'` in `character_generator.js`). Rename to `.inline-error` only after updating JS.

---

## Finding 2 — `.skip-link` is page-local in `character_generator.css`

**Severity: Low**
**Files:** `character_generator.css` (defined), `figure_maker.html` (needs it), `settings.html` (needs it), `gallery.html` (missing entirely), `book_builder.html` (missing entirely)

`book_builder.html` and `gallery.html` have no skip link at all. `figure_maker.html` (placeholder) also has none. The skip link is a WCAG 2.1 AA requirement for pages with repeated navigation blocks (which all pages have).

**Fix:** Move `.skip-link` to `style.css`. Add `<a href="#mainId" class="skip-link">Skip to main content</a>` to every page's `<body>` as the very first child, pointing to the `id` of each page's `<main>`:
- `book_builder.html` → `<a href="#builderMain"` (currently `<main class="builder-main">` has no `id` — add `id="builderMain"`)
- `gallery.html` → `<a href="#galleryMain"` (add `id="galleryMain"` to `<main>`)
- `figure_maker.html` → `<a href="#fmMain"` (as per figure-maker spec)
- `settings.html` → `<a href="#settingsMain"` (as per settings spec)

---

## Finding 3 — Dead CSS in `style.css` (`.figure-main`, `.figure-placeholder`)

**Severity: Low**
**File:** `style.css`

The placeholder styles for the figure maker page (`.figure-main`, `.figure-placeholder`, `.figure-placeholder-icon`) remain in `style.css` after the `figure_maker.css` spec was written. Once `figure_maker.css` is implemented, these become dead code. They do not cause visual issues but add noise.

**Fix:** Remove from `style.css` when `figure_maker.css` is implemented. (This was already flagged in `figure-maker.md` as Flag 4 — noting it here for the cross-page audit record.)

---

## Finding 4 — `gallery.html` lacks a skip link and its `<main>` has no `id`

**Severity: Medium** (accessibility)
**File:** `gallery.html`

```html
<!-- current -->
<main class="gallery-main">
```

No `id`, no skip link. After the gallery split redesign, the `<main>` gains significant navigation complexity (tab bar + three grids). The skip link becomes more important, not less.

**Fix:** Add `id="galleryMain"` to `<main class="gallery-main">` and add the skip link as described in Finding 2.

---

## Finding 5 — `book_builder.html` `<main>` lacks an `id`

**Severity: Low**
**File:** `book_builder.html`

Same issue as Finding 4. The `<main>` is `<main class="builder-main">` with no `id`, so a skip link cannot point to it.

**Fix:** Add `id="builderMain"` to `<main class="builder-main">`.

---

## Finding 6 — `.thumb-upload-btn` uses `rgba(0,0,0,.6)` (raw black) rather than a token

**Severity: Low** (minor token drift)
**File:** `book_builder.css`, lines 224–236

The upload/regen overlay on page card thumbnails uses raw `rgba(0,0,0,.6)` for button backgrounds. The MCM palette does not use pure black anywhere else — it uses `var(--ink)` (`#2c2416`) as the darkest tone.

This is a dark overlay on an image thumbnail, so the raw black is defensible (images have varied backgrounds and maximum contrast is appropriate). However, it is inconsistent with the pattern.

**Recommendation:** Leave as-is — the rationale is sound. Flag for awareness rather than fix.

---

## Finding 7 — `.book-action-btn` minimum height is 40 px; touch target guideline is 44 px

**Severity: Low**
**File:** `gallery.css`, line 139

```css
.book-action-btn { min-height: 40px; }
```

WCAG 2.5.8 (AA, WCAG 2.2) recommends 24×24 px minimum with adequate spacing; Apple HIG recommends 44 px. The 40 px height, while close, falls below the stricter guideline on a touch device.

**Fix:** Change to `min-height: 44px` in `gallery.css`. This affects the books grid action buttons, the image card action buttons (which reuse `.book-action-btn`), and the model card action buttons. No visual change visible on desktop.

---

## Finding 8 — `.gallery-toolbar .project-btn` is a local re-definition of `.settings-btn`

**Severity: Low** (pattern duplication)
**File:** `gallery.css`, lines 26–38

`.gallery-toolbar .project-btn` is visually identical to `.settings-btn` from `style.css` (same `ctrl-bg` background, same border, same border-radius, same font, same transitions) but declared locally with slightly different padding (`.45rem .9rem` vs `.4rem .85rem`).

**Fix:** Replace the Refresh button class from `.project-btn` to `.settings-btn` in `gallery.html`, and remove the `.gallery-toolbar .project-btn` block from `gallery.css`. The visual difference is negligible. If the gallery split redesign is implemented, the Refresh button is already beside the tab bar and the `settings-btn` sizing is appropriate.

---

## Finding 9 — `figure_maker.html` is still the placeholder; loads no page-specific CSS

**Severity: High** (placeholder not yet replaced)
**File:** `figure_maker.html`

The current `figure_maker.html` loads only `style.css` and has a `<main class="figure-main">` placeholder. The `figure_maker.css` and `figure_maker.js` spec exist but the page hasn't been implemented. The nav links to this page from every other page.

This is not a design inconsistency per se — it is an unimplemented spec. Noting it here so the developer prioritises it. The existing `figure_maker.css` and `figure_maker.js` stubs exist as empty/near-empty files.

**Action for developer:** Implement per `design-specs/figure-maker.md`. Until then, the existing placeholder is acceptable.

---

## Finding 10 — `book_builder.css` uses `!important` for `.auto-gen-btn` and `.danger-btn` overrides

**Severity: Low** (CSS quality)
**File:** `book_builder.css`, lines 28–31, 81–82

```css
.auto-gen-btn {
  background: var(--teal) !important;
  color: #f5f0e8 !important;
  box-shadow: 0 4px 14px rgba(58,125,122,.28) !important;
}
.danger-btn { border-color: var(--terracotta) !important; color: var(--terracotta) !important; }
```

`!important` is used to override `.generate-btn` and `.project-btn` base styles. This works but is brittle — future changes to those base classes may still cascade unexpectedly.

**Fix:** Use a more specific selector instead of `!important`. Example: `.decompose-btn-row .auto-gen-btn` instead of targeting `.auto-gen-btn` globally with `!important`. This is a low-priority code quality fix; no visual change.

---

## Finding 11 — `page-card` box-shadow uses raw `rgba(0,0,0,.07)` instead of `var(--shadow)`

**Severity: Very Low**
**File:** `book_builder.css`, line 151

```css
.page-card { box-shadow: 0 3px 10px rgba(0,0,0,.07); }
```

`var(--shadow)` is `0 3px 14px rgba(44,36,22,.09)` (ink-tinted, not pure black). The values are close and visually indistinguishable, but `.book-card` in `gallery.css` correctly uses `var(--shadow)`. Minor divergence.

**Fix:** Change line 151 of `book_builder.css` to `box-shadow: var(--shadow);`.

---

## Finding 12 — No `lang-toggle` / tab segmented control in `style.css`; defined locally in `book_builder.css`

**Severity: Medium** (pattern reuse risk)
**File:** `book_builder.css` (defines `.lang-toggle`, `.lang-btn`)

The gallery split spec reuses the `.lang-toggle`/`.lang-btn` pattern for its tab bar but names the new classes `.gallery-tabs` / `.gallery-tab` to avoid pulling in `book_builder.css`. This is the right call for isolation, but it means the segmented control pattern now exists in three places: `book_builder.css`, `style.css` (`.provider-toggle`/`.provider-btn`), and `gallery.css` (new `.gallery-tabs`/`.gallery-tab`).

**Recommendation:** Extract a generic `.seg-control` / `.seg-btn` into `style.css`. This is a medium-priority refactor. For now the local definitions are acceptable. Flag for the next design system cleanup pass.

---

## Summary table

| # | Finding | File(s) | Severity | Action |
|---|---------|---------|----------|--------|
| 1 | `.cg-error` not in `style.css` | `character_generator.css` | Medium | Move to `style.css` |
| 2 | `.skip-link` not in `style.css`; missing from 3 pages | multiple | Medium | Move to `style.css`; add to all pages |
| 3 | Dead `.figure-main` CSS | `style.css` | Low | Remove when figure_maker.css lands |
| 4 | `gallery.html` `<main>` has no `id`, no skip link | `gallery.html` | Medium | Add `id`; add skip link |
| 5 | `book_builder.html` `<main>` has no `id` | `book_builder.html` | Low | Add `id="builderMain"` |
| 6 | Raw `rgba(0,0,0)` in overlay buttons | `book_builder.css` | Low | Leave as-is (justified) |
| 7 | `.book-action-btn` min-height 40 px (below 44 px guideline) | `gallery.css` | Low | Change to 44 px |
| 8 | `.gallery-toolbar .project-btn` duplicates `.settings-btn` | `gallery.css` | Low | Replace with `.settings-btn` |
| 9 | `figure_maker.html` still placeholder | `figure_maker.html` | High | Implement figure-maker spec |
| 10 | `!important` in `.auto-gen-btn`, `.danger-btn` | `book_builder.css` | Low | Use specificity instead |
| 11 | `.page-card` uses raw shadow instead of `var(--shadow)` | `book_builder.css` | Very Low | Use token |
| 12 | Segmented control pattern duplicated across files | multiple | Medium | Extract to `style.css` (next pass) |

**Priority order for developer:** 9 (figure maker placeholder) → 2 (skip links) → 1 (`.cg-error` extraction) → 4 (gallery `<main>` id) → 7 (touch targets) → 8 (button duplication) → 5 → 3 → 10 → 11 → 12
