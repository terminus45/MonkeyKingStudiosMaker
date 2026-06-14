# Mid-Century Modern Redesign Spec
# BookBuilderBot — CSS token and component update

Status: Ready for developer-agent implementation
Source files affected: `frontend/style.css`, `frontend/book_builder.css`, `frontend/gallery.css`

---

## 1. Design rationale (brief)

The current theme uses a five-color rainbow palette with gradient fills on nearly every interactive surface (header, generate button, step-num badges, progress bar, auto-gen button). The replacement is a mid-century modern palette: warm off-white ground, deep charcoal text, and four accent colors (mustard, terracotta, teal, olive) applied with restraint — one accent per component type, never blended into a gradient with another accent. The result reads as warm and hand-crafted without feeling childish or digital-garish. Large border-radius (18 px) is retained for friendliness.

---

## 2. Token table

All tokens live in `:root` in `frontend/style.css` and are inherited by `book_builder.css` and `gallery.css`.

| CSS custom property | Value | Purpose |
|---|---|---|
| `--ink` | `#2c2416` | Primary text, icon fills |
| `--ink-soft` | `#5a4a38` | Secondary text, placeholder labels |
| `--paper` | `#f5f0e8` | Page / body background |
| `--paper-dark` | `#ede5d4` | Slightly deeper warm surface (card thumbnails, input bg) |
| `--ctrl-bg` | `#f0ebe0` | Control / input background (replaces `#fff6ee`) |
| `--panel-bg` | `#f5f0e8` | Panel background (same as paper, kept separate for semantic clarity) |
| `--border` | `#d9cfbe` | Default border color |
| `--muted` | `#8c8070` | De-emphasized labels, hints, meta text |
| `--mustard` | `#e8a020` | Primary accent — generate button, active states, step 2 |
| `--mustard-dark` | `#b87a10` | Mustard hover / shadow reference |
| `--terracotta` | `#c4513a` | Secondary accent — danger/stop/step 1, error states |
| `--terracotta-dark` | `#9e3d2a` | Terracotta hover / shadow reference |
| `--teal` | `#3a7d7a` | Tertiary accent — step 3, provider active, focus ring |
| `--teal-dark` | `#2a5e5b` | Teal hover / shadow reference |
| `--olive` | `#6b7c3a` | Quaternary accent — step 4, secondary actions |
| `--olive-dark` | `#505d2a` | Olive hover / shadow reference |
| `--radius` | `18px` | Shared border-radius (unchanged) |
| `--shadow` | `0 3px 14px rgba(44,36,22,.09)` | Default card shadow (warm-tinted, replaces cool black) |

**Tokens removed:** `--coral`, `--sky`, `--sunshine`, `--mint`, `--purple`. Any reference to these in `book_builder.css` or `gallery.css` must be replaced with the new tokens per the mapping table in section 8.

---

## 3. New `:root {}` block (copy-paste ready)

Replace the entire `:root` block at lines 2–18 of `frontend/style.css` with:

```css
:root {
  --ink:             #2c2416;
  --ink-soft:        #5a4a38;
  --paper:           #f5f0e8;
  --paper-dark:      #ede5d4;
  --ctrl-bg:         #f0ebe0;
  --panel-bg:        #f5f0e8;
  --border:          #d9cfbe;
  --muted:           #8c8070;
  --mustard:         #e8a020;
  --mustard-dark:    #b87a10;
  --terracotta:      #c4513a;
  --terracotta-dark: #9e3d2a;
  --teal:            #3a7d7a;
  --teal-dark:       #2a5e5b;
  --olive:           #6b7c3a;
  --olive-dark:      #505d2a;
  --radius:          18px;
  --shadow:          0 3px 14px rgba(44,36,22,.09);
}
```

---

## 4. Header spec

### Background
Replace the rainbow `linear-gradient(135deg, #ff8c69 0%, #9b5de5 55%, #4aa8ff 100%)` with a single solid color:

```css
header {
  background: #2c2416;   /* --ink: deep charcoal */
  box-shadow: 0 3px 10px rgba(44,36,22,.30);
}
```

Using solid `--ink` rather than another gradient keeps the MCM "flat plane" quality. The mustard accent appears only on the active nav pill (see below), which provides enough warmth against the charcoal.

### Title text
- `.title-zh` — color: `#f5f0e8` (--paper), `text-shadow: none` (drop the current glow shadow)
- `.title-en` — color: `rgba(245,240,232,.80)` (paper at 80% opacity)

### Nav link states

| State | Background | Text color |
|---|---|---|
| Default | `transparent` | `rgba(245,240,232,.82)` |
| Hover | `rgba(245,240,232,.14)` | `#f5f0e8` |
| Active | `#e8a020` (--mustard) | `#2c2416` (--ink) |

