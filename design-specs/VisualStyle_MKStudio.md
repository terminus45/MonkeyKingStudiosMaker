# Visual Style Guide — MonkeyKing Story Studio
## "齐天大圣 · MonkeyKing Story Studio"

**Status:** Descriptive reference — documents the implemented design system as of June 2026.
**Source files:** `frontend/style.css`, `frontend/book_builder.css`, `frontend/character_generator.css`, `frontend/figure_maker.css`, `frontend/gallery.css`, `frontend/settings.css`

---

## 1. Design Philosophy

MonkeyKing Story Studio uses a mid-century modern palette applied to a kid-facing creative tool. The visual language is warm, flat, and rounded: a deep charcoal header, a parchment-toned page background, and four accent colors (mustard, terracotta, teal, olive) applied one-at-a-time — never blended into gradients with each other. Every card, button, and border carries softly rounded corners (18 px primary radius) and a warm-tinted shadow that reads as hand-crafted rather than digital-clinical. The brand is bilingual — "齐天大圣" (the Great Sage Equal to Heaven, the Monkey King) followed by the English subtitle — setting a playful, story-first tone. The app is mobile-first with a horizontally scrollable sticky nav; all interactive targets meet a 44 px minimum height.

---

## 2. Color Tokens

All tokens are defined in `:root` in `frontend/style.css`.

### Ink / Text

| CSS custom property | Hex       | Role / usage                                              |
|---------------------|-----------|-----------------------------------------------------------|
| `--ink`             | `#2c2416` | Primary text, icon fills, header background               |
| `--ink-soft`        | `#5a4a38` | Secondary text, placeholder labels, card metadata         |

### Paper / Surfaces

| CSS custom property | Hex       | Role / usage                                              |
|---------------------|-----------|-----------------------------------------------------------|
| `--paper`           | `#f5f0e8` | Body / page background (`background` on `body`)           |
| `--paper-dark`      | `#ede5d4` | Card thumbnails, image placeholder background             |
| `--ctrl-bg`         | `#f0ebe0` | All input / control backgrounds (textarea, select, pills) |
| `--panel-bg`        | `#f5f0e8` | Named alias for paper, used for panel semantic clarity    |

Card interiors (`.builder-step`, `.page-card`, `.book-card`, `.cg-image-frame`, etc.) use `#faf7f2` — a value slightly warmer than pure white but not defined as a token. It sits between `--paper` and `--ctrl-bg` to create a subtle layering effect.

### Borders

| CSS custom property | Hex       | Role / usage                                              |
|---------------------|-----------|-----------------------------------------------------------|
| `--border`          | `#d9cfbe` | All default borders (2 px solid throughout)               |

### Muted / De-emphasized

| CSS custom property | Hex       | Role / usage                                              |
|---------------------|-----------|-----------------------------------------------------------|
| `--muted`           | `#8c8070` | Uppercase `.control-group` labels, hint text, meta dates  |

### Accent Colors

| CSS custom property  | Hex       | Hover / dark variant     | Role / semantic signal                               |
|----------------------|-----------|--------------------------|------------------------------------------------------|
| `--mustard`          | `#e8a020` | `--mustard-dark #b87a10` | Primary CTA, active states, progress bars, step 2    |
| `--terracotta`       | `#c4513a` | `--terracotta-dark #9e3d2a` | Danger, stop actions, error messages, step 1      |
| `--teal`             | `#3a7d7a` | `--teal-dark #2a5e5b`    | Generation output, provider active, focus ring, step 3 |
| `--olive`            | `#6b7c3a` | `--olive-dark #505d2a`   | Export / complete actions, filament tags, step 4     |

### Per-Step Accent Assignment (Book Builder)

| Step | ID        | Left border accent | Badge background | Badge text   | Semantic meaning         |
|------|-----------|--------------------|------------------|--------------|--------------------------|
| 1    | `#step1`  | `--terracotta`     | `--terracotta`   | `#f5f0e8`    | Story concept / setup    |
| 2    | `#step2`  | `--mustard`        | `--mustard`      | `--ink`      | Story editing / content  |
| 3    | `#step3`  | `--teal`           | `--teal`         | `#f5f0e8`    | Image generation         |
| 4    | `#step4`  | `--olive`          | `--olive`        | `#f5f0e8`    | Export / publish         |

Note: step 2 badge uses charcoal text on mustard (not paper-white) to maintain contrast — the same pairing as the generate button.

### Status Indicator (Header Dot)

| State   | Background       | Box-shadow           |
|---------|------------------|----------------------|
| Default | `rgba(245,240,232,.30)` | none          |
| `.ok`   | `#6ecf8f`        | `0 0 5px #6ecf8f`    |
| `.error`| `#e08080`        | `0 0 5px #e08080`    |

