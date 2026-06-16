"""Backend tests for the "per-character ruby cover title" feature.

Covers the just-implemented book-title-characters additions:
  1. _decompose_tool schema: top-level `book_title_characters` property exists,
     its item schema EQUALS the page `characters` item schema, and it is NOT in
     the top-level `required` list. Verified for zh/ja/ko and for both
     include_image_prompt=True/False.
  2. DecomposeResponse accepts a payload WITH and WITHOUT `book_title_characters`
     (the field is Optional).
  3. RecheckRequest accepts the three new optional title keys, and also validates
     when they are omitted.
  4. POST /recheck-readings still returns 503 with no key when the body INCLUDES
     the title fields — i.e. the new fields don't break the path before the key
     check. Uses the same monkeypatch/parity technique as test_recheck_readings.py
     so a developer config.json key doesn't break determinism.

Run:  source venv/bin/activate && python -m pytest tests/test_cover_title_characters.py -v
 or:  source venv/bin/activate && python tests/test_cover_title_characters.py

These tests are OFFLINE/deterministic. They never make a real Claude API call.
"""
import os
import sys

# Make project root importable when run from anywhere.
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


# A valid zh page body (matches PageData: page, en, image_prompt required).
VALID_ZH_PAGE = {
    "page": 1,
    "en": "The little cat sleeps.",
    "image_prompt": "a small cat sleeping on a cushion, soft light",
    "zh": "小猫在睡觉。",
    "pinyin": "xiǎo māo zài shuì jiào.",
    "characters": [
        {"c": "小", "p": "xiǎo"},
        {"c": "猫", "p": "māo"},
        {"c": "。", "p": ""},
    ],
}

TITLE_CHARS = [
    {"c": "汉", "p": "hàn"},
    {"c": "字", "p": "zì"},
]


# ───────────────────────────────────────────────────────────────────────────
# 1. _decompose_tool schema: book_title_characters
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["zh", "ja", "ko"])
@pytest.mark.parametrize("include_image_prompt", [True, False])
def test_decompose_tool_has_book_title_characters(code, include_image_prompt):
    """Top-level properties CONTAINS book_title_characters; its item schema EQUALS
    the page characters[] item schema; and it is NOT in top-level required.
    Verified across all languages and both include_image_prompt modes."""
    lang = languages.get(code)
    tool = main._decompose_tool(
        lang, min_pages=5, max_pages=5, include_image_prompt=include_image_prompt
    )

    schema = tool["input_schema"]
    top_props = schema["properties"]
    top_required = schema["required"]

    # Present in top-level properties …
    assert "book_title_characters" in top_props, "book_title_characters missing from top-level properties"
    # … but NOT required (old books / blank titles must still validate).
    assert "book_title_characters" not in top_required, (
        "book_title_characters must NOT be in top-level required"
    )

    btc = top_props["book_title_characters"]
    assert btc["type"] == "array"

    # Item schema must equal the page characters[] item schema exactly.
    page_chars_items = top_props["pages"]["items"]["properties"]["characters"]["items"]
    title_chars_items = btc["items"]

    assert title_chars_items == page_chars_items, (
        f"title char item schema != page char item schema\n"
        f"title={title_chars_items}\npage={page_chars_items}"
    )
    # And the concrete contract the spec calls out: {c,p}, required [c,p], no extras.
    assert set(title_chars_items["properties"]) == {"c", "p"}
    assert sorted(title_chars_items["required"]) == ["c", "p"]
    assert title_chars_items["additionalProperties"] is False


def test_decompose_tool_default_still_has_title_characters():
    """The default /decompose call (min=max=11, include_image_prompt=True) also
    exposes book_title_characters and keeps the original required set intact."""
    lang = languages.get("zh")
    tool = main._decompose_tool(lang)
    schema = tool["input_schema"]

    assert "book_title_characters" in schema["properties"]
    # The four original required keys remain exactly; title chars NOT added.
    assert set(schema["required"]) == {
        "book_title_zh", "book_title_pinyin", "book_title_en", "pages",
    }
    assert "book_title_characters" not in schema["required"]


# ───────────────────────────────────────────────────────────────────────────
# 2. DecomposeResponse — book_title_characters is Optional
# ───────────────────────────────────────────────────────────────────────────

