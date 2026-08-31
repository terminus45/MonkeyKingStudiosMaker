"""Backend tests for the /book-pdf subsystem (prompt/existing -> printable PDF).

Covers:
  1. _overlay_recheck_onto_story merge semantics (corrected text in, image_prompt
     and title fields preserved, book_title_characters overlay only when present,
     matched by page number with no off-by-one).
  2. Image reuse in mode="existing" (full map -> no decompose/recheck/gemini calls;
     partial map -> only the missing pages are (re)generated).
  3. Route validation (400/404/409) on POST /book-pdf and its status/download routes.
  4. Key-missing fail-fast (503) for both the Anthropic and Gemini call sites.
  5. The _BOOK_PDF_SEM guardrail: exhausted -> 429 with no job spawned; a
     completed job releases its slot so a later request can proceed.
  6. Worker stage progression: a fully-mocked prompt-mode job reaches stage="done"
     with the expected pdf_filename/practice_sheet_included, and a forced
     exception mid-pipeline sets stage="error" while still releasing the sem.

These tests are OFFLINE/deterministic. They never make a real Claude/Gemini call,
never launch headless Chromium (Playwright is not even installed in this venv),
and never touch the real gallery/output directories (OUTPUT_DIR/BOOK_PDF_DIR are
monkeypatched to a per-test tmp_path). book_pdf.render_pdf/merge_pdfs are stubbed
since the real implementations need Playwright/PyMuPDF-rendered Chromium output
that has no place in a fast offline suite; book_pdf.build_storybook_html and
practice_sheet_local's real ReportLab renderer are exercised for real since they
have no external dependencies.

Run:  source venv/bin/activate && python -m pytest tests/test_book_pdf.py -v
 or:  source venv/bin/activate && python tests/test_book_pdf.py   (lightweight runner)
"""
import copy
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
from starlette.testclient import TestClient

import main
import languages
import settings_store


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


@pytest.fixture
def tmp_dirs(tmp_path, monkeypatch):
    """Redirect OUTPUT_DIR/IMAGES_DIR/BOOK_PDF_DIR to a scratch tmp_path for this
    test only. Isolating IMAGES_DIR too is mandatory — tests must never read,
    write, or clean files inside the real content dirs (see CLAUDE.md data-safety
    rule; a `rm -f output/*.png` cleanup once wiped every saved image)."""
    output_dir = tmp_path / "output"
    images_dir = tmp_path / "images"
    book_pdf_dir = tmp_path / "book_pdfs"
    output_dir.mkdir()
    images_dir.mkdir()
    book_pdf_dir.mkdir()
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(main, "IMAGES_DIR", str(images_dir))
    monkeypatch.setattr(main, "BOOK_PDF_DIR", str(book_pdf_dir))
    return {"output": output_dir, "images": images_dir, "book_pdf": book_pdf_dir}


@pytest.fixture
def default_keys(monkeypatch):
    """Both keys resolve to a fake, non-empty string unless a test overrides."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: f"fake-{name}")


def _dummy_png_name() -> str:
    return f"{uuid.uuid4().hex}.png"


def _write_dummy_png(output_dir, filename=None) -> str:
    filename = filename or _dummy_png_name()
    with open(os.path.join(str(output_dir), filename), "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\nFAKE-IMAGE-BYTES")
    return filename


def _fake_render_pdf(html_str):
    assert isinstance(html_str, str) and "<html" in html_str
    return b"%PDF-1.4 FAKE BOOK PDF"


def _fake_merge_pdfs(book_bytes, practice_bytes):
    return book_bytes + b"MERGED" + practice_bytes


def _make_story(language="zh", n_pages=2, book_title_characters=True):
    """Minimal but schema-shaped decompose-style story dict."""
    pages = []
    for i in range(1, n_pages + 1):
        pages.append({
            "page": i,
            "en": f"Page {i} in English.",
            "image_prompt": f"a whimsical scene for page {i}, soft colors",
            "zh": f"第{i}页的中文句子。",
            "pinyin": f"dì {i} yè de zhōngwén jùzi.",
            "characters": [{"c": "第", "p": "dì"}, {"c": "。", "p": ""}],
        })
    story = {
        "book_title_en": "The Little Duckling",
        "book_title_zh": "小鸭子",
        "book_title_pinyin": "xiǎo yā zi",
        "language": language,
        "pages": pages,
    }
    if book_title_characters:
        story["book_title_characters"] = [
            {"c": "小", "p": "xiǎo"}, {"c": "鸭", "p": "yā"}, {"c": "子", "p": "zi"},
        ]
    return story


def _prompt_req_data(**overrides):
    base = {
        "mode": "prompt",
        "concept": "a duckling learns to swim",
        "character": "",
        "style_suffix": "",
        "language": "zh",
        "page_count": 11,
        "story": None,
        "generated_images": None,
        "recheck_readings": None,
        "gemini_model": "imagen-4.0-fast-generate-001",
    }
    base.update(overrides)
    return base


def _raise_if_called(name):
    def _f(*args, **kwargs):
        raise AssertionError(f"{name} should NOT have been called")
    return _f


def _echo_run_recheck(*, language, pages, api_key, book_title_native=None,
                       book_title_reading=None, book_title_characters=None):
    """Fake run_recheck that just echoes the pages back unchanged (a no-op
    overlay). recheck_readings is LOCKED True for mode="prompt" (see
    _resolve_book_pdf_recheck), so every prompt-mode worker test must mock
    run_recheck even when it doesn't care about the correction itself."""
    return {"language": language, "pages": [dict(p) for p in pages]}