---

## 3. Typography

### Font Families

| Family          | Google Fonts weights loaded | Usage                                                   |
|-----------------|-----------------------------|---------------------------------------------------------|
| **Baloo 2**     | 400, 600, 700, 800          | Primary display and UI. `body` font-family first entry. Headings, button labels, nav links, card titles. |
| **Nunito**      | 400, 600, 700, 800          | Fallback display/UI. Loaded alongside Baloo 2; used where Baloo 2 is unavailable. |
| `system-ui`     | —                           | Third fallback in `body` font stack                     |
| `'Comic Sans MS'`| —                          | Last resort fallback (listed in body stack)             |

Body declaration: `font-family: 'Baloo 2', 'Nunito', system-ui, 'Comic Sans MS', sans-serif`

### CJK Serif Stacks (Native Language Content)

Used in `.card-field.native-field`, `.card-field.zh-field`, and `.book-title-native` — applied to native-language storybook text fields and gallery titles:

| Language | Font stack                                          |
|----------|-----------------------------------------------------|
| Chinese (zh) | `'Noto Serif SC', 'SimSun', serif`             |
| Japanese (ja) | `'Noto Serif JP', 'Yu Mincho', serif`          |
| Korean (ko)  | `'Noto Serif KR', 'Nanum Myeongjo', serif`     |

These are not loaded via the Google Fonts `<link>` tag in the current HTML head — the stacks rely on system fonts or separately loaded Noto Serif faces if available. The serif stack contrasts intentionally with the rounded display UI, signaling "this is story content, not UI chrome."

### Type Scale

| Usage                       | Selector / context               | Size          | Weight | Transform / tracking             |
|-----------------------------|----------------------------------|---------------|--------|----------------------------------|
| Header brand (Chinese)      | `.title-zh`                      | `1.35rem`     | 800    | `letter-spacing: .05em`          |
| Header brand (English)      | `.title-en`                      | `.88rem`      | 700    | none                             |
| Nav links                   | `.nav-link`                      | `.82rem`      | 700    | none                             |
| Step / card headings (h2)   | `.step-header h2`                | `1.15rem`     | 800    | none                             |
| Gallery page heading        | `.gallery-heading`               | `1.4rem`      | 800    | `letter-spacing: .01em`          |
| Settings card heading       | `.settings-card-header h2`       | `1.2rem`      | 800    | none                             |
| Section sub-labels          | `.section-sub`                   | `.85rem`      | 400    | color `--muted`                  |
| Control group labels        | `.control-group label`           | `.75rem`      | 700    | uppercase, `letter-spacing: .06em`, color `--muted` |
| Slider row labels           | `.slider-row label`              | `.75rem`      | 700    | uppercase, `letter-spacing: .06em`, color `--muted` |
| Settings key labels         | `.settings-key-label`            | `.75rem`      | 700    | uppercase, `letter-spacing: .06em`, color `--muted` |
| Preset / pill text          | `.preset`                        | `.8rem`       | 400 / 700 active | none                    |
| Generate button             | `.generate-btn`                  | `1rem`        | 700    | `letter-spacing: .02em`          |
| Settings btn / project btn  | `.settings-btn`, `.project-btn`  | `.82rem` / `.8rem` | 600–700 | none                        |
| Hint / caption text         | `.hint`                          | `.72rem`      | 400    | color `--muted`                  |
| Card page number            | `.card-page-num`                 | `.65rem`      | 700    | uppercase, `letter-spacing: .08em` |
| Card field labels           | `.card-field label`              | `.65rem`      | 700    | uppercase, `letter-spacing: .06em` |
| Card body text (textarea)   | `.card-field textarea`           | `.85rem`      | 400    | none                             |
| Native language textarea    | `.native-field textarea`         | `1rem`        | 400    | CJK serif font                   |
| Sync badge                  | `.sync-badge`                    | `.72rem`      | 700    | `letter-spacing: .03em`          |
| Filament tag                | `.model-filament-tag`, `.fm-filament-tag` | `.72rem` / `.75rem` | 700 | uppercase, `letter-spacing: .05em` |
| Inline error / success      | `.cg-error`, `.inline-success`   | `.82rem`      | 400    | `line-height: 1.45`              |
| Code / monospace (settings) | `settings-key-input`, `code`     | `.88rem` / `.8rem` | 400 | `SFMono-Regular`, Consolas, Liberation Mono |

---

## 4. Spacing, Radius & Elevation

### Border Radius