def test_decompose_response_with_title_characters():
    """DecomposeResponse accepts a payload WITH book_title_characters."""
    resp = main.DecomposeResponse(
        book_title_en="Chinese Characters",
        book_title_zh="汉字",
        book_title_pinyin="hàn zì",
        book_title_characters=TITLE_CHARS,
        language="zh",
        pages=[main.PageData(**VALID_ZH_PAGE)],
    )
    assert resp.book_title_characters is not None
    assert len(resp.book_title_characters) == 2
    assert resp.book_title_characters[0].c == "汉"
    assert resp.book_title_characters[0].p == "hàn"


def test_decompose_response_without_title_characters():
    """DecomposeResponse accepts a payload WITHOUT book_title_characters
    (Optional → defaults to None, no validation error)."""
    resp = main.DecomposeResponse(
        book_title_en="Chinese Characters",
        book_title_zh="汉字",
        book_title_pinyin="hàn zì",
        language="zh",
        pages=[main.PageData(**VALID_ZH_PAGE)],
    )
    assert resp.book_title_characters is None


def test_decompose_response_title_characters_items_validated():
    """Each title-char entry is coerced to CharData ({c,p} both required)."""
    with pytest.raises(Exception):
        main.DecomposeResponse(
            book_title_en="x",
            pages=[main.PageData(**VALID_ZH_PAGE)],
            book_title_characters=[{"c": "汉"}],  # missing required 'p'
        )


# ───────────────────────────────────────────────────────────────────────────
# 3. RecheckRequest — new optional title keys
# ───────────────────────────────────────────────────────────────────────────

def test_recheck_request_accepts_title_keys():
    """RecheckRequest validates with all three new title keys provided."""
    req = main.RecheckRequest(
        language="zh",
        pages=[main.PageData(**VALID_ZH_PAGE)],
        book_title_native="汉字",
        book_title_reading="hàn zì",
        book_title_characters=TITLE_CHARS,
    )
    assert req.book_title_native == "汉字"
    assert req.book_title_reading == "hàn zì"
    assert req.book_title_characters[1].c == "字"


def test_recheck_request_title_keys_optional():
    """RecheckRequest validates with the title keys omitted (all default None)."""
    req = main.RecheckRequest(
        language="zh",
        pages=[main.PageData(**VALID_ZH_PAGE)],
    )
    assert req.book_title_native is None
    assert req.book_title_reading is None
    assert req.book_title_characters is None


# ───────────────────────────────────────────────────────────────────────────
# 4. /recheck-readings missing-key contract WITH title fields in the body
# ───────────────────────────────────────────────────────────────────────────

def test_recheck_with_title_fields_missing_key_returns_503(client, monkeypatch):
    """A body INCLUDING the new title fields must still reach the key check and
    return 503 (not a 422) — proving the fields don't break the request path
    before the key check. monkeypatched no-key so a developer config.json key
    can't make this non-deterministic."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)
    body = {
        "language": "zh",
        "pages": [VALID_ZH_PAGE],
        "book_title_native": "汉字",
        "book_title_reading": "hàn zì",
        "book_title_characters": TITLE_CHARS,
    }
    r = client.post("/recheck-readings", json=body)
    assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text}"
    assert "ANTHROPIC_API_KEY" in r.text


def test_recheck_with_title_decompose_key_parity(client, monkeypatch):
    """Parity: under the SAME no-key condition, /recheck-readings (with title
    fields) and /decompose return the same missing-key status (503)."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)

    recheck_body = {
        "language": "zh",
        "pages": [VALID_ZH_PAGE],
        "book_title_native": "汉字",
        "book_title_reading": "hàn zì",
        "book_title_characters": TITLE_CHARS,
    }
    decompose_body = {"concept": "a cat learns to share", "language": "zh"}

    r_recheck = client.post("/recheck-readings", json=recheck_body)
    r_decompose = client.post("/decompose", json=decompose_body)

    assert r_recheck.status_code == r_decompose.status_code == 503, (
        f"recheck={r_recheck.status_code} decompose={r_decompose.status_code}"
    )


def test_recheck_blank_title_still_503_not_422(client, monkeypatch):
    """A blank book_title_native (the B3 'omit title' path) must not change the
    contract: still 503 with no key, never a 422."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)
    body = {
        "language": "zh",
        "pages": [VALID_ZH_PAGE],
        "book_title_native": "   ",
        "book_title_reading": "",
        "book_title_characters": [],
    }
    r = client.post("/recheck-readings", json=body)
    assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text}"


# Lightweight runner so the file works even without the pytest CLI.
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
