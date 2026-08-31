"""Refine-compatibility table: generation, ranking, overrides, persistence.

Offline — model files are sparse fakes; no torch, no pipelines.
"""
import json
import os

import pytest

local_generator = pytest.importorskip("local_generator")
import refine_compat


def _ckpt(d, name, gb=0.1):
    path = os.path.join(d, name)
    with open(path, "wb") as f:
        f.truncate(int(gb * 1024 ** 3))
    return path


def _sidecar(d, stem, data):
    with open(os.path.join(d, stem + ".json"), "w") as f:
        json.dump(data, f)


@pytest.fixture
def models_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(local_generator, "LOCAL_MODELS_DIR", str(tmp_path))
    return tmp_path


# ── ranking ─────────────────────────────────────────────────────────────────

def test_same_model_first_then_same_family_only(models_dir):
    _ckpt(models_dir, "a_xl.safetensors", gb=6.0)   # sdxl
    _ckpt(models_dir, "b_xl.safetensors", gb=6.0)   # sdxl
    _ckpt(models_dir, "small.safetensors", gb=2.0)  # sd15

    row = refine_compat.candidates("local:a_xl", "sdxl")
    ids = [c["model_id"] for c in row]
    assert ids[0] == "local:a_xl"
    assert row[0]["tier"] == "same-model"
    assert "local:b_xl" in ids
    assert "local:small" not in ids                 # cross-family excluded


def test_kind_only_query_for_cloud_or_legacy_sources(models_dir):
    _ckpt(models_dir, "a_xl.safetensors", gb=6.0)
    _ckpt(models_dir, "small.safetensors", gb=2.0)
    ids = [c["model_id"] for c in refine_compat.candidates(None, "sd15")]
    assert ids == ["local:small"]
    assert refine_compat.candidates(None, None) == []


def test_cache_unsafe_ranks_below_safe_peers(models_dir):
    _ckpt(models_dir, "safe_xl.safetensors", gb=6.0)
    _ckpt(models_dir, "unsafe_xl.safetensors", gb=6.0)
    _sidecar(models_dir, "unsafe_xl", {"cache_unsafe": True})
    _ckpt(models_dir, "src_xl.safetensors", gb=6.0)

    ids = [c["model_id"] for c in refine_compat.candidates("local:src_xl", "sdxl")]
    assert ids.index("local:safe_xl") < ids.index("local:unsafe_xl")


def test_prompt_style_mismatch_demotes(models_dir):
    _ckpt(models_dir, "src_xl.safetensors", gb=6.0)          # natural (default)
    _ckpt(models_dir, "anime_xl.safetensors", gb=6.0)
    _sidecar(models_dir, "anime_xl", {"prompt_style": "tags"})
    _ckpt(models_dir, "plain_xl.safetensors", gb=6.0)        # natural

    ids = [c["model_id"] for c in refine_compat.candidates("local:src_xl", "sdxl")]
    assert ids.index("local:plain_xl") < ids.index("local:anime_xl")


# ── table persistence & regeneration ────────────────────────────────────────

def test_table_is_saved_and_reused(models_dir):
    _ckpt(models_dir, "m_xl.safetensors", gb=6.0)
    t1 = refine_compat.load_table()
    assert os.path.exists(refine_compat.table_path())
    t2 = refine_compat.load_table()
    assert t2["generated_at"] == t1["generated_at"]   # not rebuilt


def test_table_regenerates_when_model_set_changes(models_dir):
    _ckpt(models_dir, "m_xl.safetensors", gb=6.0)
    t1 = refine_compat.load_table()
    _ckpt(models_dir, "new_xl.safetensors", gb=6.0)
    t2 = refine_compat.load_table()
    assert t2["inputs_checksum"] != t1["inputs_checksum"]
    assert "local:new_xl" in t2["models"]


def test_table_regenerates_when_a_sidecar_changes(models_dir):
    _ckpt(models_dir, "m_xl.safetensors", gb=6.0)
    t1 = refine_compat.load_table()
    _sidecar(models_dir, "m_xl", {"label": "renamed"})
    t2 = refine_compat.load_table()
    assert t2["inputs_checksum"] != t1["inputs_checksum"]


def test_overrides_survive_regeneration(models_dir):
    _ckpt(models_dir, "a_xl.safetensors", gb=6.0)
    _ckpt(models_dir, "small.safetensors", gb=2.0)
    refine_compat.load_table()

    # hand-edit the saved table: allow a cross-family pair
    t = json.load(open(refine_compat.table_path()))
    t["overrides"]["allow"].append(["local:a_xl", "local:small"])
    json.dump(t, open(refine_compat.table_path(), "w"))

    # force a regeneration
    _ckpt(models_dir, "later_xl.safetensors", gb=6.0)
    t2 = refine_compat.load_table()
    assert ["local:a_xl", "local:small"] in t2["overrides"]["allow"]

    ids = [c["model_id"] for c in refine_compat.candidates("local:a_xl", "sdxl")]
    assert "local:small" in ids
    tier = next(c["tier"] for c in refine_compat.candidates("local:a_xl", "sdxl")
                if c["model_id"] == "local:small")
    assert tier == "override-allow"


def test_ban_override_removes_a_pair(models_dir):
    _ckpt(models_dir, "a_xl.safetensors", gb=6.0)
    _ckpt(models_dir, "b_xl.safetensors", gb=6.0)
    refine_compat.load_table()
    t = json.load(open(refine_compat.table_path()))
    t["overrides"]["ban"].append(["local:a_xl", "local:b_xl"])
    json.dump(t, open(refine_compat.table_path(), "w"))

    ids = [c["model_id"] for c in refine_compat.candidates("local:a_xl", "sdxl")]
    assert "local:b_xl" not in ids
    # the ban is directional: b can still refine with a
    assert "local:a_xl" in [c["model_id"] for c in refine_compat.candidates("local:b_xl", "sdxl")]


# ── source-kind derivation ──────────────────────────────────────────────────

def test_kind_prefers_metadata_then_dimensions(models_dir, tmp_path):
    from PIL import Image
    assert refine_compat.kind_for_image({"kind": "sdxl"}, "/nope") == "sdxl"

    big = tmp_path / "big.png"
    Image.new("RGB", (896, 1152)).save(big)
    assert refine_compat.kind_for_image({}, str(big)) == "sdxl"

    small = tmp_path / "small.png"
    Image.new("RGB", (448, 576)).save(small)
    assert refine_compat.kind_for_image({}, str(small)) == "sd15"


def test_krea2_is_inventoried_but_never_a_refine_candidate(models_dir):
    """Until diffusers ships a Krea 2 img2img pipeline, krea2 images have no
    refine options and krea2 models refine nothing."""
    d = models_dir / "krea2-turbo"
    d.mkdir()
    (d / "model_index.json").write_text(json.dumps({"_class_name": "Krea2Pipeline"}))
    _ckpt(models_dir, "a_xl.safetensors", gb=6.0)

    table = refine_compat.load_table()
    assert table["models"]["local:krea2-turbo"]["kind"] == "krea2"
    # krea2 source -> nothing
    assert refine_compat.candidates("local:krea2-turbo", "krea2") == []
    assert refine_compat.candidates(None, "krea2") == []
    # sdxl source -> krea2 never appears
    ids = [c["model_id"] for c in refine_compat.candidates("local:a_xl", "sdxl")]
    assert "local:krea2-turbo" not in ids
