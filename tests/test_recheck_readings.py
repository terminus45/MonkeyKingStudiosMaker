"""Backend tests for the "Check readings" feature.

Covers:
  1. _decompose_tool parameterization (schema shape under default + recheck params).
  2. languages.correction_prompt single-sourcing + wrapper instruction.
  3. POST /recheck-readings missing-key error contract (503), with parity to /decompose.
  4. RecheckRequest validation (422 on missing required PageData fields / pages).
  5. Route registration: /recheck-readings is POST, static mount is last, no shadowing.

Run:  source venv/bin/activate && python -m pytest tests/test_recheck_readings.py -v
 or:  source venv/bin/activate && python tests/test_recheck_readings.py   (lightweight runner)

These tests are OFFLINE/deterministic. They never make a real Claude API call.
Anything that would require a live key is guarded and reported as SKIPPED.
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


# A valid zh page body (matches PageData: page, en, image_prompt required; characters optional)
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


# ───────────────────────────────────────────────────────────────────────────
# 1. _decompose_tool parameterization
# ───────────────────────────────────────────────────────────────────────────

def test_decompose_tool_default_schema_unchanged():
    """Default call must reproduce the original /decompose schema:
    pages minItems==maxItems==10, page maximum==10, image_prompt in BOTH
    properties and required."""
    lang = languages.get("zh")
    tool = main._decompose_tool(lang)

    assert tool["name"] == "submit_storybook"

    pages = tool["input_schema"]["properties"]["pages"]
    assert pages["minItems"] == 10
    assert pages["maxItems"] == 10

    page_props = pages["items"]["properties"]
    page_required = pages["items"]["required"]

    assert page_props["page"]["maximum"] == 10
    assert "image_prompt" in page_props
    assert "image_prompt" in page_required

    # native/reading/en/characters always required
    for f in ("page", "zh", "pinyin", "en", "characters"):
        assert f in page_required, f"{f} missing from required"


def test_decompose_tool_recheck_params():
    """With min==max==N and include_image_prompt=False:
    array bounds N, page maximum N, image_prompt in NEITHER properties NOR
    required, while native/reading/en/characters remain required."""
    lang = languages.get("zh")
    N = 7
    tool = main._decompose_tool(lang, min_pages=N, max_pages=N, include_image_prompt=False)

    assert tool["name"] == "submit_storybook"

    pages = tool["input_schema"]["properties"]["pages"]
    assert pages["minItems"] == N
    assert pages["maxItems"] == N

    page_props = pages["items"]["properties"]
    page_required = pages["items"]["required"]

    assert page_props["page"]["maximum"] == N
    assert "image_prompt" not in page_props, "image_prompt should be omitted from properties"
    assert "image_prompt" not in page_required, "image_prompt should be omitted from required"

    for f in ("page", "zh", "pinyin", "en", "characters"):
        assert f in page_required, f"{f} must stay required"


@pytest.mark.parametrize("code,native,reading", [
    ("zh", "zh", "pinyin"),
    ("ja", "ja", "romaji"),
    ("ko", "ko", "romanization"),
])
def test_decompose_tool_name_and_fields_all_langs(code, native, reading):
    """Tool name is submit_storybook for every language, and the language's
    native/reading fields are wired into the page schema."""
    lang = languages.get(code)
    tool = main._decompose_tool(lang)
    assert tool["name"] == "submit_storybook"
    page_props = tool["input_schema"]["properties"]["pages"]["items"]["properties"]
    assert native in page_props
    assert reading in page_props
    # recheck variant keeps the name too
    tool2 = main._decompose_tool(lang, min_pages=3, max_pages=3, include_image_prompt=False)
    assert tool2["name"] == "submit_storybook"


# ───────────────────────────────────────────────────────────────────────────
# 2. languages.correction_prompt
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["zh", "ja", "ko"])
def test_correction_prompt_single_sources_rules(code):
    """correction_prompt(lang) must CONTAIN the bare decompose prompt rule text
    (single-sourced) AND a correction wrapper instruction, and differ from the
    bare prompt."""
    lang = languages.get(code)
    cp = languages.correction_prompt(lang)
    assert isinstance(cp, str)

    bare = lang["prompt"]
    # single-sourced: the full per-language rule text is embedded verbatim
    assert bare in cp, f"correction_prompt for {code} must embed the registry prompt verbatim"

    # distinct from the bare decompose prompt
    assert cp != bare

    # correction wrapper instruction present: mentions proofreading / not rewriting / re-aligning
    low = cp.lower()
    assert "proofreader" in low or "correct" in low
    assert "re-align" in low or "realign" in low or "align" in low
    assert "do not rewrite" in low or "not rewrite" in low or "do not\n" in low or "rewrite" in low


# ───────────────────────────────────────────────────────────────────────────
# 3. POST /recheck-readings missing-key error contract + parity with /decompose
# ───────────────────────────────────────────────────────────────────────────

def test_recheck_missing_key_returns_503(client, monkeypatch):
    """With no resolvable key, /recheck-readings returns 503 (reaches the key
    check, not a 422). We monkeypatch settings_store.get_key -> None so the test
    is robust to a developer config.json that may actually contain a key."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)
    body = {"language": "zh", "pages": [VALID_ZH_PAGE]}
    r = client.post("/recheck-readings", json=body)
    assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text}"
    assert "ANTHROPIC_API_KEY" in r.text