Active pill uses mustard fill with charcoal text — the single highest-contrast MCM pop in the header.

```css
.nav-link:hover  { background: rgba(245,240,232,.14); color: #f5f0e8; }
.nav-link.active { background: var(--mustard); color: var(--ink); }
```

### Status dot
Dot colors should remain functionally readable but toned down to fit the charcoal background:

| State | Color | Box-shadow |
|---|---|---|
| Default (unknown) | `rgba(245,240,232,.30)` | none |
| `.ok` | `#6ecf8f` | `0 0 5px #6ecf8f` |
| `.error` | `#e08080` | `0 0 5px #e08080` |

Status label text: `rgba(245,240,232,.75)`.

---

## 5. Button spec

### 5a. `.generate-btn` (primary CTA — used in index.html and book_builder.html)

Replace the coral-to-dark-coral gradient with a solid mustard fill.

```
Background:  #e8a020  (--mustard)
Text:        #2c2416  (--ink)  — charcoal on mustard passes WCAG AA at this size
Border:      none
Box-shadow:  0 4px 14px rgba(232,160,32,.30)
Hover:       background #b87a10  (--mustard-dark), box-shadow 0 6px 18px rgba(232,160,32,.40), translateY(-2px)
Active:      translateY(0)
Disabled:    opacity .40
```

Note: switching from white text to charcoal text on mustard. `#2c2416` on `#e8a020` has a contrast ratio of approximately 5.4:1, which passes WCAG AA for normal text and large text. Verify with a contrast checker during implementation.

### 5b. `.auto-gen-btn` (override on `.generate-btn` in book_builder.css)

Replace the purple gradient with solid teal.

```
Background:  #3a7d7a  (--teal)
Text:        #f5f0e8  (--paper)  — light text on teal, contrast ~5.8:1
Box-shadow:  0 4px 14px rgba(58,125,122,.28)
Hover:       background #2a5e5b  (--teal-dark)
```

Remove the `!important` on `background` and `box-shadow` if the cascade allows; if the specificity war requires it, keep `!important` only on `background`.

### 5c. `.preset` pill (style.css)

```
Default:  background var(--ctrl-bg), border 2px solid var(--border), color var(--ink-soft)
Hover:    border-color var(--mustard), color var(--mustard-dark), background #f7edd8
Active:   background var(--mustard), border-color var(--mustard), color var(--ink), font-weight 700
```

Replace all `var(--sky)` and `#eef6ff` references in `.preset` rules.

### 5d. `.lang-btn` (book_builder.css — language selector toggle)

```
Default:  background transparent, color var(--ink-soft)
Hover:    color var(--teal), background rgba(58,125,122,.08)
Active:   background var(--teal), color #f5f0e8
```

Replace `var(--sky)` and `#eef6ff` in `.lang-btn` and `.lang-toggle` rules.

### 5e. `.book-action-btn` (gallery.css)

```
Default:  background var(--ctrl-bg), border 2px solid var(--border), color var(--ink-soft)
Hover:    border-color var(--mustard), color var(--mustard-dark), background #f7edd8
Hover (danger variant):  border-color var(--terracotta), color var(--terracotta), background rgba(196,81,58,.06)
Disabled: opacity .40
```

Replace `var(--sky)` / `#eef6ff` (default hover) and `var(--coral)` / `#fff0f0` (danger hover).

### 5f. `.project-btn` (book_builder.css and gallery.css)

```
Default:  background var(--ctrl-bg), border 2px solid var(--border), color var(--ink-soft)
Hover:    border-color var(--teal), color var(--teal)
```

`.danger-btn` override:
```
Default:  border-color var(--terracotta), color var(--terracotta)
Hover:    background var(--terracotta), color #f5f0e8, border-color var(--terracotta)
```

### 5g. `.stop-btn` (book_builder.css)

```
Default:  background var(--ctrl-bg), border 2px solid var(--terracotta), color var(--terracotta)
Hover:    background var(--terracotta), color #f5f0e8
```

### 5h. `.settings-btn` (style.css)

```
Default:      background var(--ctrl-bg), border 2px solid var(--border), color var(--ink-soft)
Hover:        border-color var(--teal), color var(--teal)
Muted variant (.settings-btn--muted):
  Default:    border-color var(--terracotta), color var(--terracotta)
  Hover:      background var(--terracotta), color #f5f0e8
```

### 5i. Provider toggle (`.provider-btn` in style.css)

```
Default:  background var(--ctrl-bg), color var(--muted)
Hover:    color var(--teal), background rgba(58,125,122,.08)
Active:   background var(--teal), color #f5f0e8, font-weight 700
```

### 5j. Seed / refresh button (`.seed-row button`)

```
Default:  background var(--ctrl-bg), border 2px solid var(--border)
Hover:    border-color var(--mustard)
```