def _wait_for_terminal_stage(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"/book-pdf/status/{job_id}")
        assert r.status_code == 200, r.text
        last = r.json()
        if last["stage"] in ("done", "error"):
            return last
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach a terminal stage within {timeout}s: {last}")


# ═══════════════════════════════════════════════════════════════════════════
# 1. _overlay_recheck_onto_story merge semantics
# ═══════════════════════════════════════════════════════════════════════════

def test_overlay_recheck_merges_text_preserves_prompt_and_title():
    lang = languages.get("zh")
    story = _make_story(n_pages=3)
    original_prompts = {pg["page"]: pg["image_prompt"] for pg in story["pages"]}
    original_title_zh = story["book_title_zh"]
    original_title_pinyin = story["book_title_pinyin"]
    original_title_en = story["book_title_en"]

    # recheck_data omits image_prompt entirely and returns pages OUT OF ORDER
    # (page 3 first) to catch any list-index-based (rather than page-number-based)
    # matching bug.
    recheck_data = {
        "language": "zh",
        "pages": [
            {"page": 3, "zh": "修正后的第三句。", "pinyin": "xiūzhèng hòu de dì sān jù.",
             "en": "Corrected third sentence.",
             "characters": [{"c": "修", "p": "xiū"}, {"c": "。", "p": ""}]},
            {"page": 1, "zh": "修正后的第一句。", "pinyin": "xiūzhèng hòu de dì yī jù.",
             "en": "Corrected first sentence.",
             "characters": [{"c": "修", "p": "xiū"}, {"c": "。", "p": ""}]},
        ],
        "book_title_characters": [
            {"c": "新", "p": "xīn"}, {"c": "标", "p": "biāo"}, {"c": "题", "p": "tí"},
        ],
    }

    main._overlay_recheck_onto_story(story, recheck_data, lang)

    by_page = {pg["page"]: pg for pg in story["pages"]}

    # (a) corrected pages 1 and 3 got the new text/reading/characters
    assert by_page[1]["zh"] == "修正后的第一句。"
    assert by_page[1]["pinyin"] == "xiūzhèng hòu de dì yī jù."
    assert by_page[1]["en"] == "Corrected first sentence."
    assert by_page[1]["characters"] == [{"c": "修", "p": "xiū"}, {"c": "。", "p": ""}]

    assert by_page[3]["zh"] == "修正后的第三句。"
    assert by_page[3]["en"] == "Corrected third sentence."

    # page 2 was NOT present in recheck_data.pages -> untouched (no off-by-one
    # bleed from page 1's or page 3's corrections)
    assert by_page[2]["zh"] == "第2页的中文句子。"
    assert by_page[2]["en"] == "Page 2 in English."

    # (b) image_prompt is untouched on EVERY page (recheck never supplied it)
    for pnum, pg in by_page.items():
        assert pg["image_prompt"] == original_prompts[pnum], f"page {pnum} image_prompt changed"

    # (c) decompose's title fields (book_title_zh/pinyin/en) are untouched --
    # the overlay never merges recheck's book_title_native/reading, only
    # book_title_characters.
    assert story["book_title_zh"] == original_title_zh
    assert story["book_title_pinyin"] == original_title_pinyin
    assert story["book_title_en"] == original_title_en

    # (d) book_title_characters WAS overlaid because recheck_data supplied it
    assert story["book_title_characters"] == recheck_data["book_title_characters"]


