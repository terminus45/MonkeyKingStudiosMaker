"""Upscaler: tiling math, pass plans, recipe-driven model choice, gating.

Offline — no torch/spandrel needed; the model-running path is exercised by
the live U1 smoke run, which these tests could only fake.
"""
import numpy as np
import pytest

import upscaler as up


# ── tiling math ─────────────────────────────────────────────────────────────

def test_tiles_cover_without_slivers():
    for length in (512, 513, 896, 1152, 2304, 4608):
        spans = up._tiles(length)
        assert spans[0][0] == 0 and spans[-1][1] == length
        # Full coverage, every tile full-size (or the whole image when small)
        covered = np.zeros(length, bool)
        for s, e in spans:
            assert e - s == min(up.TILE, length)
            covered[s:e] = True
        assert covered.all()


def test_small_image_is_one_tile():
    assert up._tiles(300) == [(0, 300)]


def test_feather_mask_never_zero_and_flat_in_center():
    m = up._feather_mask(512, 512, 1)
    assert m.min() > 0
    assert m[256, 256, 0] == 1.0


# ── pass plans ──────────────────────────────────────────────────────────────

def test_plans_reach_exact_factor():
    # net scale of each plan with a 4x model
    for factor, plan in ((2, ["sr", "half"]), (4, ["sr"]), (8, ["sr", "half", "sr"])):
        assert up._plan(factor) == plan
        net = 1.0
        for op in plan:
            net = net * 4 if op == "sr" else net / 2
        assert net == factor


def test_count_tiles_accounts_for_growth():
    # 896x1152, 4x: one pass, 2x3=6 tiles (spans of 896 -> 2, 1152 -> 3)
    assert up._count_tiles(896, 1152, up._plan(4), 4) == 6
    # 8x adds a second pass over the halved intermediate (1792x2304 -> 4x5)
    assert up._count_tiles(896, 1152, up._plan(8), 4) == 6 + 20


# ── recipe-driven model choice ──────────────────────────────────────────────

@pytest.fixture
def both_models(monkeypatch):
    monkeypatch.setattr(up, "discover_models", lambda: [
        {"key": "general", "file": "g.pth"}, {"key": "anime", "file": "a.pth"}])


def test_no_meta_defaults_to_general(both_models):
    assert up.choose_model(None) == ("general", "default")
    assert up.choose_model({}) == ("general", "default")


def test_anime_checkpoint_name_heuristic(both_models):
    meta = {"backend": "local", "kind": "sdxl",
            "model_file": {"name": "animagineXL_v40.safetensors"}}
    assert up.choose_model(meta) == ("anime", "heuristic")


def test_photoreal_and_cloud_get_general(both_models):
    for meta in (
        {"backend": "local", "model_file": {"name": "juggernautXL_v9.safetensors"}},
        {"backend": "gemini", "model_id": "imagen-4.0-generate-001"},
        {"backend": "comfy", "kind": "krea2",
         "model_file": {"name": "krea2_turbo_bf16.safetensors"}},
    ):
        assert up.choose_model(meta) == ("general", "default")


def test_sidecar_outranks_heuristic(both_models, monkeypatch):
    import local_generator
    monkeypatch.setattr(local_generator, "_model_settings",
                        lambda mid: {"upscaler": "general"})
    meta = {"backend": "local", "model_file": {"name": "animagineXL_v40.safetensors"}}
    assert up.choose_model(meta) == ("general", "sidecar")


def test_missing_model_falls_back_to_what_exists(monkeypatch):
    monkeypatch.setattr(up, "discover_models",
                        lambda: [{"key": "general", "file": "g.pth"}])
    meta = {"backend": "local", "model_file": {"name": "animagineXL_v40.safetensors"}}
    key, why = up.choose_model(meta)
    assert key == "general"


def test_no_models_raises(monkeypatch):
    monkeypatch.setattr(up, "discover_models", lambda: [])
    with pytest.raises(RuntimeError):
        up.choose_model(None)


# ── suggested factor & ceilings ─────────────────────────────────────────────

def test_suggested_factor_targets_print():
    assert up.suggested_factor(512, 512) == 8       # 512*4 < 3300
    assert up.suggested_factor(896, 1152) == 4      # 1152*4 = 4608
    assert up.suggested_factor(1792, 2304) == 2     # 2304*2 = 4608
    assert up.suggested_factor(400, 400) == 8       # nothing reaches: max


def test_output_ceiling_enforced():
    from PIL import Image
    big = Image.new("RGB", (4000, 4000))
    with pytest.raises(ValueError, match="ceiling"):
        up.upscale(big, 8, "general")


def test_sidecar_upscaler_key_validated():
    import local_generator
    v = local_generator._SIDECAR_KEYS["upscaler"]
    assert v("anime") == "anime" and v("general") == "general"
    assert v("Anime") is None and v(3) is None
