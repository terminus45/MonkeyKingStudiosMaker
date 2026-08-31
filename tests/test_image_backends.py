"""Tests for the image-backend dispatcher (Phase 1 of local image generation).

All offline — no network, no API key, no torch. The local backend is
simulated with a stub module so routing can be tested before local_generator
exists.
"""
import sys
import types

import pytest

import config
import gemini_generator
import image_backends as ib


@pytest.fixture(autouse=True)
def no_host_models(monkeypatch, tmp_path):
    """Point local discovery at an empty directory.

    Without this the suite depends on whatever checkpoints happen to sit in
    the developer's ./models — these tests are about routing, not inventory.
    Tests that want a local backend install their own stub.
    """
    try:
        import local_generator
    except ImportError:
        return                                   # not built yet; nothing to isolate
    monkeypatch.setattr(local_generator, "LOCAL_MODELS_DIR", str(tmp_path))


# ── registry ────────────────────────────────────────────────────────────────

def test_lists_cloud_models_tagged_gemini():
    models = ib.list_models()
    assert len(models) == len(gemini_generator.GEMINI_MODELS)
    assert {m["backend"] for m in models} == {"gemini"}
    # the ids the frontend and the book-PDF worker actually send
    ids = {m["id"] for m in models}
    assert "imagen-4.0-fast-generate-001" in ids


def test_backend_for_known_and_unknown():
    assert ib.backend_for("imagen-4.0-fast-generate-001") == "gemini"
    assert ib.backend_for("nope") is None


# ── allow-list (design-specs/local-image-generation.md D3) ──────────────────

@pytest.mark.parametrize("bad", [
    "",
    "nope",
    "../../etc/passwd",
    "/Users/chen/models/evil.ckpt",
    "models/evil.ckpt",
])
def test_generate_rejects_ids_outside_the_allow_list(bad):
    """A model identifier out of an unauthenticated request body must never
    reach a loader as anything but a key resolved server-side."""
    with pytest.raises(ib.UnknownModelError):
        ib.generate(content_prompt="a cat", model_id=bad)


# ── routing ─────────────────────────────────────────────────────────────────

def test_routes_to_gemini_and_forwards_arguments(monkeypatch):
    seen = {}

    def fake_generate(**kwargs):
        seen.update(kwargs)
        return "IMAGE"

    monkeypatch.setattr(gemini_generator, "generate", fake_generate)

    out = ib.generate(
        content_prompt="a monkey king",
        style_prompt="watercolor",
        negative_prompt="blurry",
        model_id="imagen-4.0-fast-generate-001",
        aspect_ratio="3:4",
        width=1024,
        height=768,
        api_key="k",
    )

    assert out.image == "IMAGE"
    assert out.seed is None                      # cloud: no seed, no pretending
    assert out.meta["backend"] == "gemini"
    assert out.meta["reproducible"] is False
    assert out.meta["prompt_final"].startswith("a monkey king, watercolor")
    assert seen["content_prompt"] == "a monkey king"
    assert seen["model_id"] == "imagen-4.0-fast-generate-001"
    assert seen["aspect_ratio"] == "3:4"
    assert seen["api_key"] == "k"
    # on_step and seed are dispatcher-level; the cloud generator gets neither
    assert "on_step" not in seen
    assert "seed" not in seen


def test_cloud_gets_the_safety_suffix(monkeypatch):
    seen = {}
    monkeypatch.setattr(gemini_generator, "generate", lambda **k: seen.update(k) or "IMG")
    ib.generate(content_prompt="a hero", style_prompt="watercolor",
                model_id="imagen-4.0-fast-generate-001")
    assert seen["style_prompt"].startswith("watercolor")
    assert config.SAFETY_STYLE_SUFFIX.strip() in seen["style_prompt"]


def test_safety_suffix_is_not_doubled(monkeypatch):
    seen = {}
    monkeypatch.setattr(gemini_generator, "generate", lambda **k: seen.update(k) or "IMG")
    already = ("watercolor" + config.SAFETY_STYLE_SUFFIX).strip()
    ib.generate(content_prompt="a hero", style_prompt=already,
                model_id="imagen-4.0-fast-generate-001")
    assert seen["style_prompt"].lower().count(config.SAFETY_STYLE_SUFFIX.strip().lower()) == 1


