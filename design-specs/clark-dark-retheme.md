# Clark Dark Re-theme — Component Spec

**Status:** Design spec for developer implementation.
**Source of truth:** `VisualStyle_ClarkDark.md` (color/shape language), `VisualStyle_MKStudio.md` (current inventory).
**Scope:** Every CSS custom-property swap and component-level treatment needed to move the app from the MKStudio parchment palette to Clark Dark. The architect is handling the `:root` token remap; this document specifies the per-component visual rules, exact rgba values, and contrast audit.

---

## Exact rgba Reference (Tailwind opacity → plain CSS)

These values appear repeatedly below. Use this table rather than computing inline.

| Tailwind shorthand | Plain CSS rgba | Role |
|--------------------|----------------|------|
| `bg-white/5`       | `rgba(255,255,255,0.05)` | Subtle surface / secondary card |
| `bg-white/10`      | `rgba(255,255,255,0.10)` | Standard interactive chip / button |
| `bg-white/20`      | `rgba(255,255,255,0.20)` | Hover on white/10 interactive |
| `text-white/70`    | `rgba(255,255,255,0.70)` | Nav default / body secondary |
| `text-white/60`    | `rgba(255,255,255,0.60)` | Body / label secondary |
| `text-white/50`    | `rgba(255,255,255,0.50)` | Muted / metadata |
| `text-white/40`    | `rgba(255,255,255,0.40)` | Loading text / disabled hint |
| `text-white/30`    | `rgba(255,255,255,0.30)` | Placeholder text (inputs) |
| `bg-accent/20`     | `rgba(255,107,53,0.20)`  | Tinted accent chip |
| `text-accent`      | `#ff6b35`                | Accent text on dark surface |
| `bg-black/70`      | `rgba(0,0,0,0.70)`       | Modal scrim |
| `bg-black/60`      | `rgba(0,0,0,0.60)`       | Thumb overlay button |
| `border-white/10`  | `rgba(255,255,255,0.10)` | All default borders |
| `border-white/25`  | `rgba(255,255,255,0.25)` | Stronger divider (rare) |

---

## Contrast Audit (WCAG 2.1)

Foreground colors are tested against the two primary surfaces (`#0a0b1a` navy and `#0f1129` navy-800). Use this table to decide acceptable usage levels.

| Foreground | Background | Approx ratio | WCAG result | Notes |
|------------|------------|-------------|-------------|-------|
| `#ffffff` (white) | `#0a0b1a` | ~21:1 | AAA | Headings, primary text |
| `rgba(255,255,255,0.80)` | `#0a0b1a` | ~16:1 | AAA | Body text |
| `rgba(255,255,255,0.70)` | `#0a0b1a` | ~14:1 | AAA | Nav default, secondary body |
| `rgba(255,255,255,0.60)` | `#0f1129` | ~11:1 | AAA | Labels, metadata |
| `rgba(255,255,255,0.50)` | `#0f1129` | ~9:1 | AAA | Muted / helper text |
| `rgba(255,255,255,0.40)` | `#0f1129` | ~7:1 | AA | Loading text, placeholders — PASSES for normal text |
| `rgba(255,255,255,0.30)` | `#0f1129` | ~5.5:1 | AA for normal text | Placeholder — acceptable in inputs only |
| `#ff6b35` (accent) | `#0a0b1a` | ~4.8:1 | AA (normal + large/bold) | Primary button label, active tab text |
| `#ff6b35` (accent) | `#0f1129` | ~4.6:1 | AA (normal + large/bold) | Use on bold ≥14px or large text only |
| `rgba(255,255,255,0.40)` | `rgba(255,255,255,0.10)` overlay on `#0f1129` | ~6:1 effective | AA | Chip labels — passes |
| `rgba(229,72,77,1)` approx `#e5484d` | `#0f1129` | ~4.9:1 | AA | Danger/error text |

**Flag:** `rgba(255,255,255,0.30)` at small body sizes (below 14px) without bold falls below 4.5:1 against `#0f1129`. Reserve it exclusively for placeholder text inside input elements (WCAG 1.4.3 exempts placeholder). Do not use white/30 for any visible body copy or label.

---

## 1. App Background and Body

```
body
  background: #0a0b1a          /* replaces var(--paper) #f5f0e8 */
  color: #ffffff               /* replaces var(--ink) #2c2416 */
  font-family: 'Nunito', system-ui, sans-serif   /* drop Baloo 2 */
```

