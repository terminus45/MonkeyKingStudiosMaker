# keep in sync with frontend/storybook_print.js buildStorybookHTML
"""Server-side storybook PDF renderer for the /book-pdf endpoint.

Three pieces, kept out of main.py (like practice_sheet.py / practice_sheet_local.py):

  build_storybook_html(story, image_data_uris) -- a faithful Python port of
      frontend/storybook_print.js's buildStorybookHTML(): same cover +
      page-spread layout, same <ruby> markup, same CSS (A4 landscape,
      page-break rules). The HTML is fully self-contained -- every text field
      is HTML-escaped and every image is an inlined base64 data: URI (the
      caller supplies `image_data_uris`, a {page_number: data_uri} map) -- so
      it needs no live server round-trips to render.

  render_pdf(html_str) -- headless Chromium (Playwright) turns that HTML into
      a PDF, locked down so the rendered document cannot make outbound
      network requests or execute page JS: JS is disabled at the browser
      context level, every request is aborted (data: URIs are not routed, so
      inlined images still render), and the page is loaded via
      set_content(), never goto()/navigate().

  merge_pdfs(book_bytes, practice_bytes) -- appends a (portrait, US-Letter)
      Chinese practice-sheet PDF onto the (landscape, A4) book PDF via
      pymupdf. PDF pages carry their own MediaBox, so mixed sizes/orientations
      concatenate fine without rescaling -- see
      design-specs/book-pdf-endpoint.md Section 2 for the design rationale.

The zh title/page ruby fallback (for stories that predate the `characters[]`
field) reuses practice_sheet_local's already-ported pinyin-syllable splitter
(`_derive_characters`) rather than re-porting frontend/storybook_print.js's
`_splitPinyinSyllables`/`_buildCharacters` a second time.
"""
from __future__ import annotations

from typing import Optional

import languages
import practice_sheet_local as practice_sheet_local_mod

# ── Font stack broadening ────────────────────────────────────────────────────
# languages.py's font_stack (e.g. "'Noto Serif SC', 'SimSun', serif") is tuned
# for a BROWSER's font stack (system fonts / whatever's cached from a prior
# page load). A server-side headless-Chromium render has no browser to lean
# on, so we append OS-default CJK families before the trailing generic
# (serif) family -- widening the odds that *some* installed font on the
# render host actually has the glyphs, rather than silently falling back to
# tofu. See design-specs/book-pdf-endpoint.md Section 2 ("Fonts -- a real gap
# to flag") and CLAUDE.md's book-pdf section for the deploy-host font note.
_FONT_STACK_EXTRAS = {
    "zh": ["'PingFang SC'", "'Noto Sans CJK SC'", "'Noto Serif CJK SC'"],
    "ja": ["'Hiragino Sans'", "'Noto Sans CJK JP'"],
    "ko": ["'Apple SD Gothic Neo'", "'Noto Sans CJK KR'"],
}
_GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy"}


def _broadened_font_stack(lang: dict) -> str:
    """Insert this language's OS-default CJK fallbacks just before the
    trailing generic family (usually `serif`) in languages.py's font_stack."""
    base = lang["font_stack"]
    extras = _FONT_STACK_EXTRAS.get(lang["code"], [])
    if not extras:
        return base
    parts = [p.strip() for p in base.split(",")]
    if parts and parts[-1] in _GENERIC_FAMILIES:
        return ", ".join(parts[:-1] + extras + [parts[-1]])
    return ", ".join(parts + extras)


# ── HTML escaping ────────────────────────────────────────────────────────────
# Mirrors frontend/storybook_print.js's escHtml exactly (does NOT escape
# apostrophes -- kept identical on purpose).
def esc_html(value) -> str:
    if value is None:
        value = ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── Ruby text renderer (mirrors renderRubyText in storybook_print.js) ───────
