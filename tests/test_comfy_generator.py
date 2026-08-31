"""ComfyUI backend: discovery gating, graph construction, dispatcher routing.

Offline — Comfy's HTTP API is stubbed. The live path is verified against a
real ComfyUI, which these tests could only fake.
"""
import pytest

import comfy_generator as cg
import image_backends as ib


@pytest.fixture(autouse=True)
def fresh_probe():
    cg._probe_cache.update(at=0.0, url=None)
    yield
    cg._probe_cache.update(at=0.0, url=None)


def _stub_api(monkeypatch, up=True, files=None):
    files = files if files is not None else {
        "diffusion_models": ["krea2_turbo_fp8_scaled.safetensors"],
        "text_encoders": ["qwen3vl_4b_fp8_scaled.safetensors"],
        "vae": ["qwen_image_vae.safetensors"],
    }

    def fake_get(url, timeout=5.0):
        if not up:
            raise OSError("connection refused")
        if url.endswith("/system_stats"):
            return {"system": {}}
        for kind, listing in files.items():
            if url.endswith(f"/models/{kind}"):
                return listing
        return []

    monkeypatch.setattr(cg, "_get", fake_get)


# ── discovery gating ────────────────────────────────────────────────────────

def test_not_offered_when_comfy_is_down(monkeypatch):
    _stub_api(monkeypatch, up=False)
    assert cg.discover_models() == []
    ok, reason = cg.available()
    assert ok is False and "not running" in reason


def test_not_offered_when_files_missing(monkeypatch):
    _stub_api(monkeypatch, files={"diffusion_models": [],
                                  "text_encoders": [], "vae": []})
    assert cg.discover_models() == []
    ok, reason = cg.available()
    assert ok is False and "missing model files" in reason


def test_offered_when_up_and_complete(monkeypatch):
    _stub_api(monkeypatch)
    models = cg.discover_models()
    assert [m["id"] for m in models] == ["comfy:krea2-turbo"]
    assert models[0]["type"] == "krea2"


def test_prefers_fp8_over_int8(monkeypatch):
    """int8's aten::_int_mm has no MPS kernels — verified live; fp8 wins."""
    _stub_api(monkeypatch, files={
        "diffusion_models": [
            "krea2TurboOfficialComfy_krea2TurboInt8.safetensors",
            "krea2_turbo_fp8_scaled.safetensors"],
        "text_encoders": ["qwen3vl_4b_fp8_scaled.safetensors"],
        "vae": ["qwen_image_vae.safetensors"],
    })
    assert cg._dit_file("http://x") == "krea2_turbo_fp8_scaled.safetensors"


def test_int8_alone_still_offers(monkeypatch):
    _stub_api(monkeypatch, files={
        "diffusion_models": ["krea2TurboOfficialComfy_krea2TurboInt8.safetensors"],
        "text_encoders": ["qwen3vl_4b_fp8_scaled.safetensors"],
        "vae": ["qwen_image_vae.safetensors"],
    })
    assert cg.discover_models() != []


# ── graph construction ──────────────────────────────────────────────────────

def test_graph_mirrors_the_official_template():
    g = cg._build_graph("a hero", seed=7, steps=8, cfg=1.0,
                        width=896, height=1152, dit_file="dit.safetensors")
    assert g["c"]["inputs"]["type"] == "krea2"
    k = g["k"]["inputs"]
    assert (k["seed"], k["steps"], k["cfg"]) == (7, 8, 1.0)
    assert (k["sampler_name"], k["scheduler"]) == ("euler", "simple")
    assert g["tn"]["class_type"] == "ConditioningZeroOut"
    assert g["l"]["inputs"] == {"width": 896, "height": 1152, "batch_size": 1}
    assert g["u"]["inputs"]["unet_name"] == "dit.safetensors"


# ── dispatcher integration ──────────────────────────────────────────────────

def test_registry_tags_comfy_backend(monkeypatch):
    _stub_api(monkeypatch)
    entry = next((m for m in ib.list_models() if m["id"] == cg.KREA2_ID), None)
    assert entry and entry["backend"] == "comfy"
    assert ib.backend_for(cg.KREA2_ID) == "comfy"


def test_unreachable_comfy_never_breaks_the_registry(monkeypatch):
    monkeypatch.setattr(cg, "discover_models",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    models = ib.list_models()
    assert any(m["backend"] == "gemini" for m in models)


def test_dispatcher_routes_and_finalizes(monkeypatch):
    _stub_api(monkeypatch)
    from PIL import Image as PILImage
    monkeypatch.setattr(cg, "generate", lambda **kw: (
        PILImage.new("RGB", (8, 8), (90, 90, 90)),
        {"backend": "comfy", "kind": "krea2", "seed": kw.get("seed"),
         "reproducible": True}))
    res = ib.generate(content_prompt="x", model_id=cg.KREA2_ID, seed=11)
    assert res.seed == 11
    assert res.meta["backend"] == "comfy"
    assert "created_at" in res.meta and "versions" in res.meta