| Token / value | Where used                                                              |
|---------------|-------------------------------------------------------------------------|
| `--radius: 18px` | `.builder-step`, `.page-card`, `.book-card`, `.image-card`, `.model-card`, `.cg-image-frame`, `.fm-viewer-frame`, `.model-viewer-content`, `.fm-report-card`, `.import-section`, settings card |
| `14px`        | `.provider-toggle`, `.lang-toggle`, `.gallery-tabs` (segmented controls) |
| `12px`        | `textarea`, `select`, `input[type="number"]` (form controls), `.skip-link` |
| `12px`        | `.cg-strip-thumb` (session strip thumbnails)                            |
| `10px`        | `.cg-error`, `.inline-success`, `.settings-btn`, `.project-btn`, `.book-action-btn`, `.seed-row button` |
| `8px`         | `.thumb-upload-btn`, `.thumb-regen-btn` (overlay action buttons)        |
| `6px`         | `.model-viewer-close`, `.settings-eye-btn`, `.settings-clear-btn` (icon buttons) |
| `5px`         | `settings-card-sub code` inline code element                           |
| `3px`         | Progress bar tracks and fills; scrollbar thumb                          |
| `50%`         | `.status-dot` (10×10), `.step-num` (2.2rem circle), `.spinner` (18px circle), slider thumb (20×20) |
| `20px`        | `.preset` pills, `.nav-link`, `.header-nav` pills, `.sync-badge`, `.fm-viewer-hint` hint pill, `.model-filament-tag` |

### Spacing

The layout uses `rem`-based spacing without a defined spacing scale token. Common measurements observed:

- Page padding: `1.25rem 1rem` (base `main`), `1.5rem 1rem 3rem` (builder/character/figure), `2rem 1rem 4rem` (settings)
- Section gap (flex column, builder): `2rem`
- Card padding: `1.5rem` (`.builder-step`), `.9rem` (`.card-body`), `.9rem 1rem` (book/model card info)
- Control group internal gap: `.4rem` (label → control)
- Step header gap: `.75rem`
- Header inner gap: `.6rem`

### Elevation

| Token / value                           | Where used                                             |
|-----------------------------------------|--------------------------------------------------------|
| `--shadow: 0 3px 14px rgba(44,36,22,.09)` | All card components: `.builder-step`, `.page-card`, `.book-card`, `.image-card`, `.model-card`, `.cg-image-frame`, etc. |
| `0 3px 10px rgba(44,36,22,.30)`         | Header `box-shadow` (stronger, darker)                 |
| `0 4px 14px rgba(232,160,32,.30)`       | `.generate-btn` default shadow (mustard-tinted)        |
| `0 6px 18px rgba(232,160,32,.40)`       | `.generate-btn:hover` elevated shadow                  |
| `0 4px 14px rgba(58,125,122,.28)`       | `.auto-gen-btn` shadow (teal-tinted)                   |
| `0 2px 6px rgba(196,81,58,.25)`         | Step 1 badge shadow (terracotta)                       |
| `0 2px 6px rgba(232,160,32,.25)`        | Step 2 badge shadow (mustard)                          |
| `0 2px 6px rgba(58,125,122,.25)`        | Step 3 badge shadow (teal)                             |
| `0 2px 6px rgba(107,124,58,.25)`        | Step 4 badge shadow (olive)                            |
| `0 8px 22px rgba(232,160,32,.22)`       | Card hover shadow (mustard glow)                       |
| `0 16px 48px rgba(44,36,22,.30)`        | Modal (`model-viewer-content`) shadow                  |

All shadows use warm-tinted alpha values (the `rgba(44,36,22,…)` base matches `--ink`), not cool blacks. This keeps the depth feeling consistent with the parchment surface palette.

---

## 5. Core Components

### 5.1 Header

A full-width sticky bar (`z-index: 10`) with solid `#2c2416` background and a `0 3px 10px rgba(44,36,22,.30)` box-shadow. Max-width inner container `1400px`, centered.

**Structure (left to right):**
1. `.settings-gear` — 44×44 circular icon link to `settings.html` (gear SVG, `aria-label="Settings"`)
2. `.header-title` — flex baseline row: `.title-zh` (1.35rem/800 paper color) + `.title-en` (.88rem/700 paper at 80% opacity)
3. `.header-nav` — flex, `overflow-x: auto`, `scrollbar-width: none` (horizontal scroll on mobile), `gap: .35rem`
4. `.server-status` — `.status-dot` + text label, right-aligned

**Nav links (`.nav-link`):**

| State   | Background                    | Text color            |
|---------|-------------------------------|-----------------------|
| Default | transparent                   | `rgba(245,240,232,.82)` |
| Hover   | `rgba(245,240,232,.14)`       | `#f5f0e8`             |
| Active  | `var(--mustard)` `#e8a020`    | `var(--ink)` `#2c2416` |

Nav links: `.82rem`, 700 weight, `border-radius: 20px`, `min-height: 36px`, `padding: .35rem .85rem`. Contains emoji + text label. Current nav items: "🎭 Character Generator", "📖 Book Builder", "🧩 Figure Maker", "🖼 Gallery".