def render_ruby_text(pg: dict, lang_code: str) -> str:
    lang = languages.get(lang_code)
    native_f = lang["native_field"]
    reading_f = lang["reading_field"]
    native_str = pg.get(native_f) or ""
    reading_str = pg.get(reading_f) or ""

    chars = pg.get("characters")
    if not chars:
        # Fallback: only zh has a deterministic syllable splitter. ja/ko
        # without a characters array fall back to native text alone (no ruby).
        if lang_code == "zh" or not lang_code:
            chars = practice_sheet_local_mod._derive_characters(native_str, reading_str)
        else:
            return f'<p class="text-ruby">{esc_html(native_str)}</p>'

    parts = []
    for ch in chars:
        c = ch.get("c", "") if isinstance(ch, dict) else getattr(ch, "c", "")
        p = ch.get("p", "") if isinstance(ch, dict) else getattr(ch, "p", "")
        if p:
            parts.append(f"<ruby>{esc_html(c)}<rt>{esc_html(p)}</rt></ruby>")
        else:
            parts.append(esc_html(c))
    return f'<p class="text-ruby">{"".join(parts)}</p>'


def _ruby_spans(items) -> str:
    parts = []
    for ch in items:
        c = ch.get("c", "") if isinstance(ch, dict) else getattr(ch, "c", "")
        p = ch.get("p", "") if isinstance(ch, dict) else getattr(ch, "p", "")
        if p:
            parts.append(f"<ruby>{esc_html(c)}<rt>{esc_html(p)}</rt></ruby>")
        else:
            parts.append(esc_html(c))
    return "".join(parts)


# ── Cover title renderer (mirrors renderRubyTitle in storybook_print.js) ────
def render_ruby_title(story: dict, lang_code: str) -> tuple[str, bool]:
    """Returns (title_html, show_reading_line)."""
    lang = languages.get(lang_code)
    native_str = story.get(lang["title_native_field"]) or ""
    reading_str = story.get(lang["title_reading_field"]) or ""
    font_stack = _broadened_font_stack(lang)

    # Branch 1 (language-neutral): pre-split book_title_characters when present.
    btc = story.get("book_title_characters")
    if btc:
        ruby = _ruby_spans(btc)
        return (
            f'<h1 class="cover-title-native cover-title-ruby" '
            f'style="font-family:{font_stack}">{ruby}</h1>',
            False,
        )

    # Branch 2: zh fallback -- derive characters via the deterministic
    # syllable splitter (reused from practice_sheet_local, not re-ported).
    if (lang_code == "zh" or not lang_code) and native_str and reading_str:
        chars = practice_sheet_local_mod._derive_characters(native_str, reading_str)
        ruby = _ruby_spans(chars)
        return (
            f'<h1 class="cover-title-native cover-title-ruby" '
            f'style="font-family:{font_stack}">{ruby}</h1>',
            False,
        )

    # Branch 3: ja/ko fallback -- native title + separate reading line below.
    return (f'<h1 class="cover-title-native">{esc_html(native_str)}</h1>', True)


