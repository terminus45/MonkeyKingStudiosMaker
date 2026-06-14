# Settings Page — Design Spec
# BookBuilderBot · `settings.html`

Status: Ready for developer-agent implementation
New files: `frontend/settings.html`, `frontend/settings.css`
Shared dependencies: `frontend/style.css` (all MCM tokens — no edits needed)

---

## 1. Gear icon in the header (all pages)

### 1a. Placement

The gear appears at the **far left of `.header-inner`**, before `.header-title`. This is an N-file edit: `book_builder.html`, `character_generator.html`, `figure_maker.html`, `gallery.html`, and the new `settings.html` all receive it.

The current DOM order inside `.header-inner` is:

```
.header-title → .header-nav → .server-status
```

The new order is:

```
a.settings-gear → .header-title → .header-nav → .server-status
```

### 1b. Markup skeleton (one copy per page)

```html
<header>
  <div class="header-inner">

    <a href="settings.html" class="settings-gear" aria-label="Settings">
      <svg aria-hidden="true" focusable="false" width="20" height="20"
           viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83
                 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1
                 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65
                 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A
                 1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0
                 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0
                 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65
                 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0
                 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0
                 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65
                 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0
                 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </a>

    <div class="header-title"> … </div>
    <nav class="header-nav" aria-label="Main navigation"> … </nav>
    <div class="server-status"> … </div>

  </div>
</header>
```

Use a real inline SVG (Feather/Heroicons gear icon path). Do not use an emoji; the SVG scales and respects `currentColor`.

### 1c. CSS for `.settings-gear`

Add to `style.css` — this is a global shared component:

```css
.settings-gear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  color: rgba(245,240,232,.75);
  text-decoration: none;
  flex-shrink: 0;
  transition: background .15s, color .15s;
}
.settings-gear:hover {
  background: rgba(245,240,232,.14);
  color: #f5f0e8;
}
.settings-gear.active {
  background: var(--mustard);
  color: var(--ink);
}
```

`flex-shrink: 0` prevents the icon from collapsing when the nav overflows. The icon sits outside `.header-nav`, so it never participates in the overflow scroll — the nav remains independently scrollable between the gear and the server-status dot.

### 1d. Mobile behaviour

On small screens the header already wraps `.header-nav` in an overflow-x scroll. The gear is before `.header-title` in DOM order and is `flex-shrink: 0`, so it pins to the left edge and never scrolls out of view. No additional mobile rule is needed; the header's existing `flex-wrap: nowrap` on `.header-inner` is correct — the gear + title are fixed anchors.

Touch target: `width: 36px; height: 36px` is slightly below the 44 px guideline. Expand to 44 px via padding so the visual circle stays 36 px but the tap area is adequate:

```css
.settings-gear {
  width: 44px;
  height: 44px;
  /* SVG inside is 20px; the padding gives the larger tap target */
}
```

### 1e. Active state on settings.html

On `settings.html` only, add `class="settings-gear active"` to the anchor.

---

## 2. Settings page (`settings.html`)

### 2a. Page shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Settings · MonkeyKing</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@400;600;700;800&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="settings.css">
</head>
<body>

  <a href="#settingsMain" class="skip-link">Skip to main content</a>

  <header>
    <div class="header-inner">
      <a href="settings.html" class="settings-gear active" aria-label="Settings">
        <!-- SVG gear icon — see section 1b -->
      </a>
      <div class="header-title">
        <span class="title-zh">齐天大圣</span>
        <span class="title-en">MonkeyKing Story Studio</span>
      </div>
      <nav class="header-nav" aria-label="Main navigation">
        <a href="character_generator.html" class="nav-link">🎭 Character Generator</a>
        <a href="book_builder.html"        class="nav-link">📖 Book Builder</a>
        <a href="figure_maker.html"        class="nav-link">🧩 Figure Maker</a>
        <a href="gallery.html"             class="nav-link">🖼 Gallery</a>
      </nav>
      <div class="server-status">
        <span class="status-dot" id="statusDot"></span>
        <span id="statusLabel">Connecting…</span>
      </div>
    </div>
  </header>

  <main class="settings-main" id="settingsMain">

    <div class="settings-card">

      <div class="settings-card-header">
        <h2>API Keys</h2>
        <p class="settings-card-sub">
          Keys are stored server-side in <code>.env</code>. They are never sent to the browser in full.
        </p>
      </div>

      <!-- Key rows (one per provider) — see section 2b for template -->
      <div class="settings-key-list" id="settingsKeyList">
        <!-- injected or static — see section 2b -->
      </div>

      <!-- Save All -->
      <div class="settings-footer">
        <button class="generate-btn" id="settingsSaveAll" style="max-width: 240px;">
          <span id="settingsSaveLabel">Save All</span>
          <div class="spinner hidden" id="settingsSpinner" aria-hidden="true"></div>
        </button>
        <p class="settings-status-msg hidden" id="settingsStatusMsg" role="status" aria-live="polite"></p>
      </div>

    </div>

  </main>

  <script src="settings.js"></script>
