# Cover Title Ruby Typography — Multi-Script Design Spec

**Scope:** CSS spec for `.cover-title-ruby` and `.cover-title-ruby rt` in `storybook_print.js`,
covering Chinese (pinyin), Japanese (romaji), Korean (Revised Romanization).  
**Status:** Spec only — implementation by developer-agent.  
**File to edit:** `frontend/storybook_print.js` (the `<style>` block inside `buildStorybookHTML`).

---

## 1. Title Character Size and Ruby Size

### Current state (what exists)

```css
.cover-title-native { font-size: 4rem; letter-spacing: .1em; }
.cover-title-ruby   { line-height: 2; letter-spacing: 0; margin-bottom: .5rem; }
.cover-title-ruby rt { font-size: .34em; }
```

The inner-page reference point is `.text-ruby { font-size: 3.2rem; line-height: 2.8 }` with
`rt { font-size: .5em }`. Those inner-page values were deliberately enlarged for two-up legibility.

### Problem with 4rem on the ruby variant

At 4rem the ruby reading tokens sit in a line box determined by `line-height: 2` (= 8rem per line).
The `rt` at `.34em` of 4rem = **1.36rem rendered**, or approximately 19 px at 96 dpi.
In two-up print (≈50% scale) that becomes ~9.5 px — borderline for normal reading and below
threshold for readers with slight vision difficulty. Additionally, a long Japanese romaji token
(e.g. "gakkō" = 5 characters with macron, a wide glyph) above a 4rem kanji frequently overflows
the pair width, causing the browser ruby algorithm to push adjacent pairs apart unevenly.

### Recommendation: 3.4rem base for the ruby cover title

| Property | Value | Rationale |
|---|---|---|
| `.cover-title-ruby` base font-size | `3.4rem` | Reduces character size by 15% from 4rem; gives the ruby token more room relative to the pair width; still clearly larger than a body heading; consistent with inner-page ruby at 3.2rem |
| `.cover-title-ruby rt` font-size | `.42em` | Resolves to 1.43rem (≈20px at 96dpi). At two-up (~50%) = 10px — at the low end but held by the large inner-page `rt` (.5em × 3.2rem = 16px → 8px two-up) for consistency. The cover must be slightly larger because it is the book's first text the reader sees. |
| `.cover-title-ruby` line-height | `2.6` | The increased `rt` size (.42em vs .34em) needs more vertical clearance above the base line. 2.6 × 3.4rem = 8.84rem per line, giving ≈1.43rem above the character cap-height for the ruby token plus breathing room. Without this, macrons (ō, ū) clip into the line above on the second wrapped line. |

**Two-up legibility check:**
- Base character: 3.4rem × 50% = 1.7rem ≈ 27px. Clear.
- `rt` reading: 1.43rem × 50% = 0.715rem ≈ 11.4px. Readable for a title (short strings, 2–6 chars per ruby token). This is the floor — do not reduce `rt` below `.40em` at this base size.

The non-ruby `.cover-title-native` stays at 4rem. The two values diverge intentionally: the ruby
variant trades 0.6rem of base-character size for meaningful `rt` legibility and romaji overflow headroom.

---

## 2. Wide-Reading Handling (Romaji Overflow)

### The problem

A Japanese title like 学校 (gakkō / empty) produces:
- `<ruby>学<rt>gak·kō</rt></ruby><ruby>校<rt></rt></ruby>` (developer assigns readings per token)
- The `rt` text "gakkō" at 1.43rem is approximately 60–70px wide in a sans-serif font.
- The base character 学 at 3.4rem is approximately 54px wide (CJK glyphs approximate 1em wide).
- The ruby pair `ruby-align: center` will expand the base character's inline width to match the
  wider `rt`, inserting whitespace on both sides of 学. When the adjacent 校 has an empty `rt`, it
  does not expand — so the two characters appear unevenly spaced.

Korean is less severe (RR syllables "won", "sung" are 3–4 chars, close to the em width of Hangul
glyphs at this size). Chinese pinyin tokens (1–2 syllables per character) are typically narrower
than the base character at 3.4rem. Japanese is the primary target.

### Recommended approach: controlled natural expansion + allow wrapping

Do not attempt to compress the `rt` further or clip it. Instead:

**a) Keep `ruby-align: center` (do not change to `space-around` or `start`)**