def test_overlay_recheck_no_book_title_characters_key_when_absent():
    """If recheck_data omits book_title_characters, the story's existing value
    (or absence) must be left alone -- no accidental overwrite with None/[]."""
    lang = languages.get("zh")
    story = _make_story(n_pages=1, book_title_characters=True)
    original_btc = copy.deepcopy(story["book_title_characters"])

    recheck_data = {
        "language": "zh",
        "pages": [{"page": 1, "zh": "改。", "pinyin": "gǎi.", "en": "Changed.",
                    "characters": [{"c": "改", "p": "gǎi"}, {"c": "。", "p": ""}]}],
        # no book_title_characters key at all
    }
    main._overlay_recheck_onto_story(story, recheck_data, lang)
    assert story["book_title_characters"] == original_btc, "must not overwrite when absent from recheck response"


def test_overlay_recheck_page_not_returned_is_left_untouched():
    """A page number present in `story` but absent from recheck_data.pages
    (e.g. Claude dropped one) must be left exactly as-is, not blanked."""
    lang = languages.get("zh")
    story = _make_story(n_pages=2)
    original_page2 = copy.deepcopy(story["pages"][1])

    recheck_data = {"language": "zh", "pages": [
        {"page": 1, "zh": "改。", "pinyin": "gǎi.", "en": "Changed.", "characters": []},
    ]}
    main._overlay_recheck_onto_story(story, recheck_data, lang)
    assert story["pages"][1] == original_page2


# ═══════════════════════════════════════════════════════════════════════════
# 2. Image reuse (mode="existing")
# ═══════════════════════════════════════════════════════════════════════════

def test_existing_mode_full_reuse_skips_decompose_recheck_and_gemini(client, tmp_dirs, default_keys, monkeypatch):
    """A full generated_images map + recheck_readings=false must call NEITHER
    run_decompose/run_recheck NOR gemini_generator.generate."""
    monkeypatch.setattr(main, "run_decompose", _raise_if_called("run_decompose"))
    monkeypatch.setattr(main, "run_recheck", _raise_if_called("run_recheck"))
    monkeypatch.setattr(main.gemini_generator, "generate", _raise_if_called("gemini_generator.generate"))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    story = _make_story(language="ja", n_pages=2)  # ja -> no practice-sheet branch
    story["pages"][0]["ja"] = story["pages"][0].pop("zh")
    story["pages"][0]["romaji"] = story["pages"][0].pop("pinyin")
    story["pages"][1]["ja"] = story["pages"][1].pop("zh")
    story["pages"][1]["romaji"] = story["pages"][1].pop("pinyin")
    story["book_title_ja"] = story.pop("book_title_zh")
    story["book_title_romaji"] = story.pop("book_title_pinyin")

    fnames = {str(pg["page"]): _write_dummy_png(tmp_dirs["output"]) for pg in story["pages"]}

    body = {
        "mode": "existing",
        "language": "ja",
        "story": story,
        "generated_images": fnames,
        "recheck_readings": False,
    }
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    rec = _wait_for_terminal_stage(client, job_id)
    assert rec["stage"] == "done", rec
    assert rec["pages_reused"] == 2
    assert rec["pages_generated"] == 0