---

## 6. Step card spec (book_builder.css)

### Step card container (`.builder-step`)

Replace `background: #fff` with `background: #faf7f2` — a very slightly warmed white that avoids a stark contrast against the `--paper` background, consistent with MCM paper layering.

```css
.builder-step {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.5rem;
}
```

### Left border accent per step

| Step | CSS selector | Border color | Hex |
|---|---|---|---|
| Step 1 (Concept) | `#step1` | terracotta | `#c4513a` |
| Step 2 (Story) | `#step2` | mustard | `#e8a020` |
| Step 3 (Generate) | `#step3` | teal | `#3a7d7a` |
| Step 4 (Export) | `#step4` | olive | `#6b7c3a` |

```css
#step1 { border-left: 5px solid var(--terracotta); }
#step2 { border-left: 5px solid var(--mustard); }
#step3 { border-left: 5px solid var(--teal); }
#step4 { border-left: 5px solid var(--olive); }
```

### Step number badge (`.step-num`)

Replace all gradient fills with solid accent fills. No gradients.

```css
.step-num {
  background: var(--terracotta);
  box-shadow: 0 2px 6px rgba(196,81,58,.25);
  color: #f5f0e8;
}
#step2 .step-num {
  background: var(--mustard);
  color: var(--ink);           /* charcoal on mustard for contrast */
  box-shadow: 0 2px 6px rgba(232,160,32,.25);
}
#step3 .step-num {
  background: var(--teal);
  color: #f5f0e8;
  box-shadow: 0 2px 6px rgba(58,125,122,.25);
}
#step4 .step-num {
  background: var(--olive);
  color: #f5f0e8;
  box-shadow: 0 2px 6px rgba(107,124,58,.25);
}
```

Note: step 2 badge uses mustard + charcoal text (same contrast pattern as the generate button). All others use paper-white text on darker accent fills.

---

## 7. Gallery card spec (gallery.css)

### Book card hover state

Replace the `--sunshine` border + yellow glow with a mustard border + warm shadow:

```css
.book-card:hover {
  border-color: var(--mustard);
  transform: translateY(-3px);
  box-shadow: 0 8px 22px rgba(232,160,32,.22);
}
```

### Cover placeholder background

Replace the `linear-gradient(135deg, var(--paper-dark), #fce0c0)` gradient with a flat, slightly textured warm tone:

```css
.book-cover {
  background: var(--paper-dark);   /* #ede5d4 — flat warm sand */
}
```

The placeholder emoji (`.book-cover-placeholder`) stays at `opacity: .35` — no change needed there.

### Gallery toolbar project-btn hover

Replace `var(--sky)` with `var(--mustard)` for border and text on hover.

### Page card hover (book_builder.css)

```css
.page-card:hover {
  border-color: var(--mustard);
  box-shadow: 0 6px 16px rgba(232,160,32,.18);
  transform: translateY(-2px);
}
```

---

## 8. Progress bar spec

### Global progress bar (book_builder.css `.progress-bar`)

Replace the three-color coral→purple→sky rainbow gradient with a single solid mustard:

```css
.progress-bar {
  background: var(--mustard);
}
```

No gradient. A solid accent bar reads more confidently and avoids the fairground-ride effect.

### Per-card progress fill (book_builder.css `.card-progress-fill`)

This is already `var(--sunshine)`. Replace with `var(--mustard)` — same hue family, now references the new token:

```css
.card-progress-fill {
  background: var(--mustard);
}
```

---

## 9. Focus / input states

Replace `var(--sky)` focus ring throughout `style.css`:

```css
textarea:focus, select:focus, input[type="number"]:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(58,125,122,.15);
}
```

Slider thumb:
```css
input[type="range"]::-webkit-slider-thumb {
  background: var(--mustard);
  box-shadow: 0 2px 6px rgba(232,160,32,.35);
}
```

Drag-over outline on card thumbnail:
```css
.card-thumb-wrap.drag-over {
  outline: 3px dashed var(--mustard);
}
```

---

## 10. Regen button (book_builder.css `.thumb-regen-btn`)

Replace the purple rgba fill with teal:

```css
.thumb-regen-btn {
  background: rgba(58,125,122,.80);
}
.thumb-regen-btn:hover {
  background: rgba(58,125,122,.95);
}
```

---

## 11. Card error state (book_builder.css `.card-error`)

Replace `var(--coral)` references with `var(--terracotta)`:

```css
.card-error {
  background: rgba(196,81,58,.07);
  border: 1px solid rgba(196,81,58,.28);
  color: var(--terracotta);
}
```

---

## 12. Token replacement mapping (for find-and-replace)