**Settings gear (`.settings-gear`):**

| State   | Background                    | Color                 |
|---------|-------------------------------|-----------------------|
| Default | none                          | `rgba(245,240,232,.75)` |
| Hover   | `rgba(245,240,232,.14)`       | `#f5f0e8`             |
| Active  | `var(--mustard)`              | `var(--ink)`          |

---

### 5.2 Generate Button (`.generate-btn`)

The primary CTA. Solid mustard fill, no gradient.

| State              | Background       | Text      | Transform          | Shadow                                  |
|--------------------|------------------|-----------|--------------------|-----------------------------------------|
| Default            | `#e8a020`        | `#2c2416` | none               | `0 4px 14px rgba(232,160,32,.30)`       |
| Hover (not disabled) | `#b87a10`      | `#2c2416` | `translateY(-2px)` | `0 6px 18px rgba(232,160,32,.40)`       |
| Active (mousedown) | `#b87a10`        | `#2c2416` | `translateY(0)`    | —                                       |
| Disabled           | `#e8a020`        | `#2c2416` | none               | — (opacity `.40`)                       |

Properties: `border: none`, `border-radius: var(--radius)` (18px), `padding: .9rem 1.25rem`, `font-size: 1rem`, `font-weight: 700`, `letter-spacing: .02em`, `min-height: 48px`. Contains optional `.spinner` (hidden when not loading) at `18px` with white border.

**Auto-generate variant (`.auto-gen-btn`):**
Override applied in `book_builder.css` using `!important`. Teal fill, paper-white text.

| State   | Background      | Text      |
|---------|-----------------|-----------|
| Default | `#3a7d7a`       | `#f5f0e8` |
| Hover   | `#2a5e5b`       | `#f5f0e8` |

Shadow: `0 4px 14px rgba(58,125,122,.28)`.

---

### 5.3 Preset / Pill Toggles (`.preset`)

Used for style presets and any multi-choice pill group. Flex row with `gap: .35rem`, `flex-wrap: wrap`.

| State   | Background      | Border                  | Text color         | Font weight |
|---------|-----------------|-------------------------|--------------------|-------------|
| Default | `var(--ctrl-bg)` `#f0ebe0` | `2px solid #d9cfbe` | `#5a4a38` | 400 |
| Hover   | `#f7edd8`       | `2px solid #e8a020`     | `#b87a10`          | 400         |
| Active  | `#e8a020`       | `2px solid #e8a020`     | `#2c2416`          | 700         |

Properties: `border-radius: 20px`, `padding: .35rem .8rem`, `font-size: .8rem`, `min-height: 36px`.

---

### 5.4 Provider Toggle / Segmented Controls (`.provider-toggle`)

Also used as `.lang-toggle` (book_builder) and `.gallery-tabs`. All share the same segmented-pill pattern: a wrapping container with a shared border, children share interior dividers.

**Container:** `border: 2px solid var(--border)`, `border-radius: 14px`, `overflow: hidden`. Tabs use `background: var(--ctrl-bg)`.

**Segment buttons (`.provider-btn`, `.lang-btn`, `.gallery-tab`):**

| State   | Background                      | Text color      |
|---------|---------------------------------|-----------------|
| Default | transparent / `var(--ctrl-bg)` | `var(--muted)` / `var(--ink-soft)` |
| Hover   | `rgba(58,125,122,.08)`          | `var(--teal)`   |
| Active  | `var(--teal)` OR `var(--mustard)` | see below      |

Active color varies by context:
- `.provider-btn.active`: teal background, `#f5f0e8` text
- `.lang-btn.active`: teal background, `#f5f0e8` text
- `.gallery-tab.active` / `[aria-selected="true"]`: **mustard** background, `var(--ink)` text

Interior dividers: `border-right: 2px solid var(--border)` on non-last children (or `border-left` for `.provider-btn`). Minimum height 40–44px.

---

### 5.5 Inputs, Textarea, Select

Base rule in `style.css` applies to `textarea`, `select`, `input[type="number"]`:

| State   | Background      | Border                   | Shadow                             |
|---------|-----------------|--------------------------|------------------------------------|
| Default | `#f0ebe0`       | `2px solid #d9cfbe`      | none                               |
| Focus   | `#f0ebe0`       | `2px solid #3a7d7a` (teal) | `0 0 0 3px rgba(58,125,122,.15)` |

Properties: `border-radius: 12px`, `padding: .5rem .7rem`, `font-size: .9rem`, `color: var(--ink)`, `font-family: inherit`, `resize: vertical`, `width: 100%`.

Dimension number inputs (`.size-dims-row input`): narrower variant — `width: 5rem`, `border-radius: 8px`, `text-align: center`, teal focus without outer glow.