def test_local_does_not_get_the_safety_suffix(stub_local):
    """Deliberate: local generation sends the style prompt unmodified."""
    ib.generate(content_prompt="a hero", style_prompt="watercolor",
                model_id="sdxl-local")
    assert stub_local.calls[0]["style_prompt"] == "watercolor"


def test_local_result_carries_seed_and_versions(stub_local):
    out = ib.generate(content_prompt="a hero", model_id="sdxl-local", seed=1234)
    assert stub_local.calls[0]["seed"] == 1234   # forwarded, not swallowed
    assert out.seed == 4242                      # what the backend reports back
    assert out.meta["versions"]["meta_version"] == ib.META_VERSION
    assert "created_at" in out.meta


def test_gemini_reports_a_single_progress_step(monkeypatch):
    monkeypatch.setattr(gemini_generator, "generate", lambda **k: "IMAGE")
    steps = []
    ib.generate(
        content_prompt="x",
        model_id="imagen-4.0-fast-generate-001",
        on_step=lambda s, t: steps.append((s, t)),
    )
    assert steps == [(0, 1)]


def test_save_image_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini_generator, "save_image",
                        lambda img, fn, meta=None: calls.append((img, fn, meta)) or "/tmp/x.png")
    assert ib.save_image("IMG", "x.png") == "/tmp/x.png"
    assert calls == [("IMG", "x.png", None)]


def test_save_result_attaches_the_results_own_meta(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini_generator, "save_image",
                        lambda img, fn, meta=None: calls.append(meta) or "/tmp/x.png")
    res = ib.GenerationResult(image="IMG", seed=7, meta={"seed": 7})
    ib.save_result(res, "x.png")
    assert calls == [{"seed": 7}]


# ── local backend (stubbed — local_generator does not exist yet) ────────────

@pytest.fixture
def stub_local(monkeypatch):
    """Install a fake `local_generator` module for the duration of a test."""
    mod = types.ModuleType("local_generator")
    mod.calls = []
    mod.discover_models = lambda: [{"id": "sdxl-local", "name": "SDXL", "type": "sdxl"}]

    def gen(**kwargs):
        mod.calls.append(kwargs)
        # (image, meta) — the local backend's contract since metadata capture
        return "LOCAL_IMAGE", {"backend": "local", "seed": 4242, "reproducible": True}

    mod.generate = gen
    monkeypatch.setitem(sys.modules, "local_generator", mod)
    return mod


def test_local_models_join_the_registry(stub_local):
    models = ib.list_models()
    assert ("sdxl-local", "local") in {(m["id"], m["backend"]) for m in models}
    # cloud models are still there and still cloud
    assert ib.backend_for("imagen-4.0-fast-generate-001") == "gemini"
    assert ib.backend_for("sdxl-local") == "local"


def test_routes_to_local_without_an_api_key(stub_local):
    out = ib.generate(
        content_prompt="a dragon",
        model_id="sdxl-local",
        api_key="should-not-be-forwarded",
        on_step=lambda s, t: None,
    )
    assert out.image == "LOCAL_IMAGE"
    kwargs = stub_local.calls[0]
    assert kwargs["content_prompt"] == "a dragon"
    assert "api_key" not in kwargs        # a local pipeline has no credential
    assert kwargs["on_step"] is not None  # but it does get progress


def test_broken_local_backend_does_not_break_cloud(monkeypatch):
    """A half-installed local backend must not take the paid, working path down."""
    mod = types.ModuleType("local_generator")

    def boom():
        raise RuntimeError("torch not installed")

    mod.discover_models = boom
    monkeypatch.setitem(sys.modules, "local_generator", mod)

    models = ib.list_models()
    assert {m["backend"] for m in models} == {"gemini"}
    assert ib.backend_for("imagen-4.0-fast-generate-001") == "gemini"