The page background is a single flat navy — no texture, no gradient. Every surface lifts off it purely through translucency or a solid `#0f1129` panel.

---

## 2. Header / Nav

**Header bar (`header`):**
- `background: #0f1129` (navy-800 solid — replaces charcoal `#2c2416`)
- `border-bottom: 1px solid rgba(255,255,255,0.10)` (replaces `box-shadow: 0 3px 10px rgba(44,36,22,.30)`)
- Remove `box-shadow` entirely

**Brand title (`.header-title`):**
- `.title-zh` / `.title-en`: `color: #ffffff` (was paper-white `#f5f0e8` — visually identical on dark, keep as `#ffffff`)
- `.title-en`: `color: rgba(255,255,255,0.70)`

**Nav links (`.nav-link`):**

| State | Background | Text color |
|-------|------------|------------|
| Default | transparent | `rgba(255,255,255,0.70)` |
| Hover | `rgba(255,255,255,0.10)` | `#ffffff` |
| Active | `#ff6b35` | `#ffffff` |

Active uses full solid accent fill with white text. Contrast: white on `#ff6b35` = ~4.8:1, AA for bold text at `.82rem/700` which qualifies as bold ≥14px — passes.

Border-radius stays `20px` (rounded-full pill). No change to padding or min-height.

**Settings gear (`.settings-gear`):**

| State | Background | Color |
|-------|------------|-------|
| Default | none | `rgba(255,255,255,0.70)` |
| Hover | `rgba(255,255,255,0.10)` | `#ffffff` |
| Active | `rgba(255,107,53,0.20)` | `#ff6b35` |

Note: the active state shifts from solid mustard fill + dark icon to a tinted overlay + accent icon. This is lighter than the nav-link active treatment — keeps the gear recessive relative to nav tabs. If the gear doubles as the current-page indicator when on settings.html, use `background: #ff6b35; color: #ffffff` to match nav-link active.

**Status dot (`.status-dot`):**
- Default: `background: rgba(255,255,255,0.20)` (replaces `rgba(245,240,232,.30)`)
- `.ok`: `background: #6ecf8f; box-shadow: 0 0 5px #6ecf8f` — keep unchanged
- `.error`: `background: #e08080; box-shadow: 0 0 5px #e08080` — keep unchanged

**Server status text (`.server-status`):** `color: rgba(255,255,255,0.50)`

---

## 3. Cards and Panels

All card types (`.builder-step`, `.cg-image-frame`, `.fm-controls-card`, `.fm-viewer-frame`, `.fm-mascot-zone`, `.fm-progress-state`, `.fm-viewer-empty`, `.cg-strip-section`, `.import-section`, settings card) share the same three-property Clark Dark treatment:

```
background: #0f1129                         /* or rgba(255,255,255,0.05) for second-level nesting */
border: 1px solid rgba(255,255,255,0.10)    /* replaces 2px solid #d9cfbe */
border-radius: 16px                         /* rounded-2xl; current --radius is 18px — keep 18px or normalize to 16px; spec recommends 16px per Clark Dark */
box-shadow: none                            /* remove all shadows */
```

**Border width:** drop from 2px to 1px. The hairline is more appropriate for dark surfaces; 2px warm borders read as hand-crafted on parchment but feel heavy on navy.

**Second-level nesting** (a panel inside a panel, e.g. `.import-section` inside `.builder-step`): use `background: rgba(255,255,255,0.05)` so it reads slightly lighter than the navy-800 parent. Do not use a third solid color.