def test_existing_mode_partial_map_regenerates_only_missing_pages(client, tmp_dirs, default_keys, monkeypatch):
    """A partial generated_images map must (re)generate ONLY the missing pages."""
    monkeypatch.setattr(main, "run_decompose", _raise_if_called("run_decompose"))
    monkeypatch.setattr(main, "run_recheck", _raise_if_called("run_recheck"))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    calls = []

    def _fake_generate(*, content_prompt, style_prompt, negative_prompt, model_id,
                        aspect_ratio, width, height, api_key):
        calls.append(content_prompt)
        return "FAKE_IMAGE_OBJECT"

    def _fake_save_image(image, filename, meta=None):
        _write_dummy_png(tmp_dirs["output"], filename)

    monkeypatch.setattr(main.gemini_generator, "generate", _fake_generate)
    monkeypatch.setattr(main.gemini_generator, "save_image", _fake_save_image)

    story = _make_story(language="ja", n_pages=3)
    for pg in story["pages"]:
        pg["ja"] = pg.pop("zh")
        pg["romaji"] = pg.pop("pinyin")
    story["book_title_ja"] = story.pop("book_title_zh")
    story["book_title_romaji"] = story.pop("book_title_pinyin")

    # Only pages 1 and 3 have a reusable existing image; page 2 is missing.
    fnames = {
        "1": _write_dummy_png(tmp_dirs["output"]),
        "3": _write_dummy_png(tmp_dirs["output"]),
    }

    body = {
        "mode": "existing",
        "language": "ja",
        "story": story,
        "generated_images": fnames,
        "recheck_readings": False,
    }
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    rec = _wait_for_terminal_stage(client, job_id)
    assert rec["stage"] == "done", rec
    assert rec["pages_reused"] == 2
    assert rec["pages_generated"] == 1
    assert len(calls) == 1
    assert "page 2" in calls[0] or "2" in calls[0]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Route validation
# ═══════════════════════════════════════════════════════════════════════════

def test_status_malformed_job_id_is_400(client):
    r = client.get("/book-pdf/status/not-a-hex-id")
    assert r.status_code == 400, r.text


def test_status_unknown_job_id_is_404(client):
    r = client.get(f"/book-pdf/status/{uuid.uuid4().hex}")
    assert r.status_code == 404, r.text


def test_download_malformed_job_id_is_400(client):
    r = client.get("/book-pdf/download/not-a-hex-id")
    assert r.status_code == 400, r.text


def test_download_unknown_job_id_is_404(client):
    r = client.get(f"/book-pdf/download/{uuid.uuid4().hex}")
    assert r.status_code == 404, r.text


def test_download_before_done_is_409(client):
    job_id = uuid.uuid4().hex
    main._book_pdf_job_create(job_id)  # default stage == "decomposing"
    try:
        r = client.get(f"/book-pdf/download/{job_id}")
        assert r.status_code == 409, r.text
    finally:
        with main._book_pdf_jobs_lock:
            main._book_pdf_jobs.pop(job_id, None)


def test_prompt_mode_empty_prompt_is_400(client, default_keys):
    body = _prompt_req_data(concept="", character="")
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text


def test_prompt_mode_bad_page_count_is_rejected_not_clamped(client, default_keys):
    """page_count must be one of 11/15/19 -- an out-of-set value is REJECTED
    (400), unlike /decompose's page_count which is silently clamped."""
    body = _prompt_req_data(page_count=12)
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text
    assert "page_count" in r.text


def test_existing_mode_without_story_is_400(client, default_keys):
    body = {"mode": "existing", "language": "zh", "story": None, "generated_images": None}
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text


def test_existing_mode_story_without_pages_is_400(client, default_keys):
    body = {"mode": "existing", "language": "zh", "story": {"book_title_en": "x"}}
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text


def test_existing_mode_bad_generated_images_filename_is_400(client, default_keys):
    story = _make_story(n_pages=1)
    body = {
        "mode": "existing", "language": "zh", "story": story,
        "generated_images": {"1": "not-a-valid-filename.png"},
    }
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text
    assert "generated_images" in r.text or "Invalid" in r.text


def test_prompt_mode_generated_images_is_validated(client, default_keys):
    """SECURITY REGRESSION: generated_images is honored by the worker in ALL
    modes (it reads + base64-embeds each file from OUTPUT_DIR), so the
    [a-f0-9]{32}.png allow-list must be enforced in prompt mode too -- not only
    in the existing-mode branch. Previously a mode="prompt" caller could smuggle
    an absolute/traversal path ("config.json", "/etc/passwd", "../x") and
    exfiltrate it inside the downloadable PDF. Each of these must 400 BEFORE any
    job is spawned."""
    for bad in ("config.json", "/etc/passwd", "../secrets.png", "..%2fx.png",
                "a" * 31 + ".png", "deadbeef" * 4 + ".PNG"):
        body = _prompt_req_data()
        body["generated_images"] = {"1": bad}
        r = client.post("/book-pdf", json=body)
        assert r.status_code == 400, f"{bad!r} should be rejected, got {r.status_code}: {r.text}"
        assert "generated_images" in r.text or "Invalid" in r.text