Settings API key inputs (`.settings-key-input`): monospace font stack, `border-radius: 12px`, `padding-right: 4.5rem` (space for inset eye/clear buttons).

---

### 5.6 Range Sliders

Track: `height: 5px`, `background: var(--border)`, `border-radius: 3px`, no border.
Thumb: `width: 20px`, `height: 20px`, `background: var(--mustard)`, `border-radius: 50%`, `box-shadow: 0 2px 6px rgba(232,160,32,.35)`.

---

### 5.7 Settings Button (`.settings-btn`)

Secondary action buttons for contextual controls (e.g., "Load Model", "Clear LoRA").

| State                     | Background      | Border                   | Text           |
|---------------------------|-----------------|--------------------------|----------------|
| Default                   | `#f0ebe0`       | `2px solid #d9cfbe`      | `#5a4a38`      |
| Hover                     | `#f0ebe0`       | `2px solid #3a7d7a` (teal) | `#3a7d7a`    |
| `.settings-btn--muted` default | `#f0ebe0` | `2px solid #c4513a`      | `#c4513a`      |
| `.settings-btn--muted` hover | `#c4513a`   | `2px solid #c4513a`      | `#f5f0e8`      |

Properties: `border-radius: 10px`, `padding: .4rem .85rem`, `font-size: .82rem`, `min-height: 36px`.

---

### 5.8 Project / Action Buttons (`.project-btn`, `.book-action-btn`)

Identical base appearance to `.settings-btn` but slightly varied sizing. Both default to `--ctrl-bg` / `--border` / `--ink-soft`. On hover: teal border + text (`.project-btn`) or mustard border + warm cream bg (`.book-action-btn`).

**Danger variant (`.danger-btn` / `.book-action-btn.danger`):**

| State   | Background    | Border / Text            |
|---------|---------------|--------------------------|
| Default | `#f0ebe0`     | `#c4513a` for both       |
| Hover   | `#c4513a`     | text `#f5f0e8`           |

**Stop button (`.stop-btn`):**
Same danger coloring — terracotta border and text by default, solid terracotta fill on hover. `min-height: 48px`, `border-radius: var(--radius)`.

---

### 5.9 Builder Step Cards (`.builder-step`)

The primary workflow container. `background: #faf7f2`, `border: 2px solid var(--border)`, `border-radius: 18px`, `box-shadow: var(--shadow)`, `padding: 1.5rem`.

**Left-border accent:** `border-left: 5px solid <accent>` applied per step ID (see token table in section 2). The shared inputs panel also uses a teal left border: `style="border-left: 5px solid var(--teal)"`.

**Step number badge (`.step-num`):** 2.2rem diameter circle, `display: flex; align-items: center; justify-content: center`, `border-radius: 50%`, `font-size: 1rem; font-weight: 800`. Per-step accent fill and shadow (see section 2 table). Step 2 badge uniquely uses `var(--ink)` charcoal text on mustard.

**Step header (`.step-header`):** `display: flex; align-items: center; gap: .75rem; margin-bottom: 1.1rem`. Contains `.step-num`, `<h2>` (1.15rem/800), and optionally `.project-actions` pushed right with `margin-left: auto`.

Mobile: `padding` reduces to `1.1rem .9rem`; `h2` drops to `1rem`.

---

### 5.10 Shared Inputs Panel & Sync Badge

The cross-tab shared fields (Story Prompt, Character, Style) appear either as a standalone `.builder-step` card (Character Generator, Figure Maker) or as an inline `div.shared-inputs-inline` without its own card (Book Builder).

**`.shared-field-primary`** highlights the most important field per context:
- Label: `color: var(--ink); font-weight: 800` (instead of muted)
- Textarea: `border-left-color: var(--teal); border-left-width: 3px`

**`.sync-badge`:** Inline pill indicating cross-tab sync. `background: rgba(58,125,122,.10)`, `color: var(--teal)`, `border-radius: 20px`, `padding: .28rem .65rem`, `.72rem` / 700 weight. Contains a link-chain SVG icon. Non-interactive (`cursor: default`) but receives `focus-visible` outline: `2px solid var(--teal)`. In the Book Builder inline placement, it lives in a `.sync-badge-row` div (no `margin-left: auto`); in standalone panels it is inside `.step-header` (pushed right).

---

### 5.11 Progress Bars

**Global progress bar (Book Builder step 3, `.progress-bar`):**
Track: `.progress-bar-track` — `height: 10px`, `background: var(--paper-dark)`, `border-radius: 5px`.
Fill: `.progress-bar` — `height: 100%`, `background: var(--mustard)`, `border-radius: 5px`, `transition: width .4s ease`, `width: 0%` default.