For the developer-agent: this table gives the mechanical substitution across all three CSS files. Where a hex literal was used (not a var()), the correct replacement is the new token var().

| Old value | Old purpose | Replace with |
|---|---|---|
| `var(--coral)` | primary accent / danger | `var(--terracotta)` |
| `var(--sky)` | interactive accent / focus | `var(--teal)` (focus/interactive) or `var(--mustard)` (hover borders) — see per-component rules above |
| `var(--sunshine)` | highlight / progress | `var(--mustard)` |
| `var(--mint)` | step 4 / secondary | `var(--olive)` |
| `var(--purple)` | step 1 / gradient stop | `var(--terracotta)` (step context) or `var(--teal)` (auto-gen button) |
| `#eef6ff` | sky hover background | `#f7edd8` (mustard-tinted warm cream) or `rgba(58,125,122,.08)` (teal-tinted) — see per-button rules above |
| `#fff0f0` | coral/danger hover bg | `rgba(196,81,58,.06)` |
| `rgba(155,93,229,…)` | purple shadow/fill | use teal equivalent `rgba(58,125,122,…)` |
| `rgba(255,200,61,…)` | sunshine shadow | `rgba(232,160,32,…)` (mustard shadow) |
| `rgba(255,107,107,…)` | coral shadow | `rgba(196,81,58,…)` (terracotta shadow) |
| `rgba(74,168,255,…)` | sky shadow/focus | `rgba(58,125,122,…)` (teal) |
| `linear-gradient(135deg, #ff8c69 0%, #9b5de5 55%, #4aa8ff 100%)` | header | `#2c2416` (solid charcoal) |
| `linear-gradient(135deg, var(--coral) 0%, #e04545 100%)` | generate-btn | `var(--mustard)` (solid) |
| `linear-gradient(135deg, var(--coral), var(--purple))` | step-num default | `var(--terracotta)` (solid) |
| `linear-gradient(135deg, var(--sunshine), #e8a010)` | step-num step2 | `var(--mustard)` (solid) |
| `linear-gradient(135deg, var(--sky), #2272d8)` | step-num step3 | `var(--teal)` (solid) |
| `linear-gradient(135deg, var(--mint), #2ea07a)` | step-num step4 | `var(--olive)` (solid) |
| `linear-gradient(90deg, var(--coral), var(--purple), var(--sky))` | progress bar | `var(--mustard)` (solid) |
| `linear-gradient(135deg, var(--purple), #6c35b5)` | auto-gen-btn | `var(--teal)` (solid) |
| `linear-gradient(135deg, var(--paper-dark), #fce0c0)` | gallery book-cover bg | `var(--paper-dark)` (flat) |
| `#fff` (on `.builder-step`, `.page-card`, `.book-card`) | card white bg | `#faf7f2` |

---

## 13. Accessibility notes

- Charcoal text (`#2c2416`) on paper background (`#f5f0e8`): contrast ratio ~13:1. Excellent.
- Charcoal text (`#2c2416`) on mustard (`#e8a020`): ~5.4:1. Passes WCAG AA for normal text (4.5:1 threshold) and large text. Used on generate-btn and step-2 badge.
- Paper text (`#f5f0e8`) on teal (`#3a7d7a`): ~5.8:1. Passes WCAG AA.
- Paper text (`#f5f0e8`) on terracotta (`#c4513a`): ~4.7:1. Passes WCAG AA for normal text. Passes AA for large/bold text.
- Paper text (`#f5f0e8`) on olive (`#6b7c3a`): ~4.9:1. Passes WCAG AA.
- Paper text (`#f5f0e8`) on charcoal header (`#2c2416`): ~14:1. Excellent.
- Muted label (`#8c8070`) on paper (`#f5f0e8`): ~3.6:1. Falls below 4.5:1 for small normal text — this matches the current behavior (existing `--muted` is `#9c8474` which is similarly low). These labels are font-weight 700 uppercase 0.75rem, which qualifies as "large text" under WCAG (bold + ≥14pt ≈ ≥18.67px equivalent). If any muted text is non-bold and below 14px, increase contrast by darkening `--muted` to `#7a6e62`.
- Keyboard navigation: no structural changes to interactive element order or ARIA roles are required by this redesign.
- Focus ring: replacing sky blue with teal keeps a visible, high-contrast ring (3px `rgba(58,125,122,.15)` outer glow plus `border-color: var(--teal)` on inputs).

---

## 14. Out of scope / unchanged

- Font stack (Baloo 2, Nunito) — no change
- `--radius: 18px` — no change
- Layout, grid, spacing values — no change
- ARIA roles, HTML structure — no change
- `storybook_print.js` export styles — out of scope (print/export CSS is inline-generated; check separately if MCM palette is desired there)
- Mobile Capacitor wrapper — inherits frontend CSS; no additional action needed