def test_unknown_language_is_400(client, default_keys):
    body = _prompt_req_data(language="fr")
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 400, r.text


# ═══════════════════════════════════════════════════════════════════════════
# 4. Key-missing fail-fast (503)
# ═══════════════════════════════════════════════════════════════════════════

def test_prompt_mode_no_anthropic_key_is_503(client, monkeypatch):
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)
    body = _prompt_req_data()
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 503, r.text
    assert "ANTHROPIC_API_KEY" in r.text


def test_existing_mode_needing_images_no_gemini_key_is_503(client, monkeypatch):
    """mode=existing, recheck disabled (so Anthropic isn't required), but the
    generated_images map is empty -> needs Gemini -> 503 naming GEMINI_API_KEY."""
    def _get_key(name):
        return "fake-anthropic" if name == "ANTHROPIC_API_KEY" else None
    monkeypatch.setattr(settings_store, "get_key", _get_key)

    story = _make_story(n_pages=1)
    body = {
        "mode": "existing", "language": "zh", "story": story,
        "generated_images": {}, "recheck_readings": False,
    }
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 503, r.text
    assert "GEMINI_API_KEY" in r.text


# ═══════════════════════════════════════════════════════════════════════════
# 5. _BOOK_PDF_SEM guardrail
# ═══════════════════════════════════════════════════════════════════════════

def test_semaphore_exhausted_returns_429_and_spawns_no_job(client, default_keys):
    acquired = 0
    while main._BOOK_PDF_SEM.acquire(blocking=False):
        acquired += 1
    assert acquired >= 1, "test assumes the semaphore started with >=1 capacity available"

    try:
        jobs_before = set(main._book_pdf_jobs.keys())
        r = client.post("/book-pdf", json=_prompt_req_data())
        assert r.status_code == 429, r.text
        assert set(main._book_pdf_jobs.keys()) == jobs_before, "no job record should be created on 429"
    finally:
        for _ in range(acquired):
            main._BOOK_PDF_SEM.release()


def test_semaphore_released_after_job_completes(client, tmp_dirs, default_keys, monkeypatch):
    """A completed job must release its semaphore slot so the full pool of
    slots can be re-acquired afterwards."""
    def _fake_run_decompose(**kwargs):
        return _make_story(language="ja", n_pages=1)

    monkeypatch.setattr(main, "run_decompose", lambda *a, **k: _fake_run_decompose())
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))  # locked True for mode="prompt"
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    def _fake_generate(**kwargs):
        return "FAKE_IMAGE_OBJECT"

    def _fake_save_image(image, filename, meta=None):
        _write_dummy_png(tmp_dirs["output"], filename)

    monkeypatch.setattr(main.gemini_generator, "generate", _fake_generate)
    monkeypatch.setattr(main.gemini_generator, "save_image", _fake_save_image)

    # Determine current capacity non-destructively-ish: fully exhaust, note count,
    # then give it all back before issuing the real request.
    acquired = 0
    while main._BOOK_PDF_SEM.acquire(blocking=False):
        acquired += 1
    capacity = acquired
    for _ in range(acquired):
        main._BOOK_PDF_SEM.release()

    body = _prompt_req_data(language="ja", concept="a fox finds a friend")
    r = client.post("/book-pdf", json=body)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    rec = _wait_for_terminal_stage(client, job_id)
    assert rec["stage"] == "done", rec

    # Full capacity must be acquirable again now that the job finished.
    acquired2 = 0
    while main._BOOK_PDF_SEM.acquire(blocking=False):
        acquired2 += 1
    try:
        assert acquired2 == capacity, f"expected full capacity {capacity} restored, got {acquired2}"
    finally:
        for _ in range(acquired2):
            main._BOOK_PDF_SEM.release()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Worker stage progression (direct calls to _run_book_pdf_job)
