"""Local (no-LLM) Chinese word writing-practice sheet generator.

Segments a decomposed storybook into words (1-2+ chars), frequency-counts them,
and renders a printable US-Letter PDF entirely in-process with ReportLab — no
Claude call. Picks the N most frequent words, shows each word + its pinyin +
English translation, and lays out 田字格 (tian zi ge) practice boxes per word
(the word is traced faded once, then repeated blank across the row).

Word segmentation and English glosses come from the bundled offline **CC-CEDICT**
dictionary (`pycccedict`, CC-BY-SA) — no network. Pinyin is CC-CEDICT's, converted
from numeric tones (yue4) to diacritics (yuè). A host CJK font that also covers
pinyin tone marks is discovered at import time.
"""
import io
import os
import re
from collections import OrderedDict

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── Font discovery ──────────────────────────────────────────────────────────
# (path, subfontIndex|None) — first that exists is registered. All of these were
# verified to cover both Simplified Chinese and pinyin tone marks (ǎ ǐ ē ǔ à).
_FONT_CANDIDATES = [
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/System/Library/Fonts/STHeiti Light.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/Library/Fonts/Arial Unicode.ttf", None),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),  # Linux
]
_FONT_NAME = "PracticeCJK"
_font_registered = False


def _ensure_font():
    global _font_registered
    if _font_registered:
        return
    for path, idx in _FONT_CANDIDATES:
        if os.path.exists(path):
            kwargs = {"subfontIndex": idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont(_FONT_NAME, path, **kwargs))
            _font_registered = True
            return
    raise RuntimeError(
        "No CJK font found for the local practice sheet. Looked in: "
        + ", ".join(p for p, _ in _FONT_CANDIDATES)
    )


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0xF900 <= cp <= 0xFAFF
    )


# ── Pinyin syllable splitter (fallback for books without a `characters` array,
#    e.g. older Gallery books). Mirrors storybook_print.js _splitPinyinSyllables /
#    _buildCharacters so per-character pinyin can be recovered from the page's
#    `zh` (hanzi) + `pinyin` (full reading string). Heuristic but good enough. ──
_PY_INITIALS = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
                "g", "k", "h", "j", "q", "x", "z", "c", "s", "r", "y", "w"]
_PY_VOWELS = set("aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ")
_PY_KEEP = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
               "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüÜ")


def _is_vowel(ch: str) -> bool:
    return ch.lower() in _PY_VOWELS


def _next_syllable(s: str):
    low = s.lower()
    i = 0
    for init in _PY_INITIALS:
        if low.startswith(init) and len(init) < len(s) and _is_vowel(s[len(init)]):
            i = len(init)
            break
    if i >= len(s) or not _is_vowel(s[i]):
        return None
    while i < len(s) and _is_vowel(s[i]):
        i += 1
    if low[i:i + 2] == "ng":
        i += 2
    elif i < len(s) and s[i] == "n" and (i + 1 >= len(s) or not _is_vowel(s[i + 1])):
        i += 1
    elif i < len(s) and s[i] == "r" and (i + 1 >= len(s) or not _is_vowel(s[i + 1])):
        i += 1
    return s[:i] if i > 0 else None


def _split_pinyin_syllables(pinyin: str):
    out = []
    for token in (pinyin or "").split():
        rest = "".join(ch for ch in token if ch in _PY_KEEP)
        while rest:
            syl = _next_syllable(rest)
            if not syl:
                rest = rest[1:]
                continue
            out.append(syl)
            rest = rest[len(syl):]
    return out


def _derive_characters(zh: str, pinyin: str):
    """Build [{c,p}] from a sentence + its reading, aligning syllables to hanzi."""
    syllables = _split_pinyin_syllables(pinyin)
    si = 0
    result = []
    for c in (zh or ""):
        if _is_cjk(c):
            p = syllables[si] if si < len(syllables) else ""
            si += 1
            result.append({"c": c, "p": p})
        else:
            result.append({"c": c, "p": ""})
    return result


# ── CC-CEDICT dictionary (bundled, offline) ─────────────────────────────────
_cedict_singleton = None


def _cedict():
    """Lazily construct the bundled CC-CEDICT (pycccedict). Lazy so the module
    imports even if the package is absent — the error surfaces only when a
    practice sheet is actually requested."""
    global _cedict_singleton
    if _cedict_singleton is None:
        try:
            from pycccedict.cccedict import CcCedict
        except ImportError as e:
            raise RuntimeError(
                "pycccedict is not installed. Run: pip install pycccedict"
            ) from e
        _cedict_singleton = CcCedict()
    return _cedict_singleton


# ── Numeric-tone pinyin (yue4 guang1) -> diacritics (yuè guāng) ──────────────
_TONE_MARKS = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì",
    "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ",
}