**Per-card progress (`.card-progress`):**
Absolutely positioned at card thumbnail bottom. Semi-transparent dark bg `rgba(44,36,22,.7)`. Track: 6px, `rgba(255,255,255,.18)` background. Fill: mustard. Label: `.65rem`, `rgba(255,255,255,.9)`.

**Figure Maker progress (`.fm-progress-track`):**
`height: 12px`, `background: var(--border)` (not paper-dark), fill is **teal** (`var(--teal)`) rather than mustard — distinguishes the 3D generation pipeline from image generation.

---

### 5.12 Gallery Cards (Book / Image / Model)

All three card types share the same base structure: `background: #faf7f2`, `border: 2px solid var(--border)`, `border-radius: 18px`, `box-shadow: var(--shadow)`, `overflow: hidden`.

**Hover state (all card types):**
```
border-color: var(--mustard)
transform: translateY(-3px)
box-shadow: 0 8px 22px rgba(232,160,32,.22)
```

**Book card (`.book-card`):** 1:1 aspect-ratio cover image area (`background: var(--paper-dark)`), then `.book-info` with native serif title + English subtitle + meta, then `.book-actions` footer (border-top) with flex `.book-action-btn` buttons.

**Image card (`.image-card`):** Smaller grid (`minmax(180px, 1fr)`). Same structure: square thumb, then `.image-card-info` with 2-line-clamped `.image-card-prompt` and `.image-card-date`.

**Model card (`.model-card`):** Square thumb with emoji placeholder at opacity .30, `.model-card-info` with title + `.model-filament-tag` + date. Filament tag: olive color scheme — `color: var(--olive-dark)`, `background: rgba(107,124,58,.12)`, `border: 1px solid rgba(107,124,58,.30)`, `border-radius: 12px`.

**Gallery tab bar (`.gallery-tabs`):** Active tab uses mustard (not teal), aligning with "browsing/selection" rather than "generation".

---

### 5.13 3D Model Viewer Modal

Full-viewport overlay: `position: fixed; inset: 0; z-index: 100`.
Backdrop: `background: rgba(44,36,22,.72)`, `backdrop-filter: blur(2px)`.
Content panel: `background: #faf7f2`, `border: 2px solid var(--border)`, `border-radius: 18px`, `box-shadow: 0 16px 48px rgba(44,36,22,.30)`, `max-width: 760px`, `max-height: 90vh`.
Header: `border-bottom: 2px solid var(--border)`, title `.8rem/800`.
Close button: muted icon, hover to terracotta (`color: var(--terracotta)`, `background: rgba(196,81,58,.08)`). `min-width: 36px; min-height: 36px`.
Canvas: `background: var(--paper-dark)`, `min-height: 340px`.
Footer hint: `.72rem`, color `--muted`, `border-top: 1px solid var(--border)`.

Mobile: `max-height: 95vh`, `border-radius: calc(var(--radius) / 2)` (≈9px), canvas `min-height: 260px`.

---

### 5.14 Inline Feedback Messages

**Error (`.cg-error`):**
- `color: var(--terracotta)` `#c4513a`
- `background: rgba(196,81,58,.07)`
- `border: 1px solid rgba(196,81,58,.28)`
- `border-radius: 10px`, `padding: .45rem .65rem`, `font-size: .82rem`, `line-height: 1.45`

**Card-level error (`.card-error`):** Same colors but `border-top: none`, `border-radius: 0 0 var(--radius) var(--radius)` — attaches flush to the bottom of the card thumbnail.

**Success (`.inline-success`):**
- `color: var(--teal-dark)` `#2a5e5b`
- `background: rgba(58,125,122,.07)`
- `border: 1px solid rgba(58,125,122,.28)`
- Same `border-radius: 10px`, `padding: .45rem .65rem`, `font-size: .82rem`, `line-height: 1.45`

**Settings success (`.settings-success-msg`):** Identical teal values to `.inline-success`.

---

### 5.15 Enhanced Prompt Reveal (Figure Maker, `.fm-enhanced-prompt`)

A teal-tinted read-only display box showing the AI-enhanced prompt after generation:
- `background: rgba(58,125,122,.07)`
- `border: 1px solid rgba(58,125,122,.25)`
- `border-radius: 10px`
- Label: `.72rem/700`, uppercase, `color: var(--teal-dark)`. Text: `.85rem`, italic, `color: var(--ink-soft)`.

---

### 5.16 Bolt Mascot Zone (Figure Maker, `.fm-mascot-zone`)

A contextual status/instruction banner using the Bolt emoji as a character mascot. `background: var(--paper-dark)`, `border: 2px solid var(--border)`, `border-left: 5px solid var(--teal)`, `border-radius: var(--radius)`, `box-shadow: var(--shadow)`.