</body>
</html>
```

### 2b. Key row template

One `.settings-key-row` per API key. The three providers are: Anthropic, Gemini, Meshy.

```html
<!-- Repeat for each key. "data-key" is the env var name sent to the API. -->
<div class="settings-key-row" data-key="ANTHROPIC_API_KEY">

  <div class="settings-key-label-group">
    <label class="settings-key-label" for="key-anthropic">
      Anthropic
    </label>
    <span class="settings-key-hint">Used by the Book Builder story decomposer</span>
  </div>

  <div class="settings-key-input-group">
    <div class="settings-key-input-wrap">
      <input
        type="password"
        id="key-anthropic"
        class="settings-key-input"
        placeholder="sk-ant-…"
        autocomplete="off"
        spellcheck="false"
        aria-describedby="key-anthropic-status"
      >
      <button
        type="button"
        class="settings-eye-btn"
        aria-pressed="false"
        aria-label="Show API key"
        data-target="key-anthropic"
      >
        <!-- Eye SVG — open eye when aria-pressed=false, slashed eye when true -->
        <svg aria-hidden="true" focusable="false" width="18" height="18"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </button>
      <button
        type="button"
        class="settings-clear-btn"
        aria-label="Clear Anthropic key"
        data-key="ANTHROPIC_API_KEY"
      >✕</button>
    </div>

    <span
      class="settings-status-chip"
      id="key-anthropic-status"
      data-state="unknown"
      aria-live="polite"
    >
      <!-- JS sets: "Set (env)" / "Set (config)" / "Not set" with matching data-state -->
    </span>
  </div>

</div>
```

Provider row details:

| `data-key`          | `<label>` text | `id` for input      | `placeholder`       | hint text                                |
|---------------------|----------------|---------------------|---------------------|------------------------------------------|
| `ANTHROPIC_API_KEY` | Anthropic      | `key-anthropic`     | `sk-ant-…`          | Used by the Book Builder story decomposer |
| `GEMINI_API_KEY`    | Google Gemini  | `key-gemini`        | `AIza…`             | Used by Imagen / Gemini image generation  |
| `MESHY_API_KEY`     | Meshy          | `key-meshy`         | `msy_…`             | Used by the Figure Maker 3D generator     |

### 2c. Status chip states

The `.settings-status-chip` is a small inline badge. Its `data-state` attribute drives the visual:

| `data-state` | Text            | Visual                                                   |
|--------------|-----------------|----------------------------------------------------------|
| `set-env`    | ✓ Set (env)     | Teal fill: `background: rgba(58,125,122,.12)`, `color: var(--teal-dark)`, teal border |
| `set-config` | ✓ Set (config)  | Same teal treatment as `set-env`                         |
| `not-set`    | Not set         | Muted: `background: transparent`, `color: var(--muted)`, `border: 1px solid var(--border)` |
| `unknown`    | —               | Hidden / empty while loading                             |

"env" means the key came from the server's environment variables; "config" means the user previously saved it via this UI. The source string is returned by `GET /settings/keys` as `source: "env" | "config" | null`.

```css
.settings-status-chip {
  display: inline-flex;
  align-items: center;
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .04em;
  border-radius: 12px;
  padding: .18rem .55rem;
  border: 1px solid var(--border);
  color: var(--muted);
  white-space: nowrap;
  min-height: 24px;
}
.settings-status-chip[data-state="set-env"],
.settings-status-chip[data-state="set-config"] {
  background: rgba(58,125,122,.12);
  color: var(--teal-dark);
  border-color: rgba(58,125,122,.35);
}
.settings-status-chip[data-state="not-set"] {
  background: transparent;
  color: var(--muted);
  border-color: var(--border);
}
.settings-status-chip[data-state="unknown"] {
  visibility: hidden;
}
```

### 2d. Show/hide toggle behaviour

The `.settings-eye-btn` toggles the `type` of the paired `<input>` between `"password"` and `"text"`. When `aria-pressed="true"`, the key is visible:
- Swap the SVG to a slashed-eye icon (Feather `eye-off`).
- Update `aria-label` to `"Hide API key"`.
- Update `aria-pressed="true"`.

When `aria-pressed="false"`, reverse all three.

The JS implementation can keep two SVG paths as constants and swap `.innerHTML` of the svg's `<path>` element, or swap between two hidden `<svg>` elements.

### 2e. Inline success / error messaging

There are two levels of feedback:

**Per-row:** Not specified — the chip state update and the input border are sufficient feedback for individual key validation. If a save attempt returns a per-key error, add a `.cg-error` paragraph immediately after the `.settings-key-input-group` for that row. Reuse `.cg-error` from `character_generator.css` (see consistency flag below about extracting it to `style.css`).

**Page-level (Save All):** The `#settingsStatusMsg` paragraph below the Save All button. Two variants:

