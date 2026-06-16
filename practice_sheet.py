"""Chinese character writing-practice sheet generator.

Stateless module — lazily imports anthropic (mirrors gemini_generator/meshy_generator
conventions). The actual PDF is produced by Claude running ReportLab inside Anthropic's
code-execution sandbox; this module drives the API loop and retrieves the file via the
Files API.
"""

import time
from typing import Optional

# ── Fixed instructions embedded verbatim in every request ────────────────────

_PRACTICE_SPEC = """\
Chinese Practice Sheet Generator
Build a printable Chinese character writing-practice sheet as a single-page US-Letter PDF with ReportLab.
Layout: Header = the Chinese book title + "Writing Practice", a subtitle with the English book name, and a "Name / Date" line. Then UP TO 8 characters (fewer if the text has fewer distinct suitable new characters; never repeat a character on the sheet), ordered simplest→most strokes, one per row. Each row: a label area (the hanzi + its bold pinyin + its italic English meaning) followed by 6 田字格 (tian zi ge) boxes — box 1 a faded gray trace of the character, boxes 2–6 blank — each box with a pinyin line above it (generous space, ≥16pt) and dashed crosshairs inside. A footer with brief usage instructions. Light gray grid, minimal ink.
Colors (RGB 0–1): grid 0.78, trace 0.72, dashed 0.85, pinyin line 0.80, heading 0.15, secondary 0.35, separator 0.92.
Fonts: register the CJK font with pdfmetrics.registerFont(TTFont('WQY','/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', subfontIndex=0)); it renders both hanzi and pinyin tone marks. Do NOT use UnicodeCIDFont('STSong-Light'), Noto CJK .ttc (OTF), or Helvetica for pinyin (tone marks become black squares).
Characters: choose UP TO 8 high-frequency characters drawn FROM the provided story's Chinese text, favoring ones useful for a young learner; order simplest→most strokes; give each its pinyin (with tone marks) and a short English gloss.
Verify the output by rasterizing with pdftoppm before finishing, to confirm the Chinese glyphs render (not empty boxes).
"""

_FONT_ENV_NOTE = """\
Environment note: /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc (subfontIndex=0) is present and covers Simplified Chinese + pinyin tone marks. reportlab 4.2.2 and pdftoppm are preinstalled. No internet access or pip installs are needed or available.
"""

# How long to wait across ALL loop turns before giving up (seconds)
_WALL_CLOCK_LIMIT = 150
# Max number of "pause_turn" continuations
_MAX_CONTINUATIONS = 6


def generate_practice_pdf_bytes(
    title_en: str,
    title_zh: str,
    title_pinyin: str,
    zh_text: str,
    api_key: str,
) -> bytes:
    """Call Claude with the code-execution tool to produce a 田字格 practice PDF.

    Runs the pause_turn continuation loop (capped at _MAX_CONTINUATIONS turns and
    _WALL_CLOCK_LIMIT seconds). Collects Files-API file_ids from every
    bash_code_execution_tool_result block across all turns, then resolves which is
    the PDF via retrieve_metadata (newest → oldest). Downloads and returns the PDF
    bytes.

    Raises RuntimeError with a clear message on timeout, no PDF, or API error.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package is not installed. Run: pip install anthropic"
        )

    # Per-call client — never cache a module-level client (mirrors every other call site)
    client = anthropic.Anthropic(api_key=api_key)

    user_message = "\n\n".join([
        _PRACTICE_SPEC,
        _FONT_ENV_NOTE,
        f"English title: {title_en}",
        f"Chinese title: {title_zh}",
        f"Pinyin title: {title_pinyin}",
        f"Chinese story text:\n{zh_text}",
        "Save the final practice sheet as a PDF, verify it with pdftoppm, then reply 'done'.",
    ])

    messages = [{"role": "user", "content": user_message}]
    tools = [{"type": "code_execution_20260120", "name": "code_execution"}]
    # NOTE: do NOT set tool_choice — server tools must not be force-named

    # Collect file_ids from every bash_code_execution_tool_result block across turns.
    # The model may produce the PDF in one execution and verification PNGs in another;
    # or it may regenerate the PDF. We iterate newest→oldest when resolving.
    collected_file_ids: list[str] = []

    deadline = time.monotonic() + _WALL_CLOCK_LIMIT
    continuations = 0

    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Practice sheet generation timed out after {_WALL_CLOCK_LIMIT}s "
                "(wall-clock limit reached before Claude finished)."
            )

        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=8000,
            tools=tools,
            messages=messages,
        )

        # Harvest file_ids from this turn's result blocks
        for block in resp.content:
            if getattr(block, "type", None) == "bash_code_execution_tool_result":
                # block.content is a bash_code_execution_result object
                inner = getattr(block, "content", None)
                if inner is None:
                    continue
                # inner.content is a list of output items
                items = getattr(inner, "content", None) or []
                for item in items:
                    if getattr(item, "type", None) == "bash_code_execution_output":
                        fid = getattr(item, "file_id", None)
                        if fid:
                            collected_file_ids.append(fid)

        # Check if we should continue
        stop_reason = getattr(resp, "stop_reason", None)
        if stop_reason != "pause_turn":
            # end_turn, max_tokens, or other terminal state
            break

        if continuations >= _MAX_CONTINUATIONS:
            raise RuntimeError(
                f"Practice sheet generation exceeded {_MAX_CONTINUATIONS} continuations "
                "without completing. The task may be too complex — please try again."
            )

        # Append the assistant turn and loop
        messages.append({"role": "assistant", "content": resp.content})
        continuations += 1

    # Resolve which file_id is the PDF — iterate newest → oldest
    pdf_file_id: Optional[str] = None
    for fid in reversed(collected_file_ids):
        try:
            meta = client.beta.files.retrieve_metadata(fid)
            fname = getattr(meta, "filename", "") or ""
            mime = getattr(meta, "mime_type", "") or ""
            if fname.endswith(".pdf") or mime == "application/pdf":
                pdf_file_id = fid
                break
        except Exception:
            # If metadata retrieval fails for a particular file, keep trying others
            continue

    if pdf_file_id is None:
        raise RuntimeError(
            "Claude produced no PDF file. "
            f"Collected {len(collected_file_ids)} file(s) but none matched a PDF. "
            "This may be a transient sandbox issue — please try again."
        )

    # Download PDF bytes — the SDK auto-injects the files-api-2025-04-14 beta header;
    # do NOT pass betas= explicitly
    pdf_bytes = client.beta.files.download(pdf_file_id).read()
    return pdf_bytes
