# Text-Only Book Mode — Design Spec

**Feature:** a second storybook mode — native text + reading (pinyin/romaji/romanization) + English
translation, with **no illustrations, no image generation step, and no per-page cost from Gemini**.
Must be a complete book: viewable in the page editor, printable, exportable as HTML, and
gallery-savable, using a text-only layout (no image column).

**Status:** Spec only. Implementation by `developer-agent` after `architect-agent` picks the
response-shape option (Section 3) and confirms the `run_decompose` signature change (flagged at
the end). Not security- or cost-sensitive in the way `book-pdf-endpoint.md` is (this mode is
strictly *cheaper* than the existing art path — one Claude call, zero image calls), so no
`cyber-architect`/`financials-agent` gate is proposed; `product-manager` may still route it through
`financials-agent` briefly to confirm the up-to-30-page allowance doesn't blow up
`claude-opus-4-8` output-token cost (a 30-page page/reading/English JSON payload is still bounded
and modest relative to image generation, but sizing that number is `financials-agent`'s call, not
mine).

**Locked scope reminder (do not revisit):**
1. Text-only books: **1–30 pages via the API.** Art books: unchanged **11/15/19** cap, Book Builder
   UI keeps using the existing Settings page-count control (11/15/19) **for both modes** — the
   1–30 range is an API-only capability in v1, not exposed as a new UI control.
2. A text-only book is a **complete book** — viewable, printable, exportable, gallery-savable with
   a text-only layout. Not just "dump text into the editor."

---

## 0. Naming decision — `include_art`

One boolean, used **identically** by name in every layer (request field, response/story field,
project-schema field, gallery-meta field, print-template check). This is a deliberate choice to
avoid yet another name-mapping table in a codebase `CLAUDE.md` already flags for registry/duplication
risk (the 4× language-registry backlog item) — one name, no translation code anywhere in the chain.

