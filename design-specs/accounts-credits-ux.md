# Accounts + Coin-Bank Wallet — UI/UX Design Spec

**Status:** Spec only. Implementation by developer-agent.
**Scope:** Phase 1 — auth entry points, header affordances, account/wallet page, buy-coins flow. Phase 2 affordances sketched but not implemented.
**Constraint:** Vanilla JS, no build step. Auth UI is a managed hosted widget (Clerk or Supabase Auth). This spec designs everything around that redirect; it does not spec the auth widget itself.
**Design system baseline:** `style.css` tokens (`--paper`, `--paper-dark`, `--ctrl-bg`, `--border`, `--mustard`, `--ink`, `--muted`, `--success`, `--radius`), Nunito + Space Mono fonts, `rounded-full` pills, `border-white/10` hairlines, white-opacity text hierarchy.

---

## 0. Guiding Principles

1. **Additive in Phase 1.** Generation still works for signed-out users exactly as today. The coin wallet is locked behind sign-in but no action is blocked yet. This avoids a hard gate while building trust.
2. **Webhook-authoritative balance.** The Stripe webhook credits coins; the client success-redirect must never assume coins are already added. The success state polls the server.
3. **Two-audience awareness.** The coin metaphor (not dollars) is child-friendly. Unit labels read "coins", never "$0.05/generation". Price in dollars appears only on the buy screen in muted secondary text.
4. **No new design tokens.** The coin chip uses `--mustard` (the single brand accent) and `--success` (`#4ade80`) for credited states. No new colors are introduced.
5. **Header space budget.** The header-inner is `flex, nowrap, gap: .6rem`. Left-to-right order after this change: gear icon → title → nav (flex:1, scrolls) → coin chip → server-status dot. The coin chip replaces nothing; it is appended before the status dot.

---

## 1. Auth Entry and States

### 1.1 Header Structure (all 5 pages + account.html)

Current order:
```
[gear] [title] [nav flex:1] [status-dot]
```

New order:
```
[gear] [title] [nav flex:1] [coin-chip OR sign-in-chip] [status-dot]
```

The new element sits between the nav and the status dot. It is `flex-shrink: 0` so it never collapses. On very narrow viewports (< 480 px) the coin chip label text hides; only the coin icon remains (see Section 4).

### 1.2 Signed-Out State

The slot renders a **"Sign in" chip** — a pill button using the `.preset` / `rounded-full` pattern with `bg-white/10` background. It is NOT accent-orange; accent is reserved for primary generation actions. Hovering applies `bg-white/20`.

```
class: auth-chip  (sign-in variant)
element: <a href="/account.html?intent=signin" ...>
text: "Sign in"
icon: person-silhouette SVG (18x18, aria-hidden), left of text
aria-label: "Sign in to your account"
min-height: 36px (matches .nav-link)
```

Clicking navigates to `account.html` with `?intent=signin`. `account.html` detects the param and immediately fires the managed auth redirect. No inline modal.

### 1.3 Signed-In State

The slot renders a **coin balance chip** (see Section 4) plus a **user avatar button** that opens an account dropdown menu.

```
[coin-chip]  [avatar-btn]
```