```css
/* Reuse .cg-error for error state. Add a teal success variant: */
.settings-success-msg {
  margin-top: .4rem;
  font-size: .82rem;
  color: var(--teal-dark);
  background: rgba(58,125,122,.07);
  border: 1px solid rgba(58,125,122,.28);
  border-radius: 10px;
  padding: .45rem .65rem;
  line-height: 1.45;
}
.settings-success-msg.hidden { display: none; }
```

JS applies `.cg-error` for failure and `.settings-success-msg` for success on `#settingsStatusMsg`. Clear the message after 4 seconds.

### 2f. Backend contract

```
GET /settings/keys
Response: {
  "ANTHROPIC_API_KEY": { "set": true,  "masked": "sk-ant-…xY2z", "source": "env" },
  "GEMINI_API_KEY":    { "set": false, "masked": null,            "source": null  },
  "MESHY_API_KEY":     { "set": true,  "masked": "msy_…aB3d",    "source": "config" }
}

POST /settings/keys
Body: { "ANTHROPIC_API_KEY": "sk-ant-…full", "GEMINI_API_KEY": "AIza…full" }
  — only include keys the user has typed into; omit fields with empty inputs.
Response: same shape as GET /settings/keys (returns updated masked view)

DELETE /settings/keys/{key_name}
  — called when user clicks ✕ clear for a single key
Response: { "cleared": true }
```

On page load, `GET /settings/keys` populates each input's `placeholder` with the `masked` value (e.g. `sk-ant-…xY2z`) and sets the chip state. The actual input `value` remains empty — the user types a new value only if they want to change the key.

On "Save All", collect all inputs that have a non-empty `.value` and POST. After success, re-fetch `GET /settings/keys` to refresh chips and placeholders.

On ✕ clear, call `DELETE /settings/keys/{key_name}`, then re-fetch.

---

## 3. Settings page CSS (`settings.css`)