- **Rejected:** `text_only` / `generate_images` as two different names for the same concept at
  different layers (request says "generate images", story object would need to say "text_only" —
  that's already the exact kind of dual-name drift the codebase is trying to reduce elsewhere).
- **Rejected:** `text_only: bool = False` (inverted polarity from `include_art`) — keeping the
  *default-true, opt-out* polarity matches the existing `include_image_prompt: bool = True` param on
  `_decompose_tool` (same file, same pattern, opposite of introducing a new `False`-default flag next
  to it).
- **Chosen:** `include_art: bool = True` — request flag, response/story-level flag, project-schema
  field, gallery-meta field, and the print-template's mode check are all literally `include_art`.
  `True` (art) is the default everywhere, so every existing caller/consumer that doesn't know this
  field exists yet keeps working unchanged (Section 6 covers backward compatibility item by item).

---

## 1. Book Builder UI — the mode selector

### Placement

A new **segmented two-button control** directly above the existing `.decompose-btn-row` in
`#step1` (`frontend/book_builder.html`), **below** the canonical shared-inputs panel (that panel is
byte-identical across all three pages per its "keep identical" comment marker — this control does
not touch it). Reuses the existing `.presets` / `.preset` segmented-button pattern already used for
the Page Shape (aspect ratio) row in `#step3` — same visual language, no new component invented.

```html
<div class="control-group" id="bookTypeGroup">
  <label id="bookTypeLabel">Book Type</label>
  <div class="presets" id="bookTypePresets" role="group" aria-labelledby="bookTypeLabel">
    <button class="preset book-type-btn active" data-book-type="art">🎨 Illustrated</button>
    <button class="preset book-type-btn" data-book-type="text">📝 Text Only</button>
  </div>
  <p class="hint" id="bookTypeHint">
    Illustrated books get one AI image per page. Text-only books skip images —
    faster to generate, and free of image-generation cost.
  </p>
</div>
```

- Default: **Illustrated** (`include_art = true`) — unchanged default behavior for every existing
  user; nobody has to discover a new control to get today's app.
- Active-state styling: same `.preset.active` rule already used for Page Shape (`background:
  var(--mustard)`), no new color token.
- Keyboard/ARIA: native `<button>` elements in a `role="group"` — same as Page Shape, gets Tab/Enter/
  Space for free, no custom key handling needed. `aria-pressed="true"` on the active button
  (Page Shape's `.ar-btn` currently doesn't set this either — flagging as a **pre-existing minor a11y
  gap** worth fixing on both controls at once, not introducing new inconsistency by only fixing it
  here).

### Locking after decompose (see Section 6 for the "toggle mid-book" edge case)

Once `storyData` exists (a story has been generated), **both buttons become `disabled`** with a
tooltip/`title` of "Start a new book to change this." This exactly mirrors the existing Settings-page
precedent for Language and Book Length ("Applies to new books. Open books keep their own
language/length.") — no new interaction pattern, and it sidesteps a much harder problem (retrofitting
an illustrated book into text-only or vice versa mid-edit) by simply not allowing it. `clearProject()`
re-enables the control.

### What changes when Text Only is active

| Area | Illustrated (default) | Text Only |
|---|---|---|
| `#step3` ("Generate Images") | Shown after decompose, as today | **Hidden entirely** — never rendered, never inserted into the auto-flow |
| Auto-flow (`autoGenBtn` click → `runDecompose()` → `queueBtn.click()`) | Unchanged | Skips the `queueBtn.click()` step; goes straight from decompose to revealing `#step4` |
| Page card (`buildCard()` in `#step2`) | Thumbnail column + upload/regenerate controls + Image Prompt textarea | **No thumbnail column, no Image Prompt field** — card shows only native text, reading, and English (same three fields as today, minus the fourth) |
| `#step4` Export section | All five buttons as today | Same five buttons — Export HTML / Print / Save to Gallery / (zh) Practice Sheet ×2 all still apply; none of them require images to function |
| Check Readings | Unchanged | Unchanged — it never touched `image_prompt` anyway (`/recheck-readings` already omits it) |

### Copy

- Segmented buttons: **"🎨 Illustrated"** / **"📝 Text Only"** (matches the emoji-prefixed label
  convention already used everywhere else in this app: "⚡ Generate Story and Pictures", "✦ Check
  Readings", "🖌 Create Practice Sheet").
- Hint line (as shown above): states the mechanical difference (no per-page image) and the benefit
  (faster, no image cost) without over-explaining.
- No copy change needed on `autoGenBtn` itself ("⚡ Generate Story and Pictures") — flagging this as
  a **minor label mismatch** for text-only ("...and Pictures" when there will be none). Recommend
  swapping the button label text to **"⚡ Generate Story"** when Text Only is selected (toggle the
  `autoGenLabel.textContent` default string the same way `setDecomposeLoading()` already swaps it
  between "Writing…" and the idle label) rather than leaving a slightly misleading label — small,
  contained, developer-agent can wire it alongside the existing label-swap logic.

---

## 2. The API option — `DecomposeRequest.include_art`

### Request

```python
class DecomposeRequest(BaseModel):
    concept: Optional[str] = ""
    style_suffix: Optional[str] = ""
    character: Optional[str] = ""
    language: Optional[str] = "zh"
    page_count: Optional[int] = 11
    include_art: Optional[bool] = True        # NEW
    anthropic_key: Optional[str] = None
```

### Page-count validation — branches on `include_art`

| `include_art` | Behavior | Rationale |
|---|---|---|
| `True` (default/art) | **Unchanged.** Silent clamp to `{11, 15, 19}` (anything else → 11), exactly today's `run_decompose` behavior. No existing caller's behavior changes. | Locked scope item 1 — art books keep their existing cap and existing (permissive/clamping) validation style. |
| `False` (text-only) | **Strict validation:** `1 <= page_count <= 30`, else `400 Bad Request` with a message naming the valid range. **No silent clamping.** | The task explicitly calls for "validate the range; reject out-of-range" for text-only — a deliberate style change from the art path's silent clamp. Rationale for the divergence: the text-only range is 30× wider (1–30 vs. a 3-value enum), so a silent clamp could turn a caller's typo (`page_count: 300`) into a surprising 30-page book instead of an obvious error. Flagging this explicitly since it means `/decompose` will have two different validation styles for the same field depending on `include_art` — an intentional, scoped inconsistency, not an oversight. |

### Where validation happens

Two layers, mirroring the existing `/book-pdf` pattern (route validates strictly with `400`;
`run_decompose`'s internal clamp is a defensive fallback, not the primary gate):

1. **Route (`/decompose`)** — explicit check before calling `run_decompose`:
   ```python
   if req.include_art:
       pass  # existing behavior: run_decompose clamps silently, as today
   else:
       if not (1 <= (req.page_count or 0) <= 30):
           raise HTTPException(status_code=400, detail="page_count must be between 1 and 30 for text-only books.")
   ```
2. **`run_decompose`** — gains an `include_art: bool = True` parameter, threaded to
   `_decompose_tool(..., include_image_prompt=include_art)`. Its internal page_count clamp becomes
   conditional:
   ```python
   if include_art:
       page_count = page_count if page_count in (11, 15, 19) else 11   # unchanged
   else:
       page_count = page_count if page_count and 1 <= page_count <= 30 else 11   # defensive fallback only — route already rejected bad values
   ```
   This keeps `run_decompose` safe to call directly (e.g. from tests, or from `/book-pdf` if it
   ever adopts text-only — Section 6) even if a caller bypasses the route-level check.

### Request/response examples

**Request — text-only, 20 pages:**
```json
POST /decompose
{
  "character": "a brave little monkey king in golden armor",
  "language": "zh",
  "page_count": 20,
  "include_art": false
}
```

**Response (200) — no `image_prompt` anywhere, `include_art: false` on the story:**
```json
{
  "book_title_zh": "小猴王的旅程",
  "book_title_pinyin": "xiǎo hóu wáng de lǚ chéng",
  "book_title_en": "The Little Monkey King's Journey",
  "book_title_characters": [{"c": "小", "p": "xiǎo"}, ...],
  "language": "zh",
  "include_art": false,
  "pages": [
    {
      "page": 1,
      "zh": "小猴王住在花果山上。",
      "pinyin": "xiǎo hóu wáng zhù zài huā guǒ shān shàng。",
      "en": "The little monkey king lived on Flower Fruit Mountain.",
      "characters": [{"c": "小", "p": "xiǎo"}, ...]
    }
  ]
}
```

**Request — art (unchanged):**
```json
POST /decompose
{ "character": "...", "language": "zh", "page_count": 15 }
```
`include_art` defaults to `true`; response shape and validation are byte-for-byte what they are
today, **plus** a new `"include_art": true` field (Section 3 covers whether this is additive-only
or requires a schema change).

### Fields returned per page/title — text-only

Exactly `PageData` minus `image_prompt`: `page`, native field (`zh`/`ja`/`ko`), reading field
(`pinyin`/`romaji`/`romanization`), `en`, `characters`. Title fields unchanged: `book_title_{native}`,
`book_title_{reading}`, `book_title_en`, `book_title_characters`. This is exactly what
`_decompose_tool(..., include_image_prompt=False)` already produces today for `/recheck-readings` —
**no new schema work**, this mode reuses that exact tool-schema branch that already exists in the
codebase, just invoked from a different route with a different page-count range.

---

## 3. Response shape — the decision architect-agent must make

Two options, as instructed. Both are real, working approaches already present elsewhere in this
codebase — this is not a greenfield decision.

### Option A — `PageData.image_prompt` becomes `Optional[str] = None`; keep the single `response_model=DecomposeResponse`

```python
class PageData(BaseModel):
    page: int
    en: str
    image_prompt: Optional[str] = None     # was: str (required)
    include_art: Optional[bool] = None     # or hang this off DecomposeResponse only — see below
    ...
```
- **Pro:** minimal code change — `/decompose` keeps its `response_model=DecomposeResponse`
  decorator unchanged, FastAPI keeps validating/serializing every response through Pydantic exactly
  as it does today. Zero new response-handling code path.
- **Con — the literal requirement isn't met:** Pydantic's default JSON serialization emits
  `"image_prompt": null`, not an **absent key**. The task/acceptance criteria say "image_prompt must
  be absent for text-only" — Option A gives `null`, not absence, unless the route sets
  `response_model_exclude_none=True`. That flag can't be applied selectively per-request at the
  route-decorator level, and applying it unconditionally would also strip every other legitimately-
  null optional field the response already emits today (e.g. `book_title_ja`/`book_title_romaji` are
  `null` on a `zh` book right now, and existing consumers may depend on that key being present-but-
  null rather than missing) — so this isn't a free knob to turn on for this one field.
- **Con:** loosens `PageData`'s schema permanently for every consumer, including the art path, even
  though the art path's tool-schema (`include_image_prompt=True`) still forces Claude to always
  supply it — the *practical* guarantee for art books is unchanged, but the *declared* schema is now
  weaker than it needs to be for that path.

### Option B — plain dict for text-only, `response_model`-validated for art (mirrors `/recheck-readings`)

`/recheck-readings` already solves exactly this problem today (no `response_model`, returns a plain
dict, because `image_prompt` is genuinely absent from its response). The direct analog for
`/decompose` requires one more step than `/recheck-readings` needed, because `/decompose` must
support **both** shapes from **one** route depending on `include_art`, whereas `/recheck-readings`
only ever has one shape. FastAPI supports this cleanly by **returning a `Response` object directly**
when bypassing is needed — per FastAPI's own documented behavior, returning a `Response`
(e.g. `JSONResponse(content=data)`) from a path function **skips `response_model` processing
entirely**, while returning a plain dict (as today) still goes through the declared
`response_model=DecomposeResponse` and gets validated/filtered as normal:

```python
@app.post("/decompose", response_model=DecomposeResponse)
def decompose(req: DecomposeRequest):
    ...
    data = run_decompose(..., include_art=req.include_art, ...)
    if not req.include_art:
        return JSONResponse(content=data)   # bypasses response_model — image_prompt key is genuinely absent
    return data                              # unchanged path — validated against DecomposeResponse as today
```
- **Pro:** literally satisfies "image_prompt must be absent" — the key does not exist in the
  returned JSON for text-only, no serialization workaround needed.
- **Pro:** the art-mode path is **completely untouched** — same decorator, same validation, same
  guarantee it has today. No weakening of `PageData` for the path that actually needs the guarantee.
- **Con:** the text-only path loses `response_model`'s automatic request/response schema
  documentation in FastAPI's OpenAPI output (it'll show `DecomposeResponse` as the documented shape
  even though text-only responses look different) — same **already-accepted** tradeoff
  `/recheck-readings` lives with today (it has no `response_model` and isn't fully self-documenting
  either). Not a new problem, an existing one this mode would share.
- **Con:** the text-only branch also loses automatic **validation** that `run_decompose`'s returned
  dict actually matches the intended shape before it goes out — a schema-shape bug in that branch
  would surface as a malformed JSON response to the client instead of a 500 from Pydantic. Low risk
  given `run_decompose` already builds this dict via the same forced-tool-use path used for
  `/recheck-readings` today (proven), but worth naming as the real cost of skipping validation.

### Recommendation

**Option B**, for the same reason `/recheck-readings` already chose it: the literal requirement is
"the key is absent," and only bypassing `response_model` for that one branch achieves that without
side effects on unrelated fields or on the art path's existing guarantee. The `JSONResponse`
bypass pattern shown above is a small, contained addition — one `if` branch in one route — not a
new abstraction. **Final call is architect-agent's**, per the task instructions; this section lays
out both so that call can be made with the actual tradeoffs in view rather than picked blind.

Whichever option wins, `DecomposeResponse` (or the raw dict for Option B) gains one new field:
`include_art: bool` — the source of truth threaded to the frontend's story object, project schema,
gallery metadata, and print template (Sections 1, 4, 5).

---

## 4. Text-only print/export layout — `storybook_print.js`

### Trigger

No new function parameter. `buildStorybookHTML(story, pages, imageB64, printMode)` reads
`story.include_art` directly (it already receives the full `story` object) and derives:
```js
const illustrated = story.include_art !== false;   // undefined (old books) or true → illustrated
```
`!== false` (not `=== true`) is the deliberate backward-compat rule — every book saved before this
feature shipped has no `include_art` key at all, and must render exactly as it does today. Both
call sites (`openPrintWindow`, `downloadStorybookHTML` in `book_builder.js`; the equivalent call in
`gallery.js`) need **zero changes** — they already pass `project.story` straight through.

### Layout choice — one printed page per story page (not two-up)

**Recommended:** each story page becomes **one full-width printed page** (a `.page-spread` variant
with a single column instead of the current image-left/text-right grid), not two story-pages-per-
printed-page. Reasoning:
- Reuses the existing `.page-spread` / `page-break-after: always` mechanism as-is — only the CSS
  `grid-template-columns` and the removal of `.spread-left` differ, no new pairing/pagination logic.
- Two-up would need to (a) decide how to pair odd page counts (text-only allows up to 30, so a
  31st/odd page always needs special-casing), and (b) fit two pages' worth of ruby text + English
  onto one sheet without harming legibility — the existing `.text-ruby` sizing was already tuned
  assuming a half-width column competing with an image, not a full page of unaided text.
- **Tradeoff being flagged, not hidden:** a full 30-page text-only book prints as 30 physical pages
  (31 with cover) instead of ~16. If print-run length becomes a real complaint, two-up is a
  reasonable v2 optimization — noting it here so it isn't silently ruled out, just deferred for v1
  simplicity per the "recommend, but leave room to override" instruction.

### Markup / CSS delta

```html
<!-- Illustrated (unchanged) -->
<div class="page-spread">
  <div class="spread-left">...</div>
  <div class="spread-right">...</div>
</div>

<!-- Text-only -->
<div class="page-spread page-spread--text-only">
  <div class="spread-right">
    <div class="page-num">Page ${pg.page}</div>
    ${renderRubyText(pg, langCode)}   <!-- REUSED, unchanged -->
    <p class="text-en">${escHtml(pg.en)}</p>
  </div>
</div>
```

```css
.page-spread--text-only {
  grid-template-columns: 1fr;              /* single column, no .spread-left */
}
.page-spread--text-only .spread-right {
  align-items: center; text-align: center; /* full-width text page reads better centered */
  padding: 3.5rem 4rem;
}
.page-spread--text-only .text-ruby { font-size: 4.5rem; }  /* larger — no image competing for space */
.page-spread--text-only .text-en   { font-size: 2.3rem; border-top: none; }
```
No changes to `renderRubyText()` / `renderRubyTitle()` — both are reused exactly as-is, per the
explicit "must reuse the existing ruby rendering, not reinvent it" instruction. The recent
ruby-spacing fix (`.text-ruby ruby { margin: 0 .16em; }`) applies automatically since it's the same
class.

### Cover

```js
const coverImg = illustrated && imageB64[1]
  ? `<img src="${imageB64[1]}" alt="cover" class="cover-img">`
  : '';
```
For text-only, `imageB64[1]` will already be empty (no `generated_images` exist), so `coverImg`
naturally resolves to `''` even without the `illustrated` check — but the explicit check makes the
intent legible in the code and is a one-line defensive guard against a hand-edited/corrupted project
that has stray `generated_images` alongside `include_art: false` (Section 6, "mixed state"). No other
cover markup changes — title (via `renderRubyTitle`, already reused), English title line, and the
`.cover` container are identical between modes.

---

## 5. Book Builder flow + persistence

### Decompose → edit → (skip image gen) → print/export/gallery

1. `runDecompose()` reads the new `#bookTypePresets` selection into a module-level `includeArt`
   state var (mirrors the existing `geminiAR` pattern), sends `include_art: includeArt` in the POST
   body alongside the existing `page_count` (still sourced from `monkeyking_bb_pages`, **unchanged**
   for both modes per locked scope item 1).
2. On success, `storyData.include_art` comes back from the server (Section 3) — this is the single
   source of truth from here on, not the local `includeArt` var (which only exists to build the
   request; once a story exists, always read `storyData.include_art`).
3. `renderPages()` / `buildCard()` branch on `storyData.include_art`:
   - `true`/absent → today's card markup (thumb-wrap + Image Prompt field), unchanged.
   - `false` → card markup omits the `.card-thumb-wrap` block and the Image Prompt `.card-field`
     entirely — three fields only (native / reading / English), same as today minus the fourth.
4. `#step3` visibility: shown/hidden based on `storyData.include_art` at the same point `step2`/
   `step4` visibility is already toggled in `runDecompose()`/`restoreProject()`.
5. The `autoGenBtn` click handler's auto-flow (`runDecompose()` → `queueBtn.click()`) skips the
   `queueBtn.click()` call when `storyData.include_art === false` — goes straight to scrolling down
   to `#step4`, which is already visible-and-ready (no images to wait for).
6. `readCard()` omits the `image_prompt` key from its returned object when
   `storyData.include_art === false` (today it unconditionally includes it, reading an empty string
   from a textarea that won't exist for text-only cards — harmless today, but cleaner and more
   explicit to omit the key entirely rather than emit a phantom empty field).

### Project schema

No structural change to the `version: 1` schema — `include_art` rides along for free since
`currentProject()`/`saveState()` already spread `...storyData` into `story:`:
```js
story: { ...storyData, language: currentLang, pages: editedPages }   // include_art already present via spread
generated_images: {}   // naturally empty for text-only — no new code needed
```

### Restore / reopen

`restoreProject()` (loading from Gallery or `localStorage`) reads `project.story.include_art`
(default `true` if absent, for pre-feature saves) and re-applies the same branching as step 3 above
— render text-only cards, hide `#step3`, lock the `#bookTypePresets` control to reflect the loaded
book's mode (consistent with the language/page-count "open books keep their own settings" precedent
already established for those two fields).

### zh Practice Sheet

**No changes required.** Both `practiceSheetBtn` (cloud/Claude) and `practiceLocalBtn` (local/
ReportLab) already operate purely on `storyData.pages[].zh` text — neither reads `image_prompt` or
any image data. Gating stays exactly `code === 'zh'` (language-based, not mode-based) as it is today.

### Gallery card display

`_read_gallery_meta()` (`main.py`) gains one field, defaulting `True` for backward compatibility:
```python
"include_art": story.get("include_art", True),
```
`buildBookCard()` (`gallery.js`) already renders `book-cover-placeholder` (📖) whenever
`book.cover_image` is falsy — which is already true for every text-only book (no `generated_images`
→ no page-1 image). That fallback **already works with zero changes**. Recommended (small) addition
for clarity, since an art book that simply hasn't generated images yet would render an identical
placeholder otherwise, making the two states visually indistinguishable:
```js
const isTextOnly = book.include_art === false;
const coverHTML = coverSrc
  ? `<img src="${coverSrc}" alt="cover" loading="lazy">`
  : isTextOnly
    ? `<div class="book-cover-placeholder book-cover-placeholder--text">📝</div>`
    : `<div class="book-cover-placeholder">📖</div>`;
```
A distinct glyph (📝 vs 📖) in the same placeholder slot — no new layout, no new CSS class beyond an
optional modifier for a background tint if desired. Kept intentionally minimal per the task's "keep
it minimal" framing.

---

## 6. Interactions & edge cases

| Case | Behavior |
|---|---|
| Existing art books (saved before this feature) | Unaffected. Every `include_art` check in this spec uses `!== false` / `.get(..., True)` defaults, so an absent key is always treated as illustrated. |
| Settings page-count UI | Unchanged — stays the 11/15/19 `#settingsPages` select for both modes (locked scope item 1). No new Settings-page control for the 1–30 API range in v1. |
| User toggles Text Only **after** a story already exists (possibly with some images already generated) | **Not reachable** — Section 1 locks (`disabled`) the `#bookTypePresets` control the moment `storyData` exists, mirroring the Language/Book-Length "applies to new books only" precedent. The user must start a new book (`clearProject()`, which already resets `storyData` and re-enables the control) to change modes. This is the recommended answer to the task's open question — a warn-and-clear flow was considered and rejected as unnecessary complexity when a simple lock, consistent with two other fields' existing UX, achieves the same safety with no new interaction pattern. |
| Mixed state (`include_art: false` with a non-empty `generated_images` map) | Only reachable via manual/hand-edited project JSON (not producible through the UI, given the lock above) — out of scope to actively support. Recommended defensive behavior if encountered: the print template and Book Builder card renderer both key **only** off `include_art`, ignoring any stray `generated_images` entries (Section 4's `illustrated && imageB64[1]` guard is exactly this). No crash, no special-cased warning — just deterministic "text-only wins." |
| `/book-pdf` endpoint | **Out of scope for v1.** Recommend deferring: `book_pdf.py`'s rendering path (still an open question per `design-specs/book-pdf-endpoint.md` Section 3, not yet implemented) is built entirely around the illustrated image-left/text-right spread; a text-only variant needs its own render path there regardless of which engine is chosen, and `BookPDFRequest` doesn't have an `include_art` field. The `run_decompose(..., include_art: bool = True)` signature change in this spec **is** exercised by `/book-pdf`'s `mode="prompt"` call site (it calls `run_decompose` directly) — confirming this default keeps `/book-pdf` byte-for-byte unchanged today is exactly the "flag for architect" item at the end of this doc, since it's a real touch point even though the *feature* is deferred there. |

---

## 7. Acceptance criteria

- [ ] `POST /decompose` accepts `include_art: bool = True`; omitting it preserves today's exact
      request/response behavior for every existing caller.
- [ ] `include_art: false` + `page_count` outside `1..30` → `400` with a message naming the valid
      range; `page_count` inside `1..30` succeeds for any value in that range (not just 11/15/19).
- [ ] `include_art: true` (or omitted) → page_count validation/clamping is byte-for-byte unchanged
      from today (silent clamp to 11/15/19).
- [ ] Text-only responses contain no `image_prompt` key anywhere in the payload (per whichever of
      Section 3's options architect-agent picks — Option A must additionally satisfy this via
      whatever mechanism is chosen, not just `null`, if that option is picked instead of B).
- [ ] Text-only responses (and art responses) carry `include_art` at the top level, matching the
      request's resolved value.
- [ ] Book Builder: the Book Type control defaults to Illustrated, is a two-button segmented group
      styled like the existing Page Shape presets, and becomes disabled once a story is generated.
- [ ] Text-only decompose in Book Builder: `#step3` never appears; the auto-flow goes straight from
      decompose to a populated `#step4`; page cards show only native/reading/English fields.
- [ ] Text-only book is printable (`🖨 Print / Save as PDF`) and exportable
      (`📖 Export as HTML`) using the new full-width, no-image-column layout; ruby rendering is
      pixel-identical in technique to the illustrated path (same `renderRubyText`/`renderRubyTitle`
      functions, no duplicated ruby logic).
- [ ] Text-only book saves to Gallery and lists correctly, with a placeholder cover distinguishable
      from an art book with no images yet generated.
- [ ] zh Practice Sheet (both cloud and local buttons) works unmodified on a text-only zh book.
- [ ] Reopening a saved text-only book (from Gallery or `localStorage`) restores the correct mode:
      no image UI, `#step3` hidden, Book Type control locked to Text Only.
- [ ] Every pre-existing art book (real or synthetic, lacking `include_art`) renders, prints,
      exports, and displays in Gallery exactly as it does before this change ships.
- [ ] `/book-pdf` behavior and its existing test/usage paths are unaffected by the `run_decompose`
      signature change (new parameter defaults to `True`, matching current behavior exactly).

---

## Flags for architect-agent

1. **Response-shape decision (Section 3) is the one open call in this spec.** Recommending Option B
   (bypass `response_model` via `JSONResponse` for the `include_art=False` branch only, mirroring
   `/recheck-readings`'s existing no-`response_model` precedent) because it's the only option that
   makes `image_prompt` genuinely *absent* rather than *null*, without weakening `PageData`'s schema
   for the art path that still needs the guarantee. Option A (Optional field, single
   `response_model`) is simpler to write but only achieves "null", not "absent," without a
   `response_model_exclude_none` side effect that would also strip other legitimately-present-null
   fields (`book_title_ja`/etc. on non-Japanese books) — flagging that side effect explicitly since
   it's easy to reach for `exclude_none` without noticing it's global, not per-field.
2. **`run_decompose(..., include_art: bool = True)` signature change is shared by two call sites** —
   the `/decompose` route (this feature) and `_run_book_pdf_job`'s `mode="prompt"` branch
   (`main.py`, `book-pdf-endpoint.md`'s pipeline). Confirming the default (`True`) preserves
   `/book-pdf`'s current behavior with **zero changes to `BookPDFRequest` or the book-pdf worker** —
   worth a explicit look since it's exactly the kind of shared-function edit `CLAUDE.md` calls out
   `run_decompose` for ("Used by BOTH the `/decompose` route AND the book-pdf worker — changing it
   affects both").
3. **Text-only support for `/book-pdf` is explicitly deferred (Section 6)** — not because it's hard,
   but because `book_pdf.py`'s renderer doesn't exist yet (open question in
   `design-specs/book-pdf-endpoint.md` Section 3) and building a text-only variant of an
   as-yet-unbuilt renderer isn't well-scoped right now. Recommend picking this back up once
   `book-pdf-endpoint.md`'s Section 3 rendering-engine decision lands.