# ── Full HTML document (mirrors buildStorybookHTML in storybook_print.js) ───
# Built with sentinel tokens + str.replace rather than an f-string, since the
# CSS block contains far too many literal `{`/`}` to safely double-escape.
_TEMPLATE = """<!DOCTYPE html>
<html lang="__HTML_LANG__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__BOOK_TITLE_EN__</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #fff; color: #111; }
  .book { max-width: 900px; margin: 0 auto; }

  .cover {
    height: 100vh;
    overflow: hidden;          /* exactly one page -- never spill a sliver onto a 2nd printed page */
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: #fff;
    padding: 2.5rem 2rem; text-align: center;
    border-bottom: 2px solid #000;
  }
  .cover-img { max-width: 480px; max-height: 50vh; width: auto; height: auto;
    object-fit: contain; border-radius: 4px; margin-bottom: 1.5rem; }
  .cover-title-native { font-size: 4rem; color: #000; letter-spacing: .1em;
    font-family: __FONT_STACK__; }
  .cover-title-ruby {
    font-size: 3.4rem;
    line-height: 2.6;
    letter-spacing: 0;
    max-width: 80%;
    margin-bottom: 0.75rem;
  }
  .cover-title-ruby rt { font-size: 0.42em; font-weight: 400; overflow: visible; }
  .cover-title-reading { font-size: 1.4rem; color: #555; margin: .5rem 0; }
  .cover-title-en { font-size: 1.9rem; color: #000; font-weight: 700; margin-top: .25rem; }

  .page-spread {
    display: grid; grid-template-columns: 1fr 1fr;
    min-height: 50vw; max-height: 100vh; background: #fff;
    border-bottom: 1px solid #ccc;
  }
  .spread-left { display: flex; align-items: center; justify-content: center;
    background: #1a1a1a; border-right: 1px solid #ccc; overflow: hidden; }
  .page-img { width: 100%; height: 100%; object-fit: contain; display: block; }
  .page-img-placeholder { width: 100%; height: 100%; min-height: 320px;
    display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(
      45deg, #f0f0f0 0px, #f0f0f0 10px, #e8e8e8 10px, #e8e8e8 20px);
    color: #bbb; font-size: 1rem; border: 2px dashed #ccc; }
  .spread-right { padding: 2.5rem 2.25rem;
    display: flex; flex-direction: column; justify-content: center; gap: 1.5rem; }
  .page-num { font-size: .8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; color: #999; }
  .text-ruby { font-size: 3.2rem; line-height: 2.8;
    font-family: __FONT_STACK__; color: #000; }
  ruby { ruby-align: center; }
  rt { font-size: .5em; color: #444; font-family: 'Segoe UI', system-ui, sans-serif;
    font-weight: 500; letter-spacing: 0; }
  .text-en { font-size: 1.9rem; line-height: 1.55; color: #111;
    border-top: 1px solid #e0e0e0; padding-top: 1.25rem; }

  @media (max-width: 600px) {
    .page-spread { grid-template-columns: 1fr; }
    .cover-title-native { font-size: 2.5rem; }
    .cover-title-ruby { font-size: 2.2rem; }
    .text-ruby { font-size: 2.4rem; }
    .text-en { font-size: 1.45rem; }
  }
  @page { size: A4 landscape; margin: 0; }
  @media print {
    *, *::before, *::after { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { background: #fff; }
    .book { max-width: 100%; }
    .cover, .page-spread {
      page-break-after: always; break-after: page;
      page-break-inside: avoid; break-inside: avoid;
    }
  }
</style>
__PRINT_SCRIPT__
</head>
<body>
<div class="book">
  <div class="cover">
    __COVER_IMG__
    __TITLE_HTML__
    __READING_LINE__
    <p class="cover-title-en">__COVER_TITLE_EN__</p>
  </div>
  __PAGE_SPREAD__
</div>
</body>
</html>"""


def build_storybook_html(story: dict, image_data_uris: dict, *, print_mode: bool = False) -> str:
    """Faithful port of buildStorybookHTML(story, pages, imageB64, printMode).

    image_data_uris: {page_number(int): "data:image/png;base64,..."} -- page 1's
    entry doubles as the cover image, exactly like storybook_print.js's imageB64[1].
    print_mode=False by default (no window.print() trigger script -- that's a
    browser-only convenience, irrelevant to a server-rendered PDF).
    """
    lang_code = story.get("language") or languages.DEFAULT_LANGUAGE
    lang = languages.get(lang_code)
    title_reading = story.get(lang["title_reading_field"]) or ""
    title_html, show_reading_line = render_ruby_title(story, lang_code)
    font_stack = _broadened_font_stack(lang)

    cover_uri = image_data_uris.get(1)
    cover_img = f'<img src="{cover_uri}" alt="cover" class="cover-img">' if cover_uri else ""

    pages = story.get("pages") or []
    spreads = []
    for pg in pages:
        pnum = pg.get("page")
        uri = image_data_uris.get(pnum)
        img = (
            f'<img src="{uri}" alt="Page {pnum}" class="page-img">'
            if uri else '<div class="page-img-placeholder">No image</div>'
        )
        spreads.append(
            f'\n    <div class="page-spread">\n'
            f'      <div class="spread-left">{img}</div>\n'
            f'      <div class="spread-right">\n'
            f'        <div class="page-num">Page {pnum}</div>\n'
            f'        {render_ruby_text(pg, lang_code)}\n'
            f'        <p class="text-en">{esc_html(pg.get("en", ""))}</p>\n'
            f'      </div>\n'
            f'    </div>'
        )
    page_spread_html = "\n".join(spreads)

    print_script = ""
    if print_mode:
        print_script = (
            "<script>\n"
            "  window.addEventListener('load', () => { setTimeout(() => window.print(), 400); });\n"
            "</script>"
        )

    reading_line_html = (
        f'<p class="cover-title-reading">{esc_html(title_reading)}</p>' if show_reading_line else ""
    )

    html = _TEMPLATE
    html = html.replace("__HTML_LANG__", esc_html(lang["html_lang"]))
    html = html.replace("__BOOK_TITLE_EN__", esc_html(story.get("book_title_en", "")))
    html = html.replace("__FONT_STACK__", font_stack)
    html = html.replace("__PRINT_SCRIPT__", print_script)
    html = html.replace("__COVER_IMG__", cover_img)
    html = html.replace("__TITLE_HTML__", title_html)
    html = html.replace("__READING_LINE__", reading_line_html)
    html = html.replace("__COVER_TITLE_EN__", esc_html(story.get("book_title_en", "")))
    html = html.replace("__PAGE_SPREAD__", page_spread_html)
    return html