```css
/* ── settings.css — page-specific styles ── */

/* Skip link — copy from character_generator.css until extracted to style.css */
.skip-link {
  position: absolute;
  top: -100px;
  left: 1rem;
  background: var(--mustard);
  color: var(--ink);
  font-weight: 700;
  padding: .5rem 1rem;
  border-radius: 0 0 12px 12px;
  text-decoration: none;
  z-index: 999;
  transition: top .15s;
}
.skip-link:focus { top: 0; }

/* Page layout — single centered column */
.settings-main {
  flex: 1;
  max-width: 680px;        /* narrower than other pages; form content */
  margin: 0 auto;
  width: 100%;
  padding: 2rem 1rem 4rem;
}

/* Settings card */
.settings-card {
  background: #faf7f2;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border-left: 5px solid var(--mustard);
  overflow: hidden;
}

.settings-card-header {
  padding: 1.5rem 1.5rem 0;
  margin-bottom: 1.25rem;
}
.settings-card-header h2 {
  font-size: 1.2rem;
  font-weight: 800;
  color: var(--ink);
  margin-bottom: .3rem;
}
.settings-card-sub {
  font-size: .82rem;
  color: var(--muted);
  line-height: 1.45;
}
.settings-card-sub code {
  background: var(--paper-dark);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: .05rem .35rem;
  font-size: .8rem;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  color: var(--ink-soft);
}

/* Key list */
.settings-key-list {
  display: flex;
  flex-direction: column;
}

/* Key row */
.settings-key-row {
  display: flex;
  flex-direction: column;
  gap: .65rem;
  padding: 1.25rem 1.5rem;
  border-top: 2px solid var(--border);
}

.settings-key-label-group {
  display: flex;
  flex-direction: column;
  gap: .15rem;
}
.settings-key-label {
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);
  /* real <label> — .control-group label pattern from style.css */
}
.settings-key-hint {
  font-size: .75rem;
  color: var(--muted);
  font-weight: 400;
}

.settings-key-input-group {
  display: flex;
  align-items: center;
  gap: .65rem;
  flex-wrap: wrap;
}

.settings-key-input-wrap {
  flex: 1;
  min-width: 200px;
  display: flex;
  align-items: center;
  position: relative;
}
.settings-key-input {
  flex: 1;
  /* inherits textarea/input styles from style.css */
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: .88rem;
  border-radius: 12px;
  padding-right: 4.5rem; /* room for eye + clear buttons */
  /* Override resize: vertical from style.css — inputs don't resize */
  resize: none;
}

/* Eye (show/hide) button */
.settings-eye-btn {
  position: absolute;
  right: 2.25rem;   /* sits left of the clear button */
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--muted);
  padding: .25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  min-height: 32px;
  border-radius: 6px;
  transition: color .15s, background .15s;
}
.settings-eye-btn:hover { color: var(--teal); background: rgba(58,125,122,.08); }
.settings-eye-btn[aria-pressed="true"] { color: var(--teal); }

/* Clear (✕) button */
.settings-clear-btn {
  position: absolute;
  right: .3rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--muted);
  font-size: .85rem;
  padding: .25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  min-height: 32px;
  border-radius: 6px;
  transition: color .15s;
}
.settings-clear-btn:hover { color: var(--terracotta); }

/* Status chip — see section 2c */
.settings-status-chip { /* see section 2c */ }

/* Footer */
.settings-footer {
  padding: 1.25rem 1.5rem 1.5rem;
  border-top: 2px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: .6rem;
}

/* Success message — teal variant of .cg-error */
.settings-success-msg { /* see section 2e */ }

/* ── Responsive ── */
@media (max-width: 600px) {
  .settings-main { padding: 1rem .75rem 3rem; }
  .settings-card-header { padding: 1.25rem 1rem 0; }
  .settings-key-row { padding: 1rem 1rem; }
  .settings-footer { padding: 1rem; }
  .settings-key-input-wrap { min-width: 0; }
}
```

---

## 4. Visual description

The settings page is a single centered card (max-width 680 px) with a mustard left border, matching the `.builder-step` card treatment used throughout the app. The card header has the title "API Keys" and a muted subtitle explaining keys stay server-side.

Each key row is separated by a hairline border. On the left is a stacked label/hint group (uppercase label + muted helper text beneath). On the right, the input takes the remaining width with two icon buttons inset at the trailing edge: a half-opacity eye icon (left) and a small ✕ (right). To the right of the input group sits the status chip — teal-tinted with a checkmark when the key is configured, or a plain muted border when not set.

Below the three rows a "Save All" button in mustard spans up to 240 px. Below it, inline success (teal) or error (terracotta) feedback appears when the POST resolves.

---

## 5. Accessibility notes

- Every `<input type="password">` has a matching `<label for="…">`. No ARIA-only labelling.
- The show/hide toggle uses `<button type="button">` with `aria-pressed` (not a checkbox, not an icon-only anchor). The `aria-label` updates with `aria-pressed` state: "Show API key" → "Hide API key".
- The status chip uses `aria-live="polite"` so screen readers announce key status changes after save/clear without interrupting.
- `#settingsStatusMsg` uses `role="status"` + `aria-live="polite"` for non-urgent page-level feedback.
- Min touch targets: `.settings-eye-btn` and `.settings-clear-btn` are `min-width/height: 32px` — acceptable for secondary in-input controls. The Save All button has `min-height: 48px` from `.generate-btn` in `style.css`.
- Keyboard order: skip link → header nav → key-anthropic input → eye btn → clear btn → chip (non-interactive, skipped) → key-gemini input → … → Save All button. Natural DOM order, no tabindex manipulation needed.
- Contrast: all text on `#faf7f2` card background is `var(--ink)` or `var(--muted)` — both verified >4.5:1 in prior MCM spec. Teal chip text (`var(--teal-dark)` = `#2a5e5b`) on teal-tint background (#eef5f5 approx) needs developer verification for AA — use `font-weight: 700` to compensate if needed.
- The `<code>` element in the subtitle should not be interactive; it is purely presentational.