`.bolt-mascot`: `font-size: 2.5rem`, `flex-shrink: 0`.
`.bolt-mascot.bolt-bounce`: vertical bounce animation (`translateY(0)` → `translateY(-5px)`, `0.6s ease infinite alternate`). Suppressed by `prefers-reduced-motion`.
`.bolt-bubble`: `font-size: 1rem; font-weight: 700; color: var(--ink); line-height: 1.4`.

---

### 5.17 Settings Key Rows (`.settings-key-row`)

List of API key fields. Card has `border-left: 5px solid var(--mustard)`. Each row has `border-top: 2px solid var(--border)`, `padding: 1.25rem 1.5rem`.

Status chips (`.settings-status-chip`):

| State                     | Background                      | Text / border            |
|---------------------------|---------------------------------|--------------------------|
| `set-env` or `set-config` | `rgba(58,125,122,.12)`          | `var(--teal-dark)` / `rgba(58,125,122,.35)` |
| `not-set`                 | transparent                     | `var(--muted)` / `var(--border)` |
| `unknown`                 | `visibility: hidden`            | —                        |

Eye (show/hide) and clear (✕) buttons are absolute-positioned inside the input wrapper. Both use `color: var(--muted)` default; eye hover uses `color: var(--teal)`; clear hover uses `color: var(--terracotta)`.

---

### 5.18 Skip Link (`.skip-link`)

`position: absolute; top: -100px; left: 1rem`. On `:focus`, `top: 0`. `background: var(--mustard)`, `color: var(--ink)`, `font-weight: 700`, `border-radius: 0 0 12px 12px`, `z-index: 999`. Present on every page.

---

### 5.19 Spinner (`.spinner`)

18×18px, `border: 2px solid rgba(255,255,255,.3)`, `border-top-color: #fff`, `border-radius: 50%`, `animation: spin .7s linear infinite`. Used inside `.generate-btn` (white on dark button fill) and in `.stop-btn` waiting state. The larger Character Generator spinner (`.cg-big-spinner`) is 40×40, `border-width: 3px`, `border-color: rgba(44,36,22,.15)`, `border-top-color: var(--mustard)`.

---

## 6. Layout & Responsive

### Max-Width Containers

| Page / context           | `max-width` | Class / selector      |
|--------------------------|-------------|-----------------------|
| Global `main`            | `1400px`    | `main`                |
| Book Builder             | `1200px`    | `.builder-main`       |
| Character Generator      | `1200px`    | `.cg-main`            |
| Figure Maker             | `1200px`    | `.fm-main`            |
| Gallery                  | `1300px`    | `.gallery-main`       |
| Settings                 | `680px`     | `.settings-main`      |

All containers use `margin: 0 auto; width: 100%`.

### Two-Column Layouts

| Page              | Grid columns (desktop)      | Breakpoint to single column |
|-------------------|-----------------------------|------------------------------|
| Character Generator | `340px 1fr`               | `700px`                      |
| Figure Maker      | `7fr 4fr`                   | `700px`                      |
| Book Builder (gen controls) | `1fr 1fr 1fr`     | `700px` → `1fr`              |

Character Generator and Figure Maker have sticky right/left control panels (`position: sticky; top: 4rem`) that un-stick at the mobile breakpoint.

### Primary Breakpoint: 700px

Most layout reflowing happens at `max-width: 700px`:
- Two-column grids collapse to single column
- `.page-grid` collapses from `repeat(auto-fill, minmax(300px, 1fr))` to `1fr`
- `.builder-step` padding reduces to `1.1rem .9rem`
- `.step-header h2` reduces to `1rem`
- Sticky controls become static (`position: static`)

### Gallery Breakpoints

| Max-width | Book grid            | Image grid              | Model grid             |
|-----------|----------------------|-------------------------|------------------------|
| default   | `minmax(260px, 1fr)` | `minmax(180px, 1fr)`    | `minmax(260px, 1fr)`   |
| `600px`   | 2 columns fixed      | 3 columns fixed, `.65rem` gap | 2 columns fixed   |
| `380px`   | 1 column             | 2 columns fixed         | 1 column               |

### Sticky Header

`position: sticky; top: 0; z-index: 10`. Control panels clear the header with `top: 4rem`.

### Touch Targets

Minimum 44px height enforced on all interactive elements: `.nav-link` (`min-height: 36px`, the one exception — lighter chrome), `.provider-btn` (44px), `.lang-btn` (40px), `.gallery-tab` (44px), `.generate-btn` (48px), `.stop-btn` (48px), `.book-action-btn` (44px), `.settings-gear` (44×44). The `.settings-btn` and `.project-btn` are 36px min-height — a slight shortfall for touch, but used for secondary/tertiary actions adjacent to larger targets.

---

## 7. Accessibility Notes

### Contrast Ratios (WCAG 2.1)

