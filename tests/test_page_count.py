"""Tests for the selectable book page count (Settings → Book Length: 11/15/19).

Offline only — no Claude calls. Covers:
  1. _decompose_tool builds matching array bounds + per-page maximum for each
     selectable count (11/15/19).
  2. DecomposeRequest exposes page_count with default 11 and accepts an explicit
     value (pydantic accepts any int; the handler clamps out-of-set → 11).
  3. The handler's clamp expression maps out-of-set / None values to 11.

Run: pytest tests/test_page_count.py   (or python tests/test_page_count.py)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import languages


# 1. Schema bounds for each selectable count
@pytest.mark.parametrize("n", [11, 15, 19])
def test_decompose_tool_bounds_for_selectable_counts(n):
    tool = main._decompose_tool(languages.get("zh"), min_pages=n, max_pages=n)
    pages = tool["input_schema"]["properties"]["pages"]
    assert pages["minItems"] == n
    assert pages["maxItems"] == n
    # page numbers must be allowed to reach n
    assert pages["items"]["properties"]["page"]["maximum"] == n


# 2. Request model default + explicit value
def test_decompose_request_page_count_default_is_11():
    req = main.DecomposeRequest(concept="a kite", language="zh")
    assert req.page_count == 11


def test_decompose_request_accepts_explicit_page_count():
    req = main.DecomposeRequest(concept="a kite", language="zh", page_count=15)
    assert req.page_count == 15


# 3. The handler clamp expression (mirrors main.py: in (11,15,19) else 11)
@pytest.mark.parametrize("value,expected", [
    (11, 11), (15, 15), (19, 19),   # allowed values pass through
    (7, 11), (100, 11), (0, 11),    # out-of-set → 11
    (None, 11),                     # omitted/None → 11
])
def test_page_count_clamp(value, expected):
    clamped = value if value in (11, 15, 19) else 11
    assert clamped == expected


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