def _accent_syllable(syl: str) -> str:
    syl = (syl or "").strip()
    if not syl:
        return syl
    tone = 0
    if syl[-1].isdigit():
        tone = int(syl[-1])
        syl = syl[:-1]
    syl = syl.replace("u:", "ü").replace("v", "ü")
    low = syl.lower()
    if tone in (0, 5):
        return syl
    # Standard tone-placement: a/e win; else 'o' in 'ou'; else the last vowel.
    if "a" in low:
        target = "a"
    elif "e" in low:
        target = "e"
    elif "ou" in low:
        target = "o"
    else:
        target = next((ch for ch in reversed(low) if ch in "aeiouü"), None)
    marks = _TONE_MARKS.get(target) if target else None
    if not marks:
        return syl
    idx = low.index(target)
    return syl[:idx] + marks[tone - 1] + syl[idx + 1:]


def _num_to_accent(numeric: str) -> str:
    return " ".join(_accent_syllable(s) for s in (numeric or "").split())


# ── English gloss cleanup ────────────────────────────────────────────────────
_SKIP_DEF_PREFIXES = ("cl:", "variant of", "old variant", "unofficial variant",
                      "see ", "abbr.", "surname ")


def _clean_gloss(defs) -> str:
    """Pick the first kid-usable English sense from CC-CEDICT's definition list,
    stripping classifier notes (CL:...), [pinyin] cross-refs, and CJK variant
    markers. Returns '' if nothing usable (e.g. grammatical particles)."""
    for d in defs or []:
        d = (d or "").strip()
        if not d or d.lower().startswith(_SKIP_DEF_PREFIXES):
            continue
        d = re.sub(r"\(?CL:[^)]*\)?", "", d)         # classifier notes
        d = re.sub(r"\[[^\]]*\]", "", d)              # [pinyin] refs
        d = re.sub(r"[|㐀-鿿]+", "", d)       # CJK variant chars / bars
        d = re.sub(r"^\([^)]*\)\s*", "", d)           # leading grammatical note, e.g. "(adverb of degree)"
        d = re.sub(r"\s+", " ", d).strip(" ;,/")
        if d:
            return d[:48]
    return ""


# ── Word segmentation (greedy longest-match against CC-CEDICT) ───────────────
_MAX_WORD = 4


def _is_proper_noun(cc, word: str) -> bool:
    """CC-CEDICT capitalizes the pinyin of proper nouns (place/person names),
    e.g. 大树 -> "Dà shù" (Tashu township). Skip those — a kids' vocab sheet
    wants common words, and 大树 should segment as 大 + 树 (big + tree)."""
    p = cc.get_pinyin(word) or ""
    return p[:1].isupper()


def _segment_words(zh: str):
    """Greedy longest-match segmentation over a Chinese sentence: at each
    position take the longest common CC-CEDICT headword (up to 4 chars, proper
    nouns excluded), else a single char. Non-CJK is skipped."""
    cc = _cedict()
    s = zh or ""
    n = len(s)
    words = []
    i = 0
    while i < n:
        if not _is_cjk(s[i]):
            i += 1
            continue
        matched = None
        for length in range(min(_MAX_WORD, n - i), 0, -1):
            cand = s[i:i + length]
            if (all(_is_cjk(x) for x in cand)
                    and cc.get_definitions(cand)
                    and not (length > 1 and _is_proper_noun(cc, cand))):
                matched = cand
                break
        if matched:
            words.append(matched)
            i += len(matched)
        else:
            words.append(s[i])   # unknown single char — kept, filtered later if no gloss
            i += 1
    return words


# ── Frequency selection ─────────────────────────────────────────────────────
def top_words(pages, n=8):
    """Return up to `n` (word, pinyin, english) triples, most frequent first.

    Segments every page's `zh` text into CC-CEDICT words, frequency-counts them,
    and keeps only words with a usable English gloss (drops bare particles).
    Multi-character words are lightly preferred on ties so the sheet favours
    meaningful word pairs over isolated characters."""
    counts = OrderedDict()   # word -> count (insertion order = first appearance)
    for pg in pages or []:
        for w in _segment_words(pg.get("zh") or ""):
            counts[w] = counts.get(w, 0) + 1

    cc = _cedict()
    order = list(counts)
    entries = []
    for w, cnt in counts.items():
        gloss = _clean_gloss(cc.get_definitions(w))
        if not gloss:
            continue
        pinyin = _num_to_accent(cc.get_pinyin(w) or "")
        entries.append((w, cnt, pinyin, gloss))

    # Prefer meaningful word PAIRS: multi-char words first, then by frequency,
    # then first appearance. Single-char words fill only if pairs run short.
    entries.sort(key=lambda e: (-(len(e[0]) >= 2), -e[1], order.index(e[0])))
    return [(w, pinyin, gloss) for (w, cnt, pinyin, gloss) in entries[:n]]


# ── Rendering ───────────────────────────────────────────────────────────────
# Colors (RGB 0-1) — light, minimal ink.
_GRID = (0.78, 0.78, 0.78)
_TRACE = (0.72, 0.72, 0.72)
_DASH = (0.85, 0.85, 0.85)
_HEAD = (0.15, 0.15, 0.15)
_SECONDARY = (0.35, 0.35, 0.35)
_SEPARATOR = (0.92, 0.92, 0.92)