| Pairing                                       | Approx. ratio | Result                              |
|-----------------------------------------------|---------------|-------------------------------------|
| `--ink` `#2c2416` on `--paper` `#f5f0e8`      | ~13:1         | AAA                                 |
| `--ink` `#2c2416` on `--mustard` `#e8a020`    | ~5.4:1        | AA (normal text, large text)        |
| `#f5f0e8` on `--teal` `#3a7d7a`               | ~5.8:1        | AA                                  |
| `#f5f0e8` on `--terracotta` `#c4513a`         | ~4.7:1        | AA (normal and large/bold text)     |
| `#f5f0e8` on `--olive` `#6b7c3a`              | ~4.9:1        | AA                                  |
| `#f5f0e8` on `--ink` `#2c2416` (header)       | ~14:1         | AAA                                 |
| `--muted` `#8c8070` on `--paper` `#f5f0e8`    | ~3.6:1        | Fails AA for small normal text. PASSES for large text (bold ≥14pt / bold ≥18.67px equivalent). Used on `.75rem/700/uppercase` labels — qualifies as "large" under WCAG. Any non-bold muted text below 14px would be a violation. |

### Skip Links

Every page includes `<a href="#mainId" class="skip-link">Skip to main content</a>` as the first focusable element. Visually hidden off-screen until focused; appears at top-left on focus.

### Focus Rings

All inputs (textarea, select, number input) receive a teal focus ring: `border-color: var(--teal); box-shadow: 0 0 0 3px rgba(58,125,122,.15)`. No `outline: none` without a visible replacement.

`.cg-strip-thumb:focus-visible`: `outline: 3px solid var(--teal); outline-offset: 2px`.
`.sync-badge:focus-visible`: `outline: 2px solid var(--teal); outline-offset: 2px`.

### ARIA Patterns in Use

- **Navigation:** `<nav aria-label="Main navigation">` wrapping `.header-nav`
- **Tablist:** Gallery tabs use `aria-selected="true"` on active tab and panel visibility toggled with `.hidden` class
- **Aria-live:** Used on generation status areas for SSE progress updates (in JS, not CSS)
- **Aria-label:** `.settings-gear` has `aria-label="Settings"`; preset groups have `role="group" aria-label="Style presets"`
- **Aria-pressed:** `.settings-eye-btn[aria-pressed="true"]` for the password reveal button
- **Aria-describedby:** Primary shared input textareas are described by sibling `.hint` elements
- **Hidden spinners:** `.spinner.hidden` / `.hidden { display: none !important }` — functional rather than `aria-hidden`, should be audited if screen readers should announce loading state

### Reduced Motion

`prefers-reduced-motion: reduce` is honored in `figure_maker.css`:
- `.bolt-mascot.bolt-bounce` animation disabled
- `.fm-progress-fill` transition removed
- `.fm-viewer-hint` transition removed

No global reduced-motion rule in `style.css` — `.generate-btn` hover transitions, card hover lifts, and page card transitions are not suppressed. This is a gap if motion sensitivity is a concern for the target audience.

---

## 8. Iconography & Tone

### Emoji Usage

Emoji are used as icons throughout the UI at the navigation and label level:

| Location               | Emoji   | Meaning             |
|------------------------|---------|---------------------|
| Nav: Character Generator | 🎭    | Performance / character |
| Nav: Book Builder      | 📖      | Book / story        |
| Nav: Figure Maker      | 🧩      | Puzzle / 3D figure  |
| Nav: Gallery           | 🖼       | Image gallery       |
| Figure Maker mascot    | ⚡ (Bolt) | AI processing hint |
| Gallery empty covers   | 📚      | Books placeholder   |
| Model card placeholders | 🧸 or similar | 3D figure hint |

The emoji approach avoids custom icon font dependencies and adds a warm, playful quality appropriate for a child-facing story app. They are used as `aria-hidden="true"` decorative elements alongside visible text labels in navigation.

SVG icons appear where semantic meaning requires precision: the settings gear, the sync link-chain icon in `.sync-badge`, and inline SVG stars/arrows in some buttons. These use `aria-hidden="true" focusable="false"` consistently.

### Copy Voice

UI labels lean friendly and direct: "Story Concept", "Tell Claude your story idea", "Generate All Pages", "Save Project". The app avoids dry technical terms (no "Submit", "Execute", "Process"). Action buttons use imperative verbs with optional emoji: "↓ Save Project", "↑ Load Project", "✕ Clear". Error messages use `.cg-error` which inherits no prescribed copy tone — inline error text is set by JavaScript.

The brand juxtaposition of the classical Chinese "齐天大圣" (Great Sage Equal to Heaven) and the English "MonkeyKing Story Studio" models the bilingual, cross-cultural identity of the app itself.