The avatar button:
- 32x32 circle, `border: 1.5px solid var(--border)`, `border-radius: 50%`
- Foreground: the user's initials (1–2 chars, Nunito 700, 13px, `color: var(--ink-soft)`) or a profile image if the auth provider returns one
- Background: `var(--paper-dark)` (#0f1129)
- On focus: `box-shadow: 0 0 0 2px #ff6b35` (accent ring, matching existing focus style)
- `aria-label`: "Account menu — [display name]"
- `aria-haspopup="menu"`, `aria-expanded="false/true"`

### 1.4 Account Dropdown Menu

A small floating panel anchored below the avatar button, right-aligned. Appears on click (toggle), disappears on outside click or Escape.

```
position: absolute; right: 0; top: calc(100% + 6px);
background: var(--paper-dark);
border: 1px solid var(--border);
border-radius: 14px;
padding: .5rem 0;
min-width: 180px;
z-index: 200;
box-shadow: 0 8px 32px rgba(0,0,0,.45);
```

Menu items use `role="menuitem"`, Nunito 600, 14px, `padding: .55rem 1rem`, `color: var(--ink-soft)`, hover `background: rgba(255,255,255,.07)`.

Menu item list:
1. **Header row** (not interactive): display name + email, `color: var(--ink)` / `var(--muted)`, `font-size: .8rem`, `padding: .6rem 1rem .4rem`, `border-bottom: 1px solid var(--border)`
2. **My Account** — links to `account.html`
3. **Sign out** — calls auth provider's sign-out, then reloads current page (which re-renders the sign-in chip)

The menu must trap focus when open: Tab cycles through items; Escape closes and returns focus to the avatar button.

### 1.5 Gating Policy (Phase 1)

| Page / action | Signed out | Signed in |
|---|---|---|
| All 5 pages — view | Allowed | Allowed |
| Generation (all 3 generators) | Allowed (as today) | Allowed (as today) |
| Account / wallet page | Redirected to sign-in | Full access |
| Buy coins flow | Redirected to sign-in | Full access |
| Coin chip in header | Shows "Sign in" chip | Shows balance chip |

No generation is gated in Phase 1. The account page itself is the only hard-gated page.

---

## 2. Account / Wallet Page (`account.html`)

### 2.1 Page Shell

Same header as all other pages (gear + title + nav + coin-chip + status-dot). The nav does not have an "active" link for Account — the avatar button is the entry point, not the nav. Add `account.html` to the nav only if explicitly requested in a future task.

Page `<title>`: "Account · MonkeyKing"
`<main>` class: `account-main` — same `max-width: 1400px; margin: 0 auto; padding: 1.25rem 1rem` as Settings.

### 2.2 Layout — Two-Column on Wide, Stacked on Narrow

```
┌─────────────────────────────────────────────────────────┐
│  LEFT COLUMN (flex: 2)          RIGHT COLUMN (flex: 1)  │
│  ┌─────────────────────┐        ┌────────────────────┐  │
│  │  Coin Balance card  │        │  Buy Coins card    │  │
│  └─────────────────────┘        └────────────────────┘  │
│  ┌─────────────────────┐                                 │
│  │  Transaction list   │                                 │
│  └─────────────────────┘                                 │
└─────────────────────────────────────────────────────────┘
```

Responsive breakpoint: below 768 px the two columns stack (left on top, right below).

Grid: `display: grid; grid-template-columns: 2fr 1fr; gap: 1.25rem;` on wide; `grid-template-columns: 1fr` on narrow. The Buy Coins card stacks below the balance card on narrow but remains in the DOM order for correct tab sequence.

### 2.3 Coin Balance Card

Container: `.account-card` — `background: var(--paper-dark); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.5rem 1.75rem;`

```
┌─────────────────────────────────────────────┐
│  YOUR BALANCE                               │
│                                             │
│       🪙  1,250                             │
│            coins                            │
│                                             │
│  100 coins = $1.00                          │
│  ─────────────────────────────────────────  │
│  Last credited: Jun 19, 2026 · +500 coins   │
└─────────────────────────────────────────────┘
```

- Eyebrow label "YOUR BALANCE": `font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted);`
- Balance number `1,250`: `font-size: 3.5rem; font-weight: 900; color: var(--ink); font-family: 'Nunito'; line-height: 1;`
- Coin icon: a simple gold-circle SVG (22px) or the literal character preceding the number. Positioned inline-flex left of the number. Use `color: #f5c842` — **flag: this is the only new non-token color in the spec**. If the team prefers zero new colors, substitute `var(--mustard)` (#ff6b35). See Section 6 for the consistency note.
- "coins" label: `font-size: 1rem; font-weight: 700; color: var(--muted); margin-top: .15rem;`
- Rate line "100 coins = $1.00": `font-size: .8rem; color: var(--muted); font-family: 'Space Mono'; margin-top: .75rem;`
- Divider: `border-top: 1px solid var(--border); margin: .75rem 0;`
- Last-credited line: `font-size: .78rem; color: var(--muted); font-family: 'Space Mono';`

States:
- **Loading:** Replace the number block with a `animate-pulse`-style skeleton — a `52px x 56px` rounded block `background: rgba(255,255,255,.07); border-radius: 8px;`
- **Zero balance:** Number shows `0`; color `rgba(255,255,255,.35)`. The "coins" label and rate line remain. No empty-state illustration needed here; the Buy Coins card is immediately visible.
- **Error fetching:** Replace number with `— coins` in `color: var(--terracotta)` with a refresh icon button (`aria-label: "Retry loading balance"`).

### 2.4 Transaction History Card

Container: same `.account-card` style, stacked below the balance card in the left column.

```
┌─────────────────────────────────────────────┐
│  TRANSACTION HISTORY                        │
│                                             │
│  Jun 19, 2026    Purchase (+1000 coins)   + │
│  Jun 15, 2026    Purchase (+500 coins)    + │
│                                             │
│  [No older transactions]                    │
└─────────────────────────────────────────────┘
```

Each row: `display: flex; justify-content: space-between; align-items: center; padding: .55rem 0; border-bottom: 1px solid var(--border);`

- Date: `font-family: 'Space Mono'; font-size: .78rem; color: var(--muted);`
- Description: `font-size: .88rem; font-weight: 600; color: var(--ink-soft);`
- Amount chip: a small pill — credit: `background: rgba(74,222,128,.12); color: var(--success); border-radius: 20px; padding: .15rem .55rem; font-size: .78rem; font-family: 'Space Mono'; font-weight: 700;` text: `+500`

Phase 2 debit rows: same pill pattern but `background: rgba(255,107,53,.12); color: var(--mustard);` text: `-12`.

**Loading state:** 3 skeleton rows (height 40px each) with `animate-pulse` shimmer.

**Empty state:** Centered within the card — text "No transactions yet" in `color: var(--muted)`, `font-size: .9rem`, with a secondary hint "Buy some coins below to get started!" No emoji needed (this is more of an admin view).

---

## 3. Buy-Coins Flow

### 3.1 Buy-Coins Card (right column of account.html)

Container: `.account-card` (same). Title eyebrow "BUY COINS" + optional subheading "Coins never expire."

Three package cards stacked vertically (they are taller than wide on this column; on the full-width mobile layout they remain stacked):

```
┌─────────────────────────────────────────────┐
│  BUY COINS                                  │
│  Coins never expire.                        │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  500 coins          $5.00             │  │
│  │  Starter pack                         │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  1,000 coins        $10.00         ★  │  │
│  │  Most popular                         │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  2,000 coins        $20.00            │  │
│  │  Best value                           │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  [Checkout with Stripe  →]                  │
└─────────────────────────────────────────────┘
```

**Package card:**
- Default: `background: rgba(255,255,255,.05); border: 1.5px solid var(--border); border-radius: 14px; padding: .85rem 1rem; cursor: pointer;` (matches `.preset` / secondary chip pattern)
- Selected: `border-color: var(--mustard); background: rgba(255,107,53,.08);`
- Hover (not selected): `background: rgba(255,255,255,.09);`
- `role="radio"`, `aria-checked="true/false"`, the group has `role="radiogroup"` with `aria-label="Coin package"`
- Keyboard: arrow keys cycle selection within the group (standard radio group pattern); Space/Enter selects.

**Inside each card (two-row layout):**
- Row 1: `[coin count]` bold left + `[price]` right. Coin count: Nunito 800, 17px, `color: var(--ink)`. Price: Space Mono 700, 15px, `color: var(--muted)`.
- Row 2: descriptor text — Nunito 600, 13px, `color: var(--muted)`. "Most popular" card gets an additional `★ Most popular` tag: `background: rgba(255,107,53,.15); color: var(--mustard); border-radius: 20px; padding: .1rem .45rem; font-size: .7rem; font-weight: 700;` inline right of the descriptor (or row 1 right side — designer preference, keep it small).

**Checkout button:**
```
class: generate-btn (reuses existing orange primary button)
text: "Checkout with Stripe →"
width: 100%
disabled: when no package selected (opacity: .4, pointer-events: none)
aria-label: "Checkout with Stripe for [N] coins at $[X]"
```
On click: shows a spinner (reusing `.spinner` class) inside the button, disables interaction, then does a server-side call to create a Stripe Checkout session and redirects `window.location.href` to the returned Stripe URL.

**Error state (session creation failed):** A red hint line below the button: `color: var(--terracotta); font-size: .82rem;` with the error message. The spinner disappears and the button re-enables.

### 3.2 Stripe Return Pages

Two lightweight pages hosted within the app. Both use the standard page shell (header + nav). They are not full pages — they render inside `account.html` using a `?return=success` or `?return=cancel` query param, detected on page load and switching a visible section.

**Success State (`?return=success&session_id=...`):**

```
┌─────────────────────────────────────────────┐
│  ✓  Payment received!                       │
│                                             │
│  We're crediting your coins now.            │
│  This usually takes a few seconds.          │
│                                             │
│  Your balance:                              │
│  ⟳  Updating…   [animated dots or spinner] │
│                                             │
│  [Go to Account]                            │
└─────────────────────────────────────────────┘
```

Layout: a centered card (max-width 480px, centered via `margin: 2rem auto`), `.account-card` styling. The checkmark icon is a SVG circle-check in `var(--success)` color, 40px.

**Balance refresh behavior:** On load with `?return=success`, the JS immediately fetches `GET /account/balance`. If coins are not yet credited (balance unchanged from before checkout, or baseline is unknown), it polls every 2 seconds for up to 30 seconds. Once the balance increases, it transitions from "Updating..." to a large green number with animation (`transition: color .4s`). If 30 seconds pass without a change, it shows: "Coins will appear shortly — refresh this page if needed." with a manual refresh button.

The "Updating..." placeholder: `color: var(--muted); font-family: 'Space Mono'; font-size: 1rem;` with a small CSS `@keyframes dots` ellipsis animation (no JS needed for the dots animation itself).

The final credited balance display: same large number style as the balance card (Section 2.3).

**Cancel State (`?return=cancel`):**

```
┌─────────────────────────────────────────────┐
│  ✗  Checkout cancelled                      │
│                                             │
│  No payment was taken.                      │
│  Your balance is unchanged.                 │
│                                             │
│  [Buy coins]     [Back to app]              │
└─────────────────────────────────────────────┘
```

Centered card, same shell. The ✗ icon: SVG circle-x in `rgba(255,255,255,.4)` (muted, not alarming red — the user cancelled intentionally). Two secondary chip-buttons side by side. "Buy coins" scrolls/returns to the buy section of account.html; "Back to app" links to `book_builder.html`.

---

## 4. Coin-Balance Chip in Header

### 4.1 Visual Spec

The chip sits between the nav and the server-status dot. It is `flex-shrink: 0`.

**Signed-in with balance:**
```
class: auth-chip  (balance variant)
element: <a href="account.html" aria-label="[N] coins — view account">
content: [coin-icon 16px] [number formatted with comma] [" coins" label hidden on < 480px]
```

Rendering:
```
background: rgba(255,255,255,.08)
border: 1px solid var(--border)
border-radius: 20px
padding: .3rem .7rem
font-size: .8rem
font-weight: 700
color: var(--ink-soft)
display: flex; align-items: center; gap: .3rem
min-height: 36px
transition: background .15s
```

Hover: `background: rgba(255,255,255,.14); color: var(--ink);`
Focus ring: `box-shadow: 0 0 0 2px #ff6b35` (matches all other focus styles).

The number itself: `font-family: 'Space Mono'; font-size: .82rem;` — this signals "technical value" per existing design language conventions.

**Responsive collapse (< 480px):** The " coins" text label is `display: none` (or `visibility: hidden` + zero-width, using a `<span class="chip-label-full">` wrapper). Only icon + number remain. Min-width drops to 44px to respect touch target size.

**Signed-in, zero balance:**
Same chip, number is `0`, no special color change. The chip remains a link to account.html where the user can buy coins.

**Signed-out:**
```
class: auth-chip  (sign-in variant)
element: <a href="account.html?intent=signin">
content: [person-icon 16px] ["Sign in"]
background: rgba(255,255,255,.08)
border: 1px solid var(--border)
```
Same sizing and spacing. No accent color — the chip must not compete with the generate buttons on the page.

**Loading (auth state unknown on page load):**
The chip renders as a skeleton placeholder: `width: 80px; border-radius: 20px; background: rgba(255,255,255,.07); height: 36px; animation: pulse 1.5s ease-in-out infinite;` — same animate-pulse pattern used elsewhere. Transitions to the signed-in or signed-out chip once the auth check resolves (target: < 300ms on warm session).

### 4.2 Balance Refresh

The chip balance is fetched once on page load from `GET /account/balance` (authenticated). It is not polled during normal use. After a successful coin purchase (detected via `BroadcastChannel` or `localStorage` event from the success return page), the chip re-fetches and updates in place.

---

## 5. Phase 2 Affordance — Generation Cost Indicator (Sketch Only, Do Not Implement)

This section documents where to reserve layout space for future per-generation cost confirmation. No implementation required now.

### 5.1 Generate Button Area

Each page (Character Generator, Book Builder, Figure Maker) has a primary orange "Generate" button. In Phase 2, the area immediately below (or above on mobile) this button would contain a cost indicator line:

```
[Generate button]
This will use 12 coins   (Balance: 1,250)
```

The indicator is a single line: `font-size: .78rem; color: var(--muted); text-align: center; margin-top: .35rem;`. "12 coins" is `font-family: 'Space Mono'; color: var(--ink-soft);`. This line is hidden (`display: none`) when the user is signed out or when the feature is disabled.

No layout change is needed today. The generate button already has margin below it. The text fits within that margin without reflow.

### 5.2 Insufficient-Coins Prompt

When a user clicks Generate with insufficient balance, a short inline prompt appears below the button (same region as the cost indicator):

```
Not enough coins.  [Buy more coins →]
```

The "Buy more coins" link uses the `nav-link` style (Nunito 700, rounded pill, hover bg-white/10). The generate button becomes `opacity: .4; pointer-events: none` while this state is active.

This prompt is intentionally lightweight — not a modal, not a toast. It occupies the space already reserved by the cost indicator line.

---

## 6. Consistency Flags

**Flag 1 — Coin icon color.**
The spec uses `#f5c842` (gold) for the coin icon. This is the only color outside the existing design token set. The design system explicitly states "Don't introduce new accent colors." Options: (a) accept `#f5c842` as a single decorative icon color only (not used for text, backgrounds, or borders); (b) substitute `var(--mustard)` (`#ff6b35`) for the coin icon and drop the gold metaphor; (c) add a `--coin` token to `:root` in `style.css`. Recommendation: option (b) is safest for token discipline. This spec flags the decision to the team.

**Flag 2 — No nav entry for Account.**
The current nav has 4 items (Character Generator, Book Builder, Figure Maker, Gallery). Adding Account to the nav would exceed the visual and spatial budget of the nav, which already overflows horizontally on medium viewports. The avatar button in the header is the correct entry point, consistent with every major web app. This is a deliberate non-addition.

**Flag 3 — account.html is the 6th page.**
The CLAUDE.md describes "Five HTML pages." `account.html` becomes the sixth. The static mount, the nav, and the header hand-copy pattern all accommodate this without structural changes to `main.py`.

**Flag 4 — Auth session check on page load.**
Every page currently has no auth state. Adding an auth check on every page load (to render the correct chip state) requires a lightweight `GET /account/me` (or equivalent Clerk/Supabase client SDK call) on every page. This is an architectural consideration for the architect-agent, not a design concern — flagged here so the spec is complete.

**Flag 5 — "Sign in" chip vs. accent color.**
The sign-in chip intentionally does NOT use `var(--mustard)`. The accent is reserved for the primary generation action on each page. Making the sign-in chip orange would create competing focal points. The muted `bg-white/10` pill matches the secondary chip pattern already in the design system.

---

## 7. Accessibility

### 7.1 Roles and Labels

| Element | ARIA role / attribute |
|---|---|
| Coin chip `<a>` | `aria-label="[N] coins — view account"` |
| Sign-in chip `<a>` | `aria-label="Sign in to your account"` |
| Avatar button | `role="button"` (it IS a button), `aria-haspopup="menu"`, `aria-expanded`, `aria-label="Account menu — [name]"` |
| Dropdown `<ul>` | `role="menu"` |
| Dropdown items | `role="menuitem"` |
| Package cards (buy coins) | `role="radio"` inside `role="radiogroup"` |
| Balance number | `aria-live="polite"` on the container so screen readers announce updates after polling |
| Success/cancel cards | `role="status"` on the outcome heading so it announces on navigation |

### 7.2 Keyboard Navigation

- Tab from nav → coin chip → avatar button → status dot. No skip-to needed for the chip (it is in the natural tab order).
- Avatar dropdown: Tab/Shift-Tab cycles items; Escape closes and returns focus to avatar button; click outside closes. Arrow Up/Down also cycle items (standard menu pattern).
- Package radio group: Tab enters the group; arrow keys cycle selection; Tab exits to the Checkout button.
- All interactive elements have a visible focus ring: `box-shadow: 0 0 0 2px #ff6b35` — matching the existing `textarea:focus` / `select:focus` pattern in `style.css`.

### 7.3 Contrast

- Balance number (`var(--ink)`, #ffffff on `var(--paper-dark)` #0f1129): contrast ratio ~18:1. Passes AAA.
- Muted text (`var(--muted)`, rgba(255,255,255,.5) on #0f1129): effective #808080 on #0f1129 — approximately 5.7:1. Passes AA for normal text, borderline for small text. The Space Mono numbers are 12–14px; prefer font-weight 700 to compensate (bold improves legibility at these sizes).
- Green credit chip (`var(--success)`, #4ade80 on rgba(74,222,128,.12) bg on #0f1129): the text color is the important one — #4ade80 on #0f1129 is ~8.5:1. Passes AA.
- Terracotta error (`var(--terracotta)`, #e5484d on #0f1129): ~4.8:1. Passes AA.

### 7.4 Motion

Balance number update (polling success): `transition: color .4s ease` only. No scale transforms, no bounce. The chip update on the header: no animation — value changes in place. This respects `prefers-reduced-motion` without needing an explicit media query (there are no new keyframe animations except the loading dots on the success page, which should be wrapped in `@media (prefers-reduced-motion: no-preference)` with a static ellipsis fallback).

---

## 8. ASCII Mockups

### Header — Signed Out

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ⚙  🤖 Monkey King Studios  [🎭 Character Generator] [📖 Book Builder]         │
│                             [🧩 Figure Maker] [🖼 Gallery]   [Sign in]  •      │
└────────────────────────────────────────────────────────────────────────────────┘
                                                               ^^^^^^^^^  ^
                                                               auth-chip  status-dot
                                                               bg-white/8
                                                               pill shape
```

### Header — Signed In (1,250 coins)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ⚙  🤖 Monkey King Studios  [🎭 Character Generator] [📖 Book Builder]         │
│                             [🧩 Figure Maker] [🖼 Gallery]  [⬤ 1,250 coins] JD •│
└────────────────────────────────────────────────────────────────────────────────┘
                                                              ^^^^^^^^^^^^^^^ ^^
                                                              coin chip       avatar circle
                                                              Space Mono num  32x32, initials
```

### Account / Wallet Page (wide layout)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  HEADER (as above, signed in)                                                  │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────────────────┐  ┌─────────────────────────┐   │
│  │  YOUR BALANCE                            │  │  BUY COINS              │   │
│  │                                          │  │  Coins never expire.    │   │
│  │      🪙  1,250                           │  │                         │   │
│  │           coins                          │  │  ┌─────────────────────┐│   │
│  │                                          │  │  │ 500 coins    $5.00  ││   │
│  │  100 coins = $1.00                       │  │  │ Starter pack        ││   │
│  │  ─────────────────────────────────────   │  │  └─────────────────────┘│   │
│  │  Last credited: Jun 19, 2026 · +500      │  │                         │   │
│  └──────────────────────────────────────────┘  │  ┌─────────────────────┐│   │
│                                                │  │ 1,000 coins  $10.00 ││   │
│  ┌──────────────────────────────────────────┐  │  │ Most popular    ★   ││   │
│  │  TRANSACTION HISTORY                     │  │  └─────────────────────┘│   │
│  │                                          │  │   ^ selected: orange    │   │
│  │  Jun 19, 2026  Purchase   +500 coins     │  │     border + bg tint    │   │
│  │  Jun 15, 2026  Purchase   +1000 coins    │  │  ┌─────────────────────┐│   │
│  │  Jun 02, 2026  Purchase   +500 coins     │  │  │ 2,000 coins  $20.00 ││   │
│  │                                          │  │  │ Best value          ││   │
│  │  [No older transactions]                 │  │  └─────────────────────┘│   │
│  └──────────────────────────────────────────┘  │                         │   │
│                                                │  [Checkout with Stripe →]│   │
│                                                └─────────────────────────┘   │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Buy-Coins Success State

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                                        │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│                    ┌────────────────────────────────────┐                     │
│                    │                                    │                     │
│                    │    (✓)  Payment received!          │                     │
│                    │         green SVG, 40px            │                     │
│                    │                                    │                     │
│                    │  We're crediting your coins now.   │                     │
│                    │  This usually takes a few seconds. │                     │
│                    │                                    │                     │
│                    │  Your balance:                     │                     │
│                    │  ⟳  Updating...                   │  ← polls every 2s  │
│                    │                                    │                     │
│                    │  (after credit lands:)             │                     │
│                    │       🪙  1,750                    │                     │
│                    │            coins                   │                     │
│                    │                                    │                     │
│                    │       [Go to Account]              │                     │
│                    └────────────────────────────────────┘                     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Buy-Coins Cancel State

```
│                    ┌────────────────────────────────────┐                     │
│                    │                                    │                     │
│                    │    (✗)  Checkout cancelled         │                     │
│                    │         muted circle-x SVG         │                     │
│                    │                                    │                     │
│                    │  No payment was taken.             │                     │
│                    │  Your balance is unchanged.        │                     │
│                    │                                    │                     │
│                    │  [Buy coins]   [Back to app]       │                     │
│                    └────────────────────────────────────┘                     │
```

### Phase 2 Generate Button Area (sketch)

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │         Generate Story   →                  │   │
│  └─────────────────────────────────────────────┘   │
│      This will use 12 coins  (Balance: 1,250)      │  ← hidden today
│                                                     │
└─────────────────────────────────────────────────────┘

Insufficient coins variant:
│      Not enough coins.  [Buy more coins →]         │
│      [Generate button is disabled, opacity: .4]    │
```

---

## 9. New File / CSS Class Summary

For the developer-agent:

**New page:** `frontend/account.html` + `frontend/account.css` (new CSS file, same pattern as `settings.css`). `account.js` as non-module script.

**New CSS classes (all in `account.css` or `style.css` per scope):**

In `style.css` (shared, used on all pages for the header chip + avatar):
- `.auth-chip` — base pill styles for both sign-in and balance variants
- `.auth-chip--balance` — modifier: Space Mono number, coin icon alignment
- `.auth-chip--signin` — modifier: person icon
- `.auth-avatar-btn` — 32x32 circle button
- `.auth-menu` — floating dropdown panel
- `.auth-menu__item` — menu row

In `account.css` (page-scoped):
- `.account-main` — page layout (max-width, padding, grid)
- `.account-card` — card shell (matches `.settings-card` pattern)
- `.account-balance-number` — 3.5rem/900 weight number
- `.account-txn-row` — transaction list item row
- `.account-credit-chip` / `.account-debit-chip` — colored amount pills
- `.pkg-card` — coin package selectable card
- `.pkg-card--selected` — selected state
- `.pkg-card--popular` — "most popular" modifier
- `.pkg-star-tag` — inline "Most popular ★" tag
- `.buy-error` — inline error under checkout button
- `.return-card` — centered success/cancel outcome card
- `.balance-updating` — "Updating..." slot (polling state)
- `.balance-credited` — credited number (post-poll state)

**Hand-copy header addition (all 6 pages):** The `<div class="server-status">` block gains a preceding `<div id="authChip" class="auth-chip">` and `<button id="avatarBtn" class="auth-avatar-btn">` element. These are populated by `auth.js` (a new shared non-module script loaded before each page's own script, similar to `shared_inputs.js`).

`auth.js` responsibilities: on load, call `GET /account/me` (or Clerk/Supabase SDK), set the chip to loading skeleton, then render the correct variant. Expose `window.Auth.getBalance()` for the header chip refresh after a purchase.