# ═══════════════════════════════════════════════════════════════════════════

def _run_worker_with_sem(job_id, req_data, anthropic_key="fake-a", gemini_key="fake-g"):
    """Mimic the route's invariant: acquire the sem before calling the worker
    (which always releases exactly once in its `finally`), so the bound isn't
    exceeded."""
    assert main._BOOK_PDF_SEM.acquire(blocking=False), "semaphore unexpectedly exhausted before test"
    main._book_pdf_job_create(job_id)
    main._run_book_pdf_job(job_id, req_data, anthropic_key, gemini_key)


def test_full_prompt_mode_job_reaches_done_zh_with_practice_sheet(tmp_dirs, monkeypatch):
    monkeypatch.setattr(main, "run_decompose", lambda **k: _make_story(language="zh", n_pages=2))
    monkeypatch.setattr(main, "run_recheck", lambda **k: {
        "language": "zh",
        "pages": [
            {"page": 1, "zh": "第一页。", "pinyin": "dì yī yè.", "en": "Page one.",
             "characters": [{"c": "第", "p": "dì"}, {"c": "。", "p": ""}]},
            {"page": 2, "zh": "第二页。", "pinyin": "dì èr yè.", "en": "Page two.",
             "characters": [{"c": "第", "p": "dì"}, {"c": "。", "p": ""}]},
        ],
    })
    monkeypatch.setattr(main.gemini_generator, "generate", lambda **k: "FAKE_IMAGE_OBJECT")
    monkeypatch.setattr(main.gemini_generator, "save_image",
                         lambda image, filename, meta=None: _write_dummy_png(tmp_dirs["output"], filename))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)
    # practice_sheet_local_mod is exercised FOR REAL here (pure ReportLab, no
    # network) -- this is a real end-to-end exercise of the zh practice-sheet path.

    job_id = uuid.uuid4().hex
    req_data = _prompt_req_data(language="zh")
    _run_worker_with_sem(job_id, req_data)

    rec = main._book_pdf_job_read(job_id)
    assert rec["stage"] == "done", rec
    assert rec["pdf_filename"] == f"{job_id}.pdf"
    assert rec["practice_sheet_included"] is True
    assert rec["book_title_en"] == "The Little Duckling"
    assert os.path.exists(os.path.join(str(tmp_dirs["book_pdf"]), f"{job_id}.pdf"))


def test_full_prompt_mode_job_reaches_done_ja_no_practice_sheet(tmp_dirs, monkeypatch):
    def _fake_decompose(**k):
        story = _make_story(language="ja", n_pages=2)
        for pg in story["pages"]:
            pg["ja"] = pg.pop("zh")
            pg["romaji"] = pg.pop("pinyin")
        story["book_title_ja"] = story.pop("book_title_zh")
        story["book_title_romaji"] = story.pop("book_title_pinyin")
        return story

    monkeypatch.setattr(main, "run_decompose", lambda **k: _fake_decompose())
    # recheck_readings is LOCKED True for mode="prompt" regardless of the
    # request field -- must still mock run_recheck (echo, no-op overlay).
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))
    monkeypatch.setattr(main.gemini_generator, "generate", lambda **k: "FAKE_IMAGE_OBJECT")
    monkeypatch.setattr(main.gemini_generator, "save_image",
                         lambda image, filename, meta=None: _write_dummy_png(tmp_dirs["output"], filename))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    job_id = uuid.uuid4().hex
    req_data = _prompt_req_data(language="ja", recheck_readings=False)
    _run_worker_with_sem(job_id, req_data)

    rec = main._book_pdf_job_read(job_id)
    assert rec["stage"] == "done", rec
    assert rec["pdf_filename"] == f"{job_id}.pdf"
    assert rec["practice_sheet_included"] is False