`center` is correct: when `rt` is wider than the base, it expands the pair symmetrically. This is
the CSS specification's intended behavior. `space-around` or `start` would cause the `rt` to
overflow one side, which is worse.

**b) Allow the title to wrap across lines**

The cover is a centered block and wrapping is acceptable (children's book titles are often 4–8
characters in CJK). A two-line title with ruby reads beautifully on a centered cover. Specify
`max-width` to control where the line break occurs (see Section 3).

Do NOT add `white-space: nowrap`. Do NOT add `overflow: hidden` or `overflow: scroll`.

**c) Reduce `rt` font-weight to `400` on the cover (vs. `500` on inner pages)**

The inner-page global `rt { font-weight: 500 }` is sized for 3.2rem text in a two-column spread.
At the cover's 3.4rem × .42em the `rt` is already larger and heavier weight adds width. Setting
`.cover-title-ruby rt { font-weight: 400 }` trims approximately 3–5% from the measured width of
each `rt` token, reducing overflow pressure without changing the visual appearance meaningfully.
This is the only weight deviation from inner pages.

**d) `letter-spacing: 0` on `rt` (already set globally, confirm it is inherited)**

The global `rt { letter-spacing: 0 }` (set via the inline `<style>` rule at line 255 of the
current file) should apply to all `rt`. The `.cover-title-ruby` already resets `letter-spacing: 0`
on the ruby container, which is correct. Confirm the developer does not add `letter-spacing` back
onto the `rt` override.

**e) Do not add `min-inline-size` on `ruby` pairs**

Adding a minimum width on ruby pairs (sometimes used to force CJK mono spacing) would push Korean
pairs apart unnaturally because Hangul word-spaces already provide inter-word separation.
Avoid this.

---

## 3. Line Wrapping and Spacing

### max-width

Set `max-width: 80%` on `.cover-title-ruby`. Rationale:
- The cover sheet is A4 landscape (297 × 210 mm). The `<body>` has `max-width: 900px; margin: 0 auto`.
  At 900px, 80% = 720px. A 6-character Japanese title at 3.4rem = ≈204px of character width plus ruby
  expansion — a title up to ≈10 characters will fit on one line; beyond that it wraps gracefully.
- Korean titles with spaces already wrap at word boundaries; the max-width prevents a very long title
  from overflowing into the cover image area.
- Chinese titles are typically 4–6 characters and rarely need wrapping.

At two-up scale (A5 effective, 720px → 360px equivalent), 80% of the book block is ~360px. A 3-character
Chinese title at 3.4rem × 50% ≈ 82px fits easily on one line even after ruby expansion.

Do not use a `max-width` in `px` because `buildStorybookHTML` renders into a browser `<body>` whose
width varies (screen preview vs. print). The percentage keeps the title proportional.

### line-height and inter-line gap for wrapped titles

Use `line-height: 2.6` (specified in Section 1). At 3.4rem:
- 2.6 × 3.4rem = 8.84rem per line.
- The `rt` at .42em = 1.43rem sits above the character cap-height (≈2.5rem at 3.4rem), leaving
  ≈8.84 – 2.5 – 1.43 = 4.91rem of space distributed as leading above and below. The ruby token is
  well clear of the descender area of the line above.
- On a two-line title the gap between the `rt` of line 2 and the character baseline of line 1 is:
  `line-height - cap-height - rt-height` = approximately 4.9rem. This is generous. There is no
  collision risk at this line-height.

Do not add explicit `margin-top` between wrapped lines — the line-height already controls this.
Do add `margin-bottom: 0.75rem` on `.cover-title-ruby` (slightly more than the current `.5rem`)
to give the English title below it a clean separation after the ruby annotation.

### Text alignment

`text-align: center` is inherited from `.cover`. No change needed. The `ruby-align: center` is
already set on the global `ruby {}` rule. Both apply correctly when the title is centered.

---

## 4. Macrons and Diacritics (Vertical Clipping)

Macrons (ō, ū) and vowel diacritics (á, é, etc.) extend above the x-height of the `rt` glyphs.
In a sans-serif like Segoe UI / system-ui, the macron sits above the cap-height of the `rt` glyph.