def _draw_tianzige(c, x, y, size, char=None):
    """Draw one 田字格 box with bottom-left at (x, y). Optional faded trace char."""
    # outer box
    c.setStrokeColorRGB(*_GRID)
    c.setLineWidth(0.8)
    c.rect(x, y, size, size, stroke=1, fill=0)
    # dashed crosshairs
    c.setStrokeColorRGB(*_DASH)
    c.setLineWidth(0.6)
    c.setDash(2, 2)
    c.line(x, y + size / 2, x + size, y + size / 2)        # horizontal
    c.line(x + size / 2, y, x + size / 2, y + size)        # vertical
    c.setDash()  # reset
    # faded trace character
    if char:
        c.setFillColorRGB(*_TRACE)
        fs = size * 0.78
        c.setFont(_FONT_NAME, fs)
        # vertically center the glyph: baseline ≈ y + (size - cap)/2
        tw = c.stringWidth(char, _FONT_NAME, fs)
        c.drawString(x + (size - tw) / 2, y + (size - fs * 0.72) / 2, char)


def render_pdf_bytes(title_zh, title_en, words, boxes=None):
    """words: list of (word, pinyin, english). Returns PDF bytes.

    Each row shows the word + pinyin + English on the left, then 田字格 boxes on
    the right: the word is traced faded once, then repeated blank across the row
    (grouped so a 2-character word is written as a unit). `boxes` is accepted for
    backward-compat but ignored — the box count is derived from the row width."""
    _ensure_font()
    buf = io.BytesIO()
    W, H = letter  # 612 x 792
    c = canvas.Canvas(buf, pagesize=letter)

    ml, mr, mt, mb = 36, 36, 40, 36

    # ── Header ──
    y = H - mt
    c.setFillColorRGB(*_HEAD)
    c.setFont(_FONT_NAME, 20)
    head = f"{title_zh}  ·  Writing Practice" if title_zh else "Writing Practice"
    c.drawString(ml, y - 16, head)
    y -= 26
    if title_en:
        c.setFillColorRGB(*_SECONDARY)
        c.setFont(_FONT_NAME, 11)
        c.drawString(ml, y - 11, title_en)
        y -= 18
    # Name / Date line
    c.setFillColorRGB(*_SECONDARY)
    c.setFont(_FONT_NAME, 10)
    c.drawString(ml, y - 11, "Name: ______________________")
    c.drawRightString(W - mr, y - 11, "Date: ______________")
    y -= 20
    # separator
    c.setStrokeColorRGB(*_SEPARATOR)
    c.setLineWidth(1)
    c.line(ml, y, W - mr, y)
    y -= 6

    # ── Rows ──
    label_w = 150       # room for word + pinyin + English gloss
    gap = 6             # between adjacent boxes
    group_gap = 16      # extra space between repetitions of the word
    footer_h = 22
    rows = max(1, len(words))
    row_h = (y - mb - footer_h) / rows
    box = min(46, row_h - 14)          # square box, capped
    boxes_x0 = ml + label_w
    boxes_x1 = W - mr

    for (word, py, english) in words:
        row_bottom = y - row_h
        by = row_bottom + (row_h - box) / 2      # box bottom, vertically centered

        # ── Left label: word (hanzi), pinyin, English ──
        # Top-align the three lines within the row.
        wchars = [ch for ch in word if _is_cjk(ch)] or list(word)
        c.setFillColorRGB(*_HEAD)
        word_fs = 26
        c.setFont(_FONT_NAME, word_fs)
        ty = row_bottom + row_h - word_fs
        c.drawString(ml, ty, word)
        if py:
            c.setFillColorRGB(*_SECONDARY)
            c.setFont(_FONT_NAME, 11)
            c.drawString(ml, ty - 14, py)
        if english:
            c.setFillColorRGB(*_SECONDARY)
            c.setFont(_FONT_NAME, 10)
            eng = english if len(english) <= 24 else english[:23] + "…"
            c.drawString(ml, ty - 28, eng)

        # ── Right: 田字格 boxes — the word traced once, then repeated blank ──
        L = len(wchars)
        bx = boxes_x0
        rep = 0
        while bx + L * box + (L - 1) * gap <= boxes_x1 + 0.5:
            for k in range(L):
                _draw_tianzige(c, bx, by, box, char=(wchars[k] if rep == 0 else None))
                bx += box + gap
            bx += group_gap - gap    # extra gap between word groups
            rep += 1

        y -= row_h

    # ── Footer ──
    c.setFillColorRGB(*_SECONDARY)
    c.setFont(_FONT_NAME, 9)
    c.drawString(ml, mb,
                 "Trace the gray word in the first group, then practise writing it in the rest. "
                 "Keep each stroke inside the dashed lines.")

    c.showPage()
    c.save()
    return buf.getvalue()


# ── self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pages = [
        {"zh": "月光照亮了森林，小猴子看见了朋友。"},
        {"zh": "朋友和猴子一起玩，月光很美。"},
    ]
    words = top_words(pages, n=8)
    print("top_words:", words)
    data = render_pdf_bytes("猴王的故事", "The Monkey King's Story", words)
    out = "/tmp/sample_practice.pdf"
    open(out, "wb").write(data)
    print("wrote", out, len(data), "bytes")