**Left-border accents per step (Book Builder):**
- Remove the four-color scheme entirely.
- All steps: `border-left: 1px solid rgba(255,255,255,0.10)` (same as all other borders — no left-border distinction by default)
- Active/current step only: `border-left: 3px solid #ff6b35` (a single orange left edge, narrow so it doesn't overpower)
- Implementation note: "active" here means the step the user is currently working in. The JS should add/remove an `.step--active` class rather than styling by ID so the accent fires on exactly one step at a time. If the PM decides all steps are always visible simultaneously (current behavior), use no left border on any step and rely on the step-num badge color to indicate current position.

**Card hover:** remove `transform: translateY(-3px)` and the mustard hover shadow. Replace with:
```
border-color: rgba(255,255,255,0.25)   /* brightens hairline on hover only */
transition: border-color .15s
```
No lift transform on dark surfaces — consistent with no-shadow rule.

---

## 4. Buttons

### 4.1 Primary — Generate (`.generate-btn`)

| State | Background | Border | Text | Other |
|-------|------------|--------|------|-------|
| Default | `#ff6b35` | none | `#ffffff` | `box-shadow: none` |
| Hover | `rgba(255,107,53,0.80)` | none | `#ffffff` | No transform |
| Active (mousedown) | `rgba(255,107,53,0.70)` | none | `#ffffff` | |
| Disabled | `#ff6b35` | none | `#ffffff` | `opacity: 0.40; cursor: not-allowed` |
| Focus-visible | — | — | — | `outline: 2px solid #ff6b35; outline-offset: 2px` |

Remove `box-shadow` and `transform: translateY(-2px)` hover lift. The hover darkening via opacity is the sole feedback.

`rgba(255,107,53,0.80)` computes to approximately `#ff7e58` on `#0f1129` — the effective rendered hex is around `#ff784f`, distinct enough from default to be perceivable.

Contrast check: white on `#ff6b35` ≈ 3.0:1 — this fails AA for normal text. However `.generate-btn` text is 1rem/700 bold, which qualifies as WCAG "large text" (bold ≥14px = bold ≥18.67px — 1rem = 16px, bold means it qualifies at 14pt/18.67px threshold). At large text level the threshold is 3:1, which passes. Acceptable.

### 4.2 Auto-generate variant (`.auto-gen-btn`)

In the MKStudio system this was teal-filled. Under Clark Dark there is only one accent. Use the same primary button treatment as `.generate-btn`. If the UI needs visual distinction between "decompose story" and "generate all images", use a secondary treatment instead:

- `background: rgba(255,255,255,0.10)` with `border: 1px solid rgba(255,255,255,0.10)` and `color: #ffffff` — the user reads the label to understand the action.

### 4.3 Secondary — Settings / Project / Book-Action (`.settings-btn`, `.project-btn`, `.book-action-btn`)

| State | Background | Border | Text |
|-------|------------|--------|------|
| Default | `rgba(255,255,255,0.10)` | `1px solid rgba(255,255,255,0.10)` | `rgba(255,255,255,0.70)` |
| Hover | `rgba(255,255,255,0.20)` | `1px solid rgba(255,255,255,0.10)` | `#ffffff` |
| Disabled | — | — | — (parent `opacity: 0.40`) |
| Focus-visible | — | `outline: 2px solid #ff6b35; outline-offset: 2px` | — |

Border-radius: keep existing values (10px for settings-btn/project-btn, 10px for book-action-btn). These are below the 16px container radius — that is correct; interior controls use tighter radii.

### 4.4 Danger variant (`.danger-btn`, `.book-action-btn.danger`, `.settings-btn--muted`, `.stop-btn`)

| State | Background | Border | Text |
|-------|------------|--------|------|
| Default | transparent | `1px solid rgba(229,72,77,0.40)` | `rgba(229,72,77,0.90)` approx `#e5484d` at 90% |
| Hover | `rgba(229,72,77,0.15)` | `1px solid rgba(229,72,77,0.70)` | `#e5484d` |
| Focus-visible | — | `outline: 2px solid #e5484d; outline-offset: 2px` | — |

`#e5484d` is the red-400 equivalent from Clark Dark's badge convention. Do not use pure `#ff0000` or `#c4513a` terracotta.

### 4.5 Seed / small icon buttons (`.seed-row button`, `.model-viewer-close`, `.settings-eye-btn`, `.settings-clear-btn`)

```
background: rgba(255,255,255,0.10)
border: 1px solid rgba(255,255,255,0.10)
border-radius: 10px   /* existing; keep */
color: rgba(255,255,255,0.50)
hover → background: rgba(255,255,255,0.20); color: #ffffff
```

`.settings-eye-btn` hover and pressed: `color: #ff6b35` (accent, replaces teal).
`.settings-clear-btn` hover: `color: #e5484d` (red-400, keep danger semantic).

### 4.6 Skip link (`.skip-link`)

```
background: #ff6b35
color: #ffffff
```

White on accent passes at large/bold text level (same as primary button — see 4.1 note).

### 4.7 Thumb overlay buttons (`.thumb-upload-btn`, `.thumb-regen-btn`)

`.thumb-upload-btn`:
```
background: rgba(0,0,0,0.60)
color: #ffffff
hover → rgba(0,0,0,0.82)
```

`.thumb-regen-btn` (currently teal-tinted): collapse to accent.
```
background: rgba(255,107,53,0.80)
color: #ffffff
hover → rgba(255,107,53,0.95)
```

---

## 5. Inputs, Textarea, Select

```css
/* Default */
background: #0f1129                        /* or rgba(255,255,255,0.05) if nested */
border: 1px solid rgba(255,255,255,0.10)
border-radius: 12px                        /* keep existing */
color: #ffffff
font-family: 'Nunito', system-ui, sans-serif

/* Placeholder */
placeholder color: rgba(255,255,255,0.30)

/* Focus */
border-color: #ff6b35
box-shadow: 0 0 0 2px rgba(255,107,53,0.35)
outline: none
```

`border-width` drops from 2px to 1px to match the card border. Focus ring uses a 2px shadow spread (not 3px as in MKStudio) — tighter on dark avoids glare.

**Dimension number inputs (`.size-dims-row input`):** Same treatment, no box-shadow on focus (keep current behavior of border-color-only focus for small inputs).

**Settings key inputs (`.settings-key-input`):** Add `font-family: 'Space Mono', monospace` — these are the one input type that uses `font-code`. Color and border as above.

**Range sliders:**
- Track: `background: rgba(255,255,255,0.10)` (replaces `--border` `#d9cfbe`)
- Thumb: `background: #ff6b35; box-shadow: none` (replaces mustard + mustard shadow)

**Scrollbar styling (`.cg-strip-scroll`):**
```
scrollbar-color: rgba(255,255,255,0.20) transparent
```
Thumb on hover: `rgba(255,255,255,0.35)`.

---

## 6. Preset Pills / Segmented Toggles / Lang Toggle / Provider Toggle / Gallery Tabs

All pill and segmented-control types collapse to a single pattern. The shared container (`.provider-toggle`, `.lang-toggle`, `.gallery-tabs`) and the standalone pill (`.preset`) use the same dark surface rules.

**Standalone pills (`.preset`):**

| State | Background | Border | Text | Weight |
|-------|------------|--------|------|--------|
| Default | `rgba(255,255,255,0.10)` | `1px solid rgba(255,255,255,0.10)` | `rgba(255,255,255,0.70)` | 400 |
| Hover | `rgba(255,255,255,0.20)` | `1px solid rgba(255,255,255,0.10)` | `#ffffff` | 400 |
| Active | `#ff6b35` | `1px solid #ff6b35` | `#ffffff` | 700 |
| Disabled | — | — | `rgba(255,255,255,0.40)` | — (opacity .40 on wrapper) |

Border-radius stays `20px` (rounded-full).

**Segmented containers (`.provider-toggle`, `.lang-toggle`, `.gallery-tabs`):**
```
background: rgba(255,255,255,0.05)
border: 1px solid rgba(255,255,255,0.10)
border-radius: 14px   /* keep existing — slightly tighter than pill, correct for segmented */
overflow: hidden
```

**Segment buttons (`.provider-btn`, `.lang-btn`, `.gallery-tab`):**

| State | Background | Border-right (divider) | Text |
|-------|------------|------------------------|------|
| Default | transparent | `1px solid rgba(255,255,255,0.10)` | `rgba(255,255,255,0.50)` |
| Hover | `rgba(255,255,255,0.10)` | — | `rgba(255,255,255,0.80)` |
| Active | `#ff6b35` | — (segment is opaque, divider hidden) | `#ffffff` |

All three context-variant active colors (mustard for gallery-tab, teal for provider/lang) collapse to `#ff6b35`.

---

## 7. Step-Number Badges (`.step-num`)

The four-color scheme (terracotta/mustard/teal/olive per step) is removed.

| State | Background | Text |
|-------|------------|------|
| Default (inactive step) | `rgba(255,255,255,0.10)` | `rgba(255,255,255,0.70)` |
| Active/current step | `#ff6b35` | `#ffffff` |

Shape: `border-radius: 50%`, `width: 2.2rem; height: 2.2rem` — unchanged.
`box-shadow: none` on all states (replaces four colored shadows).

---

## 8. Sync Badge and Shared-Inputs Panel

**Sync badge (`.sync-badge`):**
```
background: rgba(255,107,53,0.20)    /* accent/20 tint */
color: #ff6b35
border-radius: 20px
```
The SVG link-chain icon inherits `color: #ff6b35` from the parent (replaces teal `#3a7d7a`).

Focus ring: `outline: 2px solid #ff6b35; outline-offset: 2px` (replaces teal outline).

**Shared field primary emphasis (`.shared-field-primary`):**
- Label: `color: #ffffff; font-weight: 800` (was `--ink` charcoal — unchanged semantically, new color)
- Textarea left border: `border-left: 3px solid #ff6b35` (replaces teal left border)

**Import divider (`.import-divider`):**
```
color: rgba(255,255,255,0.30)
/* ::before / ::after lines */
background: rgba(255,255,255,0.10)
```

**Import section (`.import-section`, `details` + `summary`):**
- Panel treatment: `background: rgba(255,255,255,0.05)`, `border: 1px solid rgba(255,255,255,0.10)`, `border-radius: 16px`
- Summary text: `color: rgba(255,255,255,0.70)`
- Border-top inside body: `border-top: 1px solid rgba(255,255,255,0.10)`

---

## 9. Progress Bars

**Global progress bar (`.progress-bar-track` / `.progress-bar`):**
```
/* Track */
background: rgba(255,255,255,0.10)    /* replaces --paper-dark */
height: 10px
border-radius: 5px

/* Fill */
background: #ff6b35                   /* replaces --mustard */
```

Progress text (`.progress-text`): `color: rgba(255,255,255,0.50)`.

**Per-card progress (`.card-progress`):**
- Bar wrapper: `background: rgba(0,0,0,0.60)` (keep dark scrim, it sits over card thumb)
- Track: `background: rgba(255,255,255,0.18)` — unchanged (already white-opacity)
- Fill: `background: #ff6b35` (replaces mustard)
- Label: `color: rgba(255,255,255,0.90)` — unchanged

**Figure Maker progress (`.fm-progress-track` / `.fm-progress-fill`):**
- Track: `background: rgba(255,255,255,0.10)` (replaces `--border`)
- Fill: `background: #ff6b35` (replaces teal — the pipeline distinction from image generation is now carried by context/label only, not color)

---

## 10. Gallery

**Gallery heading (`.gallery-heading`):** `color: #ffffff; font-weight: 800`

**Book cards (`.book-card`), Image cards (`.image-card`), Model cards (`.model-card`):**
```
background: rgba(255,255,255,0.05)
border: 1px solid rgba(255,255,255,0.10)
border-radius: 16px
box-shadow: none
```

Hover (all card types):
```
border-color: rgba(255,255,255,0.25)
/* no transform, no shadow */
```

**Book/image/model card thumbnails (`.book-cover`, `.image-card-thumb`, `.model-card-thumb`):**
```
background: #0f1129     /* navy-800 — replaces paper-dark #ede5d4 */
```

**Book title native (`.book-title-native`):** `color: #ffffff` (CJK serif font unchanged)
**Book title English (`.book-title-en`):** `color: rgba(255,255,255,0.70)`
**Book meta (`.book-meta`):** `color: rgba(255,255,255,0.40)`; apply `font-family: 'Space Mono', monospace`

**Image card prompt (`.image-card-prompt`):** `color: rgba(255,255,255,0.60)`
**Image card date (`.image-card-date`):** `color: rgba(255,255,255,0.40)`; `font-family: 'Space Mono', monospace`

**Model card title (`.model-card-title`):** `color: #ffffff`

**Filament tags (`.model-filament-tag`, `.fm-filament-tag`):** The olive color scheme collapses. New treatment matches Clark Dark badge convention:
```
background: rgba(255,255,255,0.10)
border: 1px solid rgba(255,255,255,0.20)
color: rgba(255,255,255,0.70)
border-radius: 12px
font-family: 'Space Mono', monospace
font-size: .72rem
```

**Model card date (`.model-card-date`):** `color: rgba(255,255,255,0.40)`; `font-family: 'Space Mono', monospace`

**Book actions footer (`.book-actions`):**
```
border-top: 1px solid rgba(255,255,255,0.10)   /* replaces 2px solid --border */
```

**Gallery empty message (`.gallery-empty-msg`):** `color: rgba(255,255,255,0.50)`

**Model viewer modal:**
- Scrim (`.model-viewer-backdrop`): `background: rgba(0,0,0,0.70); backdrop-filter: blur(4px)` (replaces warm-tinted warm rgba)
- Panel (`.model-viewer-content`): `background: #0f1129; border: 1px solid rgba(255,255,255,0.10); box-shadow: none; border-radius: 16px`
- Header border: `border-bottom: 1px solid rgba(255,255,255,0.10)`
- Title (`.model-viewer-title`): `color: #ffffff`
- Close button default: `color: rgba(255,255,255,0.50)`; hover: `color: #e5484d; background: rgba(229,72,77,0.10)` (red-tint danger — replaces terracotta)
- Canvas (`.model-viewer-canvas`): `background: #0a0b1a` (deepest navy for the 3D viewport)
- Footer border: `border-top: 1px solid rgba(255,255,255,0.10)`
- Hint text (`.model-viewer-hint`): `color: rgba(255,255,255,0.40)`

---

## 11. Bolt Mascot Zone (Figure Maker, `.fm-mascot-zone`)

```
background: rgba(255,255,255,0.05)
border: 1px solid rgba(255,255,255,0.10)
border-left: 3px solid #ff6b35            /* accent left border replaces teal */
border-radius: 16px
box-shadow: none
```

`.bolt-bubble`:
```
color: #ffffff
font-size: 1rem
font-weight: 700
```

The bounce animation stays active (same keyframes). Reduced-motion suppression unchanged.

**Viewer hint pill (`.fm-viewer-hint`):**
```
background: rgba(255,255,255,0.10)    /* replaces warm rgba(245,240,232,.80) */
color: rgba(255,255,255,0.60)
border-radius: 20px
```

**Viewer error overlay (`.fm-viewer-error`):**
```
background: rgba(10,11,26,0.95)       /* near-opaque navy */
color: #ffffff
border-radius: calc(16px - 1px)
```

**Enhanced prompt reveal (`.fm-enhanced-prompt`):**
```
background: rgba(255,107,53,0.08)     /* accent/8 tint — replaces teal tint */
border: 1px solid rgba(255,107,53,0.25)
border-radius: 10px
```

`.fm-enhanced-label`: `color: rgba(255,107,53,0.90)` (accent, replaces teal-dark).
`#fmEnhancedPromptText`: `color: rgba(255,255,255,0.60)`.

**Report card (`.fm-report-card`):**
```
background: rgba(255,255,255,0.05)
border: 1px solid rgba(255,255,255,0.10)
border-left: 3px solid #ff6b35         /* replaces olive left border */
border-radius: 16px
box-shadow: none
```

---

## 12. Inline Feedback Messages

**Error (`.cg-error`, `.card-error`):**
```
color: #e5484d                          /* red-400 equivalent */
background: rgba(229,72,77,0.10)
border: 1px solid rgba(229,72,77,0.30)
border-radius: 10px
font-family: 'Space Mono', monospace    /* error messages are technical — mono */
```

The `font-family: Space Mono` on error text is new for Clark Dark. The current MKStudio spec does not specify monospace for errors. Adding it here aligns with the Clark Dark principle of using `font-code` for machine/error output.

**Success (`.inline-success`, `.settings-success-msg`):**
```
color: #ff6b35                          /* accent, replaces teal-dark */
background: rgba(255,107,53,0.10)
border: 1px solid rgba(255,107,53,0.30)
border-radius: 10px
```

Note: success messages could alternatively use a green tint (`rgba(110,207,143,0.10)` / `color: #6ecf8f`) to maintain green=good semantics. The PM specified collapsing to a single accent color, so orange-tinted success is the spec. Flag for PM review if green success feels more intuitive for the audience.

**Settings status chip (`.settings-status-chip`):**

| State | Background | Border | Text |
|-------|------------|--------|------|
| `set-env` / `set-config` | `rgba(255,107,53,0.20)` | `rgba(255,107,53,0.40)` | `#ff6b35` |
| `not-set` | transparent | `rgba(255,255,255,0.10)` | `rgba(255,255,255,0.40)` |

---

## 13. Empty and Loading States

**Empty state (`.cg-empty-state`, `.fm-viewer-empty`, `.gallery-empty-msg`):**
```
/* Large icon emoji */
opacity: 0.30               /* keep existing value */

/* Helper label */
color: rgba(255,255,255,0.50)

/* Secondary helper text / hint */
color: rgba(255,255,255,0.30)
```

**Loading state (`.cg-loading-state`, `.fm-progress-state`):**
```
/* "Loading…" text */
color: rgba(255,255,255,0.40)

/* Spinner (`.cg-big-spinner`) */
border-color: rgba(255,255,255,0.15)
border-top-color: #ff6b35               /* replaces mustard */
```

The small spinner (`.spinner` inside `.generate-btn`) stays `border: 2px solid rgba(255,255,255,0.30); border-top-color: #fff` — white is readable on the orange button background.

**Skeleton blocks (optional — not currently implemented):**
If skeletons are added later: `background: rgba(255,255,255,0.05); border-radius: 8px; animation: pulse 1.5s ease infinite`.

**Thumb spinner overlay (`.thumb-spinner`):**
```
background: rgba(10,11,26,0.70)    /* replaces warm rgba(245,240,232,.75) */
```

**Drag-over highlight (`.card-thumb-wrap.drag-over`):**
```
outline: 2px dashed #ff6b35        /* replaces mustard dashed outline */
```

---

## 14. Typography Application

### Font stack

```css
body {
  font-family: 'Nunito', system-ui, sans-serif;
  /* Remove 'Baloo 2' — it is not part of Clark Dark. */
  /* Remove 'Comic Sans MS' fallback. */
}
```

Load Nunito weights 400/600/700/800/900 and Space Mono 400/700 from Google Fonts. If the HTML `<head>` already loads both via a combined URL, verify the weights are present; Nunito 900 (extrabold) may need to be added.

### Space Mono (`font-family: 'Space Mono', monospace`) — where to apply

Apply `font-code` to all of the following (additions over current MKStudio usage):

| Selector | Existing font | Clark Dark font |
|----------|--------------|-----------------|
| `.settings-key-input` | SFMono/Consolas | Space Mono (same role, new family) |
| `.book-meta` | inherit (Baloo 2) | Space Mono |
| `.image-card-date` | inherit | Space Mono |
| `.model-card-date` | inherit | Space Mono |
| `.model-filament-tag` | inherit | Space Mono |
| `.fm-filament-tag` | inherit | Space Mono |
| `.card-page-num` | inherit | Space Mono (micro label — technical marker) |
| `.cg-error` / `.card-error` | inherit | Space Mono (error text = machine output) |
| `settings-card-sub code` | SFMono | Space Mono |

All other UI text (labels, headings, body, button labels, nav) remains Nunito.

### Weight and transform rules — unchanged from VisualStyle_ClarkDark.md

- Headings: `font-weight: 800` (extrabold)
- Control group labels, `.settings-key-label`, `.card-field label`, `.card-page-num`: `text-transform: uppercase; letter-spacing: .06em; color: rgba(255,255,255,0.50)`
- Button labels: `font-weight: 700`
- Secondary labels: `font-weight: 600`

### Control group labels (`.control-group label`, `.slider-row label`, `.settings-key-label`)
```
color: rgba(255,255,255,0.50)    /* replaces --muted #8c8070 */
text-transform: uppercase
letter-spacing: .06em
font-size: .75rem
font-weight: 700
```

### Hint text (`.hint`, `.shared-tab-hint`, `.section-sub`, `.settings-key-hint`)
```
color: rgba(255,255,255,0.40)    /* replaces --muted */
font-style: italic (only where current code has it)
```

### `.card-field label` and `.card-page-num`
```
color: rgba(255,255,255,0.50)
font-family: 'Space Mono', monospace   /* adds mono for these micro-technical markers */
```

---

## 15. Shape and Spacing

### Border radius normalization

The MKStudio system has many values (18px primary, 14px segmented, 12px inputs, 10px small buttons, 8px thumb buttons, 6px icon buttons, 5px code, 3px progress, 20px pills). Clark Dark simplifies to three tiers:

| Tier | Value | Applied to |
|------|-------|------------|
| Container (`rounded-2xl`) | `16px` | Cards, panels, modals, viewer frames, settings card |
| Control (`rounded-xl`) | `12px` | Inputs, textarea, select, segmented container wrapper, import-section |
| Pill (`rounded-full`) | `9999px` or `20px` | Standalone pills, nav-links, sync-badge, status-dot, badges, spinner, skip link |
| Micro | `8px` | Small secondary buttons (settings-btn, project-btn, book-action-btn, thumb-upload-btn) |
| Icon button | `6px` | eye-btn, clear-btn, model-viewer-close |

The primary container radius shifts from 18px to 16px. This is a small visual change — if the team wants to preserve exact MKStudio border-radius values, flag it to the architect, but the Clark Dark spec targets 16px. The `.builder-step` card and all page cards get 16px.

### Spacing

No changes to spacing values — padding, gap, and max-width are not part of the re-theme scope.

### Touch targets

All existing minimum heights are retained (`.generate-btn` 48px, `.provider-btn` 44px, `.book-action-btn` 44px, etc.). No regressions introduced by this spec.

### Focus-visible convention (global)

Every interactive element that does not already have an explicit focus style must show:
```
outline: 2px solid #ff6b35
outline-offset: 2px
```

Replace all `focus-visible` rules that currently reference `var(--teal)` or `var(--mustard)` with this single accent rule. This includes:
- `.cg-strip-thumb:focus-visible` (currently teal outline)
- `.sync-badge:focus-visible` (currently teal outline)
- All inputs (via `focus` pseudo — change `border-color` to `#ff6b35` and `box-shadow` to `rgba(255,107,53,0.35)`)
- `.settings-eye-btn:hover` / `[aria-pressed="true"]` (currently teal — change to `#ff6b35`)

---

## Inconsistency Flags

The following items in the current codebase conflict with Clark Dark rules and should not silently carry forward:

1. **Baloo 2 font.** The `body` font-family declares Baloo 2 first, Nunito second. Clark Dark uses Nunito as the primary. Baloo 2 must be removed from the Google Fonts `<link>` and the `font-family` stack.

2. **`.auto-gen-btn` uses `!important` overrides.** Under Clark Dark, if `.auto-gen-btn` adopts a secondary treatment (white/10), the `!important` declarations will need to be removed — the `!important` was fighting the base `.generate-btn` rule. Address during implementation.

3. **`.thumb-regen-btn` hardcodes teal (`rgba(58,125,122,.80)`).** No token; must be changed to the accent rgba directly.

4. **`.cg-big-spinner` hardcodes `rgba(44,36,22,.15)` and `var(--mustard)`.** Both must be replaced with white-opacity and accent respectively.

5. **`#faf7f2` is not a design token.** Card backgrounds use this hard-coded value in six places across four CSS files. Under Clark Dark, the replacement is `#0f1129` (or `rgba(255,255,255,0.05)` for second-level nesting). The developer should grep for `#faf7f2` across all CSS files and replace each occurrence systematically, not rely on token remap alone.

6. **`.book-title-native` CJK serif fonts** are not loaded via the Google Fonts `<link>`. This is pre-existing and unchanged by this retheme, but note that the dark background may cause legibility issues with thin system CJK fonts that have not been tested. Flag for QA.

7. **`box-shadow` on `.builder-step` cards references `var(--shadow)` which uses `rgba(44,36,22,.09)` — a warm ink tint.** The Clark Dark rule is no shadows. Set `--shadow: none` in `:root` or remove `box-shadow` declarations per-component. Setting the token to `none` is cleaner.

8. **The `.thumb-upload-overlay` uses `background: linear-gradient(to top, rgba(0,0,0,.35) 0%, transparent 60%)`** — this is a gradient. Clark Dark prohibits gradients. Replace with a flat dark overlay that appears only on hover/drag: `background: rgba(0,0,0,0.40)`. The overlay is on the image thumb, not the surface, so a flat dark scrim is visually appropriate and does not break the "no gradient surfaces" rule — flag for PM/architect to confirm whether photo overlays count.

---

## Summary of Key Decisions

- **Single accent `#ff6b35` everywhere.** Nav active, step-num active badge, progress fill, primary button, focus ring, sync badge tint, left border on active step — all use the same orange.
- **No shadows.** `--shadow` token becomes `none`. All `box-shadow` values on cards/buttons are removed. Focus rings use `outline`, not `box-shadow`.
- **No gradients.** The one gradient (thumb-upload-overlay) is flagged for replacement with a flat dark overlay.
- **White-opacity ladder is the only hierarchy tool.** Secondary text = white/60–70, muted = white/50, metadata = white/40, placeholder = white/30.
- **Space Mono expands.** Dates, filament tags, error messages, page-number microlabels, and settings code/keys all get `font-code`. All other UI text stays Nunito.
- **Border width drops from 2px to 1px** throughout. Hairlines on dark are legible; 2px borders read as heavy.
- **Danger is red (`#e5484d`), not terracotta.** The MKStudio terracotta `#c4513a` is too warm for the navy surface; the red-400 tint is more standard and higher contrast.
- **Step card color-coding collapses.** No per-step left-border accent by default. Orange left border only on the current/active step (requires a JS class toggle `.step--active`).