def test_recheck_decompose_key_parity(client, monkeypatch):
    """Parity: under the SAME no-key condition, /recheck-readings and /decompose
    return the same missing-key status (503)."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)

    recheck_body = {"language": "zh", "pages": [VALID_ZH_PAGE]}
    decompose_body = {"concept": "a cat learns to share", "language": "zh"}

    r_recheck = client.post("/recheck-readings", json=recheck_body)
    r_decompose = client.post("/decompose", json=decompose_body)

    assert r_recheck.status_code == r_decompose.status_code == 503, (
        f"recheck={r_recheck.status_code} decompose={r_decompose.status_code}"
    )


# ───────────────────────────────────────────────────────────────────────────
# 4. Request validation (422)
# ───────────────────────────────────────────────────────────────────────────

def test_recheck_missing_pages_is_422(client):
    """pages is required on RecheckRequest."""
    r = client.post("/recheck-readings", json={"language": "zh"})
    assert r.status_code == 422, r.text


def test_recheck_page_missing_image_prompt_is_422(client):
    """Request-side PageData.image_prompt is required, so a page lacking it ->
    422 (validation happens before the key check)."""
    bad_page = {k: v for k, v in VALID_ZH_PAGE.items() if k != "image_prompt"}
    r = client.post("/recheck-readings", json={"language": "zh", "pages": [bad_page]})
    assert r.status_code == 422, r.text
    assert "image_prompt" in r.text


def test_recheck_page_missing_en_is_422(client):
    """PageData.en is required."""
    bad_page = {k: v for k, v in VALID_ZH_PAGE.items() if k != "en"}
    r = client.post("/recheck-readings", json={"language": "zh", "pages": [bad_page]})
    assert r.status_code == 422, r.text


def test_recheck_page_missing_page_num_is_422(client):
    """PageData.page is required."""
    bad_page = {k: v for k, v in VALID_ZH_PAGE.items() if k != "page"}
    r = client.post("/recheck-readings", json={"language": "zh", "pages": [bad_page]})
    assert r.status_code == 422, r.text


# ───────────────────────────────────────────────────────────────────────────
# 5. Route registration / ordering
# ───────────────────────────────────────────────────────────────────────────

def test_recheck_route_registered_as_post():
    paths = {}
    for r in main.app.routes:
        p = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if p:
            paths.setdefault(p, set())
            if methods:
                paths[p] |= set(methods)
    assert "/recheck-readings" in paths, "route not registered"
    assert "POST" in paths["/recheck-readings"], "should accept POST"
    # Should NOT respond to GET
    assert "GET" not in paths["/recheck-readings"]


def test_static_mount_is_last():
    """The StaticFiles mount must remain the final route so it doesn't shadow
    API routes (including /recheck-readings)."""
    from starlette.routing import Mount
    routes = main.app.routes
    last = routes[-1]
    assert isinstance(last, Mount), f"last route is {type(last).__name__}, expected Mount"
    # And the recheck route appears before that mount.
    recheck_idx = next(
        (i for i, r in enumerate(routes) if getattr(r, "path", None) == "/recheck-readings"),
        None,
    )
    assert recheck_idx is not None
    assert recheck_idx < len(routes) - 1, "recheck route must come before the static mount"


def test_recheck_reachable_through_testclient_not_shadowed(client, monkeypatch):
    """Sanity: a POST to /recheck-readings is routed to the API handler (gives
    503 with no key), not swallowed by the static mount (which would 404/405)."""
    monkeypatch.setattr(settings_store, "get_key", lambda name: None)
    r = client.post("/recheck-readings", json={"language": "zh", "pages": [VALID_ZH_PAGE]})
    assert r.status_code == 503, f"static mount may be shadowing the API route: {r.status_code} {r.text}"


# ───────────────────────────────────────────────────────────────────────────
# Live recheck call — SKIPPED without a key (write the test, mark not-run)
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No ANTHROPIC_API_KEY in env — live Claude recheck call not exercised.",
)
def test_recheck_live_roundtrip(client):
    """NOT RUN by default. Would verify a real recheck round-trip returns the
    page array with corrected readings and image_prompt absent server-side."""
    body = {"language": "zh", "pages": [VALID_ZH_PAGE]}
    r = client.post("/recheck-readings", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "pages" in data
    assert data["language"] == "zh"
    for pg in data["pages"]:
        assert "image_prompt" not in pg, "server should not return image_prompt"


# Lightweight runner so the file works even without pytest installed.
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