# ── PDF rendering (headless Chromium via Playwright) ─────────────────────────

_MAX_PDF_BYTES = 100 * 1024 * 1024  # ~100MB safety guard
_RENDER_TIMEOUT_MS = 30_000  # ~30s per Playwright action, per the design spec


def render_pdf(html_str: str) -> bytes:
    """Render a self-contained HTML document (as built by build_storybook_html)
    to PDF bytes via headless Chromium.

    Security lockdown (closes cyber-architect's F2 finding -- the rendered
    document must not be able to reach the network or run arbitrary JS):
      - Playwright is imported lazily, so the app still starts if the package
        (or the Chromium binary) isn't installed.
      - java_script_enabled=False on the browser context.
      - EVERY network request is aborted via page.route -- data: URIs are not
        routed through page.route, so the inlined base64 images still render.
      - page.set_content(html_str, wait_until="load") -- never goto()/navigate,
        so there is no URL for the page to be tricked into visiting.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright/Chromium not available — run: playwright install chromium"
        ) from e

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                raise RuntimeError(
                    "Playwright/Chromium not available — run: playwright install chromium"
                ) from e
            try:
                context = browser.new_context(java_script_enabled=False)
                page = context.new_page()
                page.route("**/*", lambda route: route.abort())
                page.set_content(html_str, wait_until="load", timeout=_RENDER_TIMEOUT_MS)
                pdf_bytes = page.pdf(
                    format="A4",
                    landscape=True,
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            finally:
                browser.close()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"PDF rendering failed: {e}") from e

    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise RuntimeError(
            f"Rendered PDF ({len(pdf_bytes)} bytes) exceeds the "
            f"{_MAX_PDF_BYTES} byte safety limit."
        )
    return pdf_bytes


# ── Practice-sheet merge (pymupdf) ────────────────────────────────────────────

def merge_pdfs(book_bytes: bytes, practice_bytes: bytes) -> bytes:
    """Append practice_bytes (a portrait US-Letter PDF) onto book_bytes (a
    landscape A4 PDF). PDF pages carry their own MediaBox, so pymupdf
    concatenates the two documents without rescaling -- the resulting mixed
    page sizes/orientation is an accepted tradeoff, not a bug (see
    design-specs/book-pdf-endpoint.md Section 2)."""
    try:
        import fitz  # PyMuPDF -- lazy import, mirrors this repo's convention
        # of not hard-failing app startup on an optional/heavy dependency.
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF not available — run: pip install PyMuPDF"
        ) from e

    doc = fitz.open(stream=book_bytes, filetype="pdf")
    try:
        practice_doc = fitz.open(stream=practice_bytes, filetype="pdf")
        try:
            doc.insert_pdf(practice_doc)
        finally:
            practice_doc.close()
        return doc.tobytes()
    finally:
        doc.close()
