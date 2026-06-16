"""Local (no-LLM) Chinese character writing-practice sheet generator.

Frequency-counts the hanzi in a decomposed storybook and renders a printable
US-Letter PDF entirely in-process with ReportLab — no Claude call. Picks the
N most frequent characters, shows each character + its pinyin, and lays out a
row of 田字格 (tian zi ge) practice boxes per character (box 1 = faded trace,
the rest blank). Translation is intentionally omitted for now.

Pinyin comes straight from the story's per-character data (`characters: [{c,p}]`)
— no dictionary or pinyin library required. A host CJK font that also covers
pinyin tone marks is discovered at import time.
"""
import io
import os
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


# ── Frequency selection ─────────────────────────────────────────────────────
def top_characters(pages, n=10):
    """Return up to `n` (char, pinyin) pairs, most frequent first.

    Counts CJK characters across every page's `characters` array, keeping the
    first non-empty pinyin seen for each. Ties broken by first appearance.
    """
    counts = OrderedDict()   # char -> count (insertion order = first appearance)
    pinyin = {}              # char -> pinyin
    for pg in pages or []:
        items = pg.get("characters")
        if not items:
            # Fallback for books saved without per-character data (e.g. older
            # Gallery books): derive [{c,p}] from the sentence + its reading.
            items = _derive_characters(pg.get("zh") or "", pg.get("pinyin") or "")
        for item in items:
            c = (item.get("c") or "").strip()
            if not c or not _is_cjk(c):
                continue
            counts[c] = counts.get(c, 0) + 1
            # Lowercase: a character's reading in isolation is conventionally
            # lowercase (the fallback can inherit sentence-initial capitals).
            p = (item.get("p") or "").strip().lower()
            if p and c not in pinyin:
                pinyin[c] = p
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], list(counts).index(kv[0])))
    return [(c, pinyin.get(c, "")) for c, _ in ordered[:n]]


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


def render_pdf_bytes(title_zh, title_en, chars, boxes=8):
    """chars: list of (hanzi, pinyin). Returns PDF bytes."""
    _ensure_font()
    buf = io.BytesIO()
    W, H = letter  # 612 x 792
    c = canvas.Canvas(buf, pagesize=letter)

    ml, mr, mt, mb = 36, 36, 40, 36
    usable_w = W - ml - mr

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
    label_w = 64
    gap = 6              # between label and boxes, and between boxes
    boxes_area = usable_w - label_w - gap
    box = (boxes_area - gap * (boxes - 1)) / boxes
    footer_h = 22
    rows = max(1, len(chars))
    row_h = (y - mb - footer_h) / rows
    # box can't exceed row height
    box = min(box, row_h - 8)

    for (hanzi, py) in chars:
        row_top = y
        row_bottom = y - row_h
        by = row_bottom + (row_h - box) / 2  # box bottom, vertically centered in row
        # label: big hanzi + pinyin underneath
        c.setFillColorRGB(*_HEAD)
        big = min(34, box * 0.62)
        c.setFont(_FONT_NAME, big)
        c.drawString(ml, by + box / 2 - big * 0.30, hanzi)
        if py:
            c.setFillColorRGB(*_SECONDARY)
            c.setFont(_FONT_NAME, 11)
            c.drawString(ml, by + box / 2 - big * 0.30 - 14, py)
        # boxes
        bx = ml + label_w + gap
        for i in range(boxes):
            _draw_tianzige(c, bx, by, box, char=hanzi if i == 0 else None)
            bx += box + gap
        y -= row_h

    # ── Footer ──
    c.setFillColorRGB(*_SECONDARY)
    c.setFont(_FONT_NAME, 9)
    c.drawString(ml, mb,
                 "Trace the gray character in the first box, then practice writing it in the rest. "
                 "Keep each stroke inside the dashed lines.")

    c.showPage()
    c.save()
    return buf.getvalue()


# ── self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = [
        ("我", "wǒ"), ("你", "nǐ"), ("他", "tā"), ("大", "dà"), ("小", "xiǎo"),
        ("山", "shān"), ("水", "shuǐ"), ("火", "huǒ"), ("木", "mù"), ("人", "rén"),
    ]
    data = render_pdf_bytes("猴王的故事", "The Monkey King's Story", sample, boxes=8)
    out = "/Users/chen/.claude/jobs/b03c4b49/tmp/sample_practice.pdf"
    open(out, "wb").write(data)
    print("wrote", out, len(data), "bytes")
