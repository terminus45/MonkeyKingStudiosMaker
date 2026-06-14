# Visual Style — Clark's Rocket Studio

The design language of the app, derived from the actual codebase (`tailwind.config.js`, `index.css`, and component usage). This is the reference for keeping new UI consistent. **All styling is Tailwind utility classes** — no inline styles, no CSS modules.

## Personality

A friendly, playful, "space mission control for a 6-year-old" feel: dark cosmic background, one warm rocket-orange accent, big rounded shapes, generous spacing, and an emoji-forward, encouraging voice (the mascot "Bolt" 🤖). Serious technical detail (print analysis, debug logs) is present but visually de-emphasized so it never competes with the kid-facing flow.

## Color palette

Defined in `tailwind.config.js` and `index.css`.

| Token | Hex | Role |
|---|---|---|
| `navy` (DEFAULT) | `#0a0b1a` | App background (near-black deep navy) — set on `:root` |
| `navy-800` | `#0f1129` | Primary surface (cards, panels, inputs, bottom bar) |
| `accent` | `#ff6b35` | Rocket orange — the single brand/action color |
| white | `#ffffff` | Default text color |

**Accent is used sparingly and deliberately** — primary buttons (`bg-accent`, hover `bg-accent/80`), the active tab, the app title, progress fill, and focus rings (`focus:ring-accent`). Never use it for large background areas. Tinted accent (`bg-accent/20`) appears only for subtle highlight chips.

### Surfaces & elevation (no shadows — elevation via translucency)
Layered white/black overlays on the navy base create depth:
- **`bg-white/5`** — subtle surface / secondary card
- **`bg-white/10`** — standard interactive surface (chips, secondary buttons); hover → `bg-white/20`
- **`bg-navy-800`** — solid panel / input background
- **`bg-black/40`–`/70`** — scrims and overlay controls (e.g. download buttons floating over the 3D viewer), usually with `backdrop-blur-sm`

### Borders
One hairline border throughout: **`border-white/10`** (by far the dominant border — 17 uses). Occasionally `border-white/25` for a slightly stronger divider. Borders define card/panel edges against the dark background.

### Text opacity scale
Text hierarchy is expressed by **white opacity**, not by color. Consistent ladder:
- `text-white` (full) — primary headings / key values
- `text-white/80`, `/70`, `/60` — body and labels
- `text-white/50`, `/40` — secondary / metadata
- `text-white/30`, `/25`, `/20` — hints, placeholders, disabled, debug chrome

Placeholders use `placeholder:text-white/20–30`.

## Typography

Two fonts, loaded from Google Fonts in `index.html`:

| Family | Tailwind | Weights | Use |
|---|---|---|---|
| **Nunito** | `font-ui` (default) | 400/600/700/800/900 | All UI text — rounded, friendly sans |
| **Space Mono** | `font-code` | 400/700 | Codes, IDs, timestamps, metadata, technical labels, debug log |

`font-code` is the second most common font class (19 uses) — it signals "machine/technical" content (job IDs, dates, dimensions, the debug console) and visually separates it from kid-facing copy.

**Weights**: headings are heavy — `font-extrabold` (app title, section headers); buttons/labels are `font-bold` / `font-semibold`. Body rarely lighter than `font-semibold`, reinforcing the chunky, confident look. Labels/eyebrows use `uppercase tracking-widest` at small sizes with low opacity.

## Shape language

Large, soft corners everywhere — nothing sharp:
- **`rounded-2xl`** — cards, panels, the 3D viewer, primary inputs/buttons (the signature radius, 12 uses)
- **`rounded-xl`** — smaller controls, settings inputs, overlay buttons (7 uses)
- **`rounded-full`** — pills: quick-pick chips, tab segmented control, status badges, the round submit button (8 uses)

## Spacing & layout

- Comfortable padding: cards `p-4`/`p-6`, inputs `px-4 py-3` to `px-5 py-4`.
- Vertical rhythm via `gap-3`/`gap-4`/`gap-6` flex/grid stacks.
- Content centered in a `max-w-6xl mx-auto` column; the create form narrows to `max-w-xl`.
- Ready view is a responsive grid: single column on mobile, `lg:grid-cols-[7fr_4fr]` (viewer | info panels) on desktop.
- **Touch targets ≥ 44pt** (`min-w-[44px] min-h-[44px]`); mobile tab bar items `min-h-[56px]`.
- **iOS safe areas** respected globally (`env(safe-area-inset-*)` on `body`; `pb-[max(8px,env(safe-area-inset-bottom))]` on the fixed mobile tab bar).

## Components & states

- **Primary button**: `bg-accent` text-white `rounded-2xl` `font-bold`, hover `bg-accent/80`, disabled `opacity-40`.
- **Secondary / chip**: `bg-white/10` `rounded-full`, hover `bg-white/20`, disabled `opacity-40`.
- **Card / panel**: `bg-navy-800` (or `bg-white/5`) + `border border-white/10` + `rounded-2xl`.
- **Input**: `bg-navy-800`/`bg-white/5`, `border-white/10`, `rounded-2xl`/`xl`, `focus:outline-none focus:ring-2 focus:ring-accent`.
- **Badge** (e.g. "set", error count): tiny `rounded-full`/`rounded` pill, `font-code`, tinted bg (`bg-green-500/20 text-green-400`, `bg-red-500/30 text-red-300`).
- **State conventions**:
  - *Disabled* → `opacity-40`/`50`.
  - *Loading* → `animate-pulse` skeleton blocks (`bg-white/5 rounded-2xl`); textual "Loading…".
  - *Empty* → centered: large emoji + `font-semibold` line + muted helper text (`text-white/25`).
  - *Error* → red-tinted text (`text-red-400`) with the message in `font-code`.

## Motion

Restrained and quick:
- **`transition-colors`** is the default interaction transition (hover/active) — used almost everywhere (19×).
- `transition-opacity` for show/hide; `duration-500` easing only on the progress bar fill.
- `backdrop-blur-sm` on overlays and the mobile tab bar.
- Playful accents used sparingly: `animate-bounce` (mascot), `animate-pulse` (loading skeletons), and the 3D model auto-rotates (resuming 10s after interaction).

## Iconography & voice

- **Emoji as icons** — 🚀 (brand/create), 📚 (gallery), ⚙️ (settings), 🧊/🪐 (models/empty), 🗑 (delete), 🎨 (retexture), 🤖 (mascot). No icon-font/SVG icon set.
- **Copy is warm and encouraging**, addressed to Clark by name, short, with a single trailing emoji ("Ta-da! Here's your model! 🎉", "What do you want to build today, Clark? 🌟").

## Two-audience principle

The UI serves Clark (6) and his dad simultaneously: Clark sees **colors and simple choices only**; material/nozzle/printer logic and the debug console are present but rendered in low-opacity `font-code` "technical" styling so they recede. Keep kid-facing actions big, rounded, accent-colored, and emoji-labeled; keep technical/admin surfaces muted and monospaced.

## Quick do/don't

- **Do** build on the navy base with `white/5`–`white/10` translucent surfaces and `border-white/10`.
- **Do** reserve `accent` (`#ff6b35`) for the single most important action / active state on a screen.
- **Do** use `rounded-2xl` for containers, `rounded-full` for pills, `font-code` for anything technical.
- **Don't** introduce shadows, gradients, new accent colors, or a second sans font.
- **Don't** express hierarchy with new gray colors — use the white-opacity ladder.