At `line-height: 2` (the current value), the space above the `rt` token inside the line box is
tight. With `line-height: 2.6` (recommended), the line box above the `rt` is large enough to
clear macrons without clipping.

**Additional safeguard:** set `overflow: visible` explicitly on `.cover-title-ruby rt` (browsers
normally default to this, but some print rendering engines clip inline elements at the line box
boundary). The developer should add this as a defensive rule.

No `padding-top` is needed on `rt` — padding on `rt` is not well-supported across print rendering
engines and should be avoided.

---

## 5. Consistency with Inner Pages

The cover ruby title intentionally shares these properties with inner-page ruby:

| Property | Inner page (`rt`) | Cover (`rt`) | Status |
|---|---|---|---|
| Font family | `'Segoe UI', system-ui, sans-serif` | Same | Identical |
| Color | `#444` | Same | Identical |
| `letter-spacing` | `0` | `0` | Identical |
| `ruby-align` | `center` | `center` | Identical |

The cover intentionally differs:

| Property | Inner page | Cover | Reason |
|---|---|---|---|
| Base font-size | 3.2rem | 3.4rem | Title prominence |
| `rt` font-size | .5em (= 1.6rem) | .42em (= 1.43rem) | Title chars are larger; ratio reduced |
| `rt` font-weight | 500 | 400 | Narrower romaji tokens |
| line-height | 2.8 | 2.6 | Title is shorter text; less leading needed |
| max-width | none | 80% | Prevent overflow on wide titles |

The visual result is: the ruby on the cover looks like the "same handwriting" as the inner pages
(same sans `rt`, same grey), just proportionally scaled for a display-size title. A reader who sees
inner-page ruby and then the cover will recognize the system immediately.

---

## 6. Fallback for Books Without a Characters Array (Old Data)

For ja and ko (and zh books pre-dating the `characters[]` field), `renderRubyTitle` returns
`showReadingLine: true` with the plain `.cover-title-native` h1 plus a separate
`.cover-title-reading` paragraph below.

The `.cover-title-native` stays at `font-size: 4rem; letter-spacing: .1em`. The
`.cover-title-reading` stays at `font-size: 1.4rem; color: #555`.

These two rules must NOT receive the `line-height: 2.6` or `max-width: 80%` that the ruby variant
gets — those properties would look odd on the flat native title. The specificity of `.cover-title-ruby`
(applied only when `renderRubyTitle` emits the ruby path) naturally keeps the two paths isolated.
No shared rule changes are needed.