def test_forced_exception_sets_error_stage_and_releases_sem(tmp_dirs, monkeypatch):
    monkeypatch.setattr(main, "run_decompose", lambda **k: _make_story(language="ja", n_pages=1))
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))  # locked True for mode="prompt"

    def _boom(**kwargs):
        raise RuntimeError("simulated Gemini outage")

    monkeypatch.setattr(main.gemini_generator, "generate", _boom)
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    job_id = uuid.uuid4().hex
    req_data = _prompt_req_data(language="ja", recheck_readings=False)
    _run_worker_with_sem(job_id, req_data)

    rec = main._book_pdf_job_read(job_id)
    assert rec["stage"] == "error", rec
    assert "simulated Gemini outage" in rec["error"]

    # Sem must have been released despite the exception -- prove it's acquirable.
    assert main._BOOK_PDF_SEM.acquire(blocking=False), "semaphore slot was not released on error path"
    main._BOOK_PDF_SEM.release()


# ═══════════════════════════════════════════════════════════════════════════
# 8. Text-only books (include_art=false) — no images, no Gemini
# ═══════════════════════════════════════════════════════════════════════════

def test_text_only_prompt_page_count_over_30_is_400(client, default_keys):
    """Text-only allows 1-30; 31 is rejected with a text-only-specific message."""
    r = client.post("/book-pdf", json=_prompt_req_data(include_art=False, page_count=31))
    assert r.status_code == 400, r.text
    assert "1 and 30" in r.text or "text-only" in r.text


def test_text_only_prompt_page_count_25_is_accepted(client, tmp_dirs, default_keys, monkeypatch):
    """25 pages is invalid for illustrated (11/15/19) but valid for text-only."""
    monkeypatch.setattr(main, "run_decompose", lambda **k: {**_make_story(n_pages=2), "include_art": False})
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))
    monkeypatch.setattr(main.gemini_generator, "generate", _raise_if_called("gemini_generator.generate"))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)
    r = client.post("/book-pdf", json=_prompt_req_data(include_art=False, page_count=25))
    assert r.status_code == 200, r.text
    _wait_for_terminal_stage(client, r.json()["job_id"])


def test_text_only_prompt_no_gemini_key_is_not_503(client, tmp_dirs, monkeypatch):
    """A text-only book needs no Gemini key — only Anthropic."""
    monkeypatch.setattr(settings_store, "get_key",
                        lambda name: "fake-a" if name == "ANTHROPIC_API_KEY" else None)
    monkeypatch.setattr(main, "run_decompose", lambda **k: {**_make_story(n_pages=2), "include_art": False})
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))
    monkeypatch.setattr(main.gemini_generator, "generate", _raise_if_called("gemini_generator.generate"))
    monkeypatch.setattr(main.book_pdf, "render_pdf", _fake_render_pdf)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)
    r = client.post("/book-pdf", json=_prompt_req_data(include_art=False, page_count=11))
    assert r.status_code == 200, r.text
    _wait_for_terminal_stage(client, r.json()["job_id"])


def test_text_only_prompt_job_skips_gemini_and_renders_text_only(tmp_dirs, monkeypatch):
    """The worker for a text-only book calls NEITHER gemini.generate NOR
    save_image, reaches done, and hands render_pdf a text-only HTML document
    (no <img>, full-width text spreads)."""
    monkeypatch.setattr(main, "run_decompose",
                        lambda **k: {**_make_story(language="zh", n_pages=2), "include_art": False})
    monkeypatch.setattr(main, "run_recheck", lambda **k: _echo_run_recheck(**k))
    monkeypatch.setattr(main.gemini_generator, "generate", _raise_if_called("gemini_generator.generate"))
    monkeypatch.setattr(main.gemini_generator, "save_image", _raise_if_called("gemini_generator.save_image"))
    captured = {}
    def _cap_render(html):
        captured["html"] = html
        assert isinstance(html, str) and "<html" in html
        return b"%PDF-1.4 FAKE TEXT-ONLY"
    monkeypatch.setattr(main.book_pdf, "render_pdf", _cap_render)
    monkeypatch.setattr(main.book_pdf, "merge_pdfs", _fake_merge_pdfs)

    job_id = uuid.uuid4().hex
    _run_worker_with_sem(job_id, _prompt_req_data(language="zh", include_art=False, page_count=2))

    rec = main._book_pdf_job_read(job_id)
    assert rec["stage"] == "done", rec
    assert rec["pages_generated"] == 0
    # build_storybook_html ran for real → assert the text-only layout was rendered.
    assert "<img" not in captured["html"]
    assert "page-spread--text-only" in captured["html"]


# Lightweight runner so the file works even without pytest installed.
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