The side-by-side visual: a 4rem native title followed by a 1.4rem reading line is a conventional
two-line title treatment. Next to a book that uses the ruby path (3.4rem characters with reading
above), it reads as the same "language" at different fidelity levels — the reading text is the same
grey (#555 vs. #444), the same font family. The fallback does not look broken or mismatched.

---

## 7. Accessibility and Print

### Color contrast of `rt` on white

The global `rt { color: #444 }` on a white print background: contrast ratio of #444 on #fff is
approximately 9.7:1 (WCAG AA requires 4.5:1 for normal text, 3:1 for large text). At `.42em` of
3.4rem = 1.43rem (≈19px), this qualifies as "large text" under WCAG 2.1 (18pt = 24px at 1pt =
1.33px is the threshold, but 19px is close; at print dpi it exceeds 18pt). In any case 9.7:1
passes AA and AAA at all text sizes. No change needed to the `rt` color.

### print-color-adjust

The existing rule `*, *::before, *::after { -webkit-print-color-adjust: exact; print-color-adjust: exact }`
inside `@media print` applies globally. The `rt { color: #444 }` will be respected. No additional
`print-color-adjust` declarations are needed on `.cover-title-ruby` or `rt`.

### `overflow: visible` on `rt`

As noted in Section 4, explicitly declare `overflow: visible` on `.cover-title-ruby rt` as a
defensive rule for print rendering engines.

---

## 8. ASCII Cover Sketches

### (a) Short Chinese title — 小猴子 (Xiǎo hóu zi) — one line

```
┌──────────────────────────── A4 Landscape (297 × 210mm) ────────────────────────────┐
│                                                                                      │
│                          ┌─────────────────────────┐                                │
│                          │     [Cover Image]        │  max-width 480px               │
│                          └─────────────────────────┘                                │
│                                                                                      │
│                     xiǎo    hóu      zi                                             │
│                      ──      ──      ──          ← rt (.42em, #444, sans)            │
│                      小      猴      子          ← base char (3.4rem, serif)         │
│                                                                                      │
│                          The Little Monkey                                           │  ← .cover-title-en (1.9rem)
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

One line. rt tokens are narrower than the 1em base characters. No expansion needed.
max-width: 80% is not reached. letter-spacing: 0 keeps pairs tight.
```

### (b) Longer Japanese title — 学校の大冒険 (Gakkō no daibōken) — wraps to two lines

```
┌──────────────────────────── A4 Landscape (297 × 210mm) ────────────────────────────┐
│                                                                                      │
│                     ┌─────────────────────────┐                                      │
│                     │     [Cover Image]        │                                     │
│                     └─────────────────────────┘                                      │
│                                                                                      │
│           gak·kō     no      dai·bō·ken                                             │
│            ─────     ──       ─────────       ← rt (.42em, weight 400, #444)        │
│             学校      の        大冒険         ← line 1 (3.4rem; ruby-align: center) │
│            ╌╌╌╌╌╌╌╌╌ line break ╌╌╌╌╌╌╌╌╌╌╌╌   (line-height: 2.6 = 8.84rem)        │
│                                                  ← macron ō clear of line above     │
│                                                                                      │
│              [no second line — this title fits at 80% max-width]                    │
│                                                                                      │
│                  The Big School Adventure                                            │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

Note: "gak·kō" is wider than 学 alone. ruby-align: center expands the 学 pair's inline
width symmetrically. 校 and の are unaffected. No overlap; the ruby token floats
centered above the expanded pair. If the title were longer (8+ chars), it wraps here:

           gak·kō     no                                                              
            学校       の        ← line 1                                             
            ╌╌╌╌╌╌ line break ╌╌╌╌╌╌   ← line-height 2.6 keeps rt of line 2 clear of
           dai·bō·ken                    the characters on line 1                    
             大冒険    ← line 2                                                       
```

---

## 9. Ready-to-Apply CSS Block

The following is the recommended replacement for the current `.cover-title-ruby` and
`.cover-title-ruby rt` rules inside `buildStorybookHTML`. This is a spec — the developer
applies it to `storybook_print.js`.

```css
/* Cover title with per-character ruby alignment.
   Sized slightly smaller than .cover-title-native (3.4rem vs 4rem) so the reading
   (rt) tokens have proportional room above each character. line-height and max-width
   are tuned for wrapped Japanese romaji titles on A4 landscape. */
.cover-title-ruby {
  font-size: 3.4rem;
  line-height: 2.6;
  letter-spacing: 0;
  max-width: 80%;
  margin-bottom: 0.75rem;
  /* text-align: center is inherited from .cover */
}

/* The ruby reading annotation above each character.
   Inherits font-family and color from the global rt rule
   (font-family: 'Segoe UI', system-ui, sans-serif; color: #444).
   font-weight: 400 (vs inner-page 500) trims romaji token width slightly.
   overflow: visible is a defensive guard for print engines. */
.cover-title-ruby rt {
  font-size: 0.42em;
  font-weight: 400;
  overflow: visible;
}
```

**No changes to the global `ruby {}` or `rt {}` rules** — those stay as-is. This spec
adds only the two cover-specific overrides above. The `ruby-align: center` on the global
`ruby {}` rule already applies here; do not duplicate it in `.cover-title-ruby`.

---

## 10. Design System Flags

One inconsistency to note for the record, not blocking this change:

The `renderRubyTitle` function in `storybook_print.js` (lines 147–168) only produces the ruby
path for `zh` (Chinese). Japanese and Korean titles fall back to the native-title + reading-line
path because there is no deterministic per-character splitter for those scripts without the
`characters[]` array (which only exists on page objects, not the title fields).

This spec writes rules for all three scripts, but the ja and ko paths are only reachable if the
developer extends `renderRubyTitle` to accept a pre-split `characters[]` from the story title
fields in the future. The CSS spec is forward-compatible — the rules will work correctly for
ja and ko ruby titles once the JS produces them. No CSS change is needed when that JS work is done.

Until then, the ja and ko cover always renders the fallback path (Section 6), and the new
`.cover-title-ruby` rules are only active for zh. This is the existing behavior; this spec does
not change it, only documents it.
