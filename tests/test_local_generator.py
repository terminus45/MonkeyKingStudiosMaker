"""Tests for the local image backend's discovery and id→path resolution.

Offline and torch-free: everything here exercises the parts that run before
any pipeline is loaded. Model files are faked with sparse files of the right
size, so the suite never touches the real ./models directory.

The security rules under test come from design-specs/local-image-generation.md
decision D3.
"""
import os

import pytest

local_generator = pytest.importorskip("local_generator")


def _fake_checkpoint(directory, name, gb=0.1):
    """Create a sparse file of a given size — enough for size-based SDXL detection."""
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.truncate(int(gb * 1024 ** 3))
    return path


@pytest.fixture
def models_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(local_generator, "LOCAL_MODELS_DIR", str(tmp_path))
    return tmp_path


# ── discovery ───────────────────────────────────────────────────────────────

def test_discovers_safetensors_only(models_dir):
    """.ckpt is a pickle — loading one is arbitrary code execution, so it must
    never appear in the allow-list."""
    _fake_checkpoint(models_dir, "good_model.safetensors")
    _fake_checkpoint(models_dir, "evil_model.ckpt")
    _fake_checkpoint(models_dir, "notes.txt")

    ids = {m["id"] for m in local_generator.discover_models()}
    assert ids == {"local:good_model"}


def test_ignores_subdirectories(models_dir):
    """LoRAs and HuggingFace hub caches live in subdirectories; neither is a
    base checkpoint."""
    (models_dir / "LORAs").mkdir()
    _fake_checkpoint(models_dir / "LORAs", "some_lora.safetensors")
    _fake_checkpoint(models_dir, "base.safetensors")

    assert {m["id"] for m in local_generator.discover_models()} == {"local:base"}


def test_classifies_sdxl_by_size(models_dir):
    _fake_checkpoint(models_dir, "big.safetensors", gb=6.5)
    _fake_checkpoint(models_dir, "small.safetensors", gb=2.0)
    kinds = {m["id"]: m["type"] for m in local_generator.discover_models()}
    assert kinds["local:big"] == "sdxl"
    assert kinds["local:small"] == "sd15"


def test_empty_directory_yields_no_models(models_dir):
    assert local_generator.discover_models() == []


# ── id → path resolution (D3: ids, never paths) ─────────────────────────────

def test_resolve_maps_a_discovered_id_to_its_file(models_dir):
    _fake_checkpoint(models_dir, "base.safetensors")
    path, kind = local_generator._resolve("local:base")
    assert path == str(models_dir / "base.safetensors")
    assert kind == "sd15"


@pytest.mark.parametrize("attack", [
    "local:../../../etc/passwd",
    "../../etc/passwd",
    "/etc/passwd",
    "local:evil",                    # a .ckpt that exists on disk but is excluded
    "",
])
def test_resolve_rejects_anything_not_in_the_allow_list(models_dir, attack):
    """Nothing from a request body may be joined onto a filesystem path — the
    only paths ever built are from filenames this module itself enumerated."""
    _fake_checkpoint(models_dir, "evil.ckpt")
    with pytest.raises(ValueError):
        local_generator._resolve(attack)


def test_traversal_cannot_escape_even_with_a_real_target(models_dir, tmp_path):
    """A checkpoint outside LOCAL_MODELS_DIR stays unreachable."""
    outside = tmp_path.parent / "outside.safetensors"
    with open(outside, "wb") as f:
        f.truncate(1024)
    for attempt in (f"local:../{outside.stem}", str(outside), f"local:{outside}"):
        with pytest.raises(ValueError):
            local_generator._resolve(attempt)


# ── dimension mapping ───────────────────────────────────────────────────────

@pytest.mark.parametrize("kind,ar,expected_long_edge", [
    ("sdxl", "1:1", 1024),
    ("sd15", "1:1", 512),
])
def test_dimensions_snap_to_native_resolution(kind, ar, expected_long_edge):
    w, h = local_generator._dimensions(kind, ar, 0, 0)
    assert max(w, h) == expected_long_edge


@pytest.mark.parametrize("ar", ["1:1", "3:4", "4:3", "9:16", "16:9"])
def test_dimensions_are_multiples_of_64(ar):
    """The UNet requires it; a stray 500px would fail at generation time."""
    w, h = local_generator._dimensions("sdxl", ar, 0, 0)
    assert w % 64 == 0 and h % 64 == 0
    assert w >= 256 and h >= 256


def test_dimensions_survive_a_malformed_aspect_ratio():
    w, h = local_generator._dimensions("sd15", "not-a-ratio", 0, 0)
    assert w % 64 == 0 and h % 64 == 0


@pytest.mark.parametrize("kind,base", [("sd15", 512), ("sdxl", 1024)])
@pytest.mark.parametrize("ar", ["1:1", "3:4", "4:3", "9:16", "16:9"])
def test_dimensions_preserve_native_pixel_area(kind, base, ar):
    """Area, not long edge, is what must stay near native.

    Clamping the long edge to `base` starves non-square ratios — the model
    then renders well below the resolution it was trained at.
    """
    w, h = local_generator._dimensions(kind, ar, 0, 0)
    native = base * base
    assert 0.90 <= (w * h) / native <= 1.10, f"{ar} -> {w}x{h} is {w*h/native:.0%} of native"


def test_tall_ratio_regression():
    """9:16 on SD 1.5 used to come out 256x512 — half the pixel budget."""
    w, h = local_generator._dimensions("sd15", "9:16", 0, 0)
    assert (w, h) != (256, 512)
    assert w * h > 256 * 512 * 1.5
    assert h > w                       # still tall


def test_dimensions_respect_the_requested_orientation():
    for ar in ("3:4", "9:16"):
        w, h = local_generator._dimensions("sdxl", ar, 0, 0)
        assert h > w, f"{ar} should be portrait, got {w}x{h}"
    for ar in ("4:3", "16:9"):
        w, h = local_generator._dimensions("sdxl", ar, 0, 0)
        assert w > h, f"{ar} should be landscape, got {w}x{h}"


def test_extreme_ratio_is_capped(monkeypatch):
    """An absurd ratio must not request a huge, slow render."""
    w, h = local_generator._dimensions("sdxl", "1:50", 0, 0)
    assert w >= 256 and h <= 1024 * 2


# ── negative prompt ─────────────────────────────────────────────────────────

def test_quality_negatives_applied_when_caller_sends_none():
    neg = local_generator._negative_prompt("")
    assert "bad anatomy" in neg and "watermark" in neg


def test_caller_negatives_compose_with_the_defaults():
    """Caller terms lead: CLIP truncates at 77 tokens and the defaults spend
    ~60, so whatever falls off the end must be our boilerplate, never the
    user's explicit exclusions."""
    neg = local_generator._negative_prompt("no hats")
    assert neg.startswith("no hats")
    assert "bad anatomy" in neg          # defaults are not replaced


def test_default_negatives_target_anatomy_and_fit_the_token_budget():
    """The default set must cover the anatomy failure modes (hands, fingers,
    limbs) and stay within CLIP's window. Exact token counting needs the CLIP
    tokenizer (network download), so this is an offline tripwire: the curated
    set measured 60/77 tokens at ~34 comma-terms and ~430 chars — a ceiling
    comfortably above that but below the ~100-token community lists guards
    against someone pasting one in and silently losing the tail."""
    neg = local_generator.LOCAL_NEGATIVE_PROMPT
    for term in ("bad hands", "extra fingers", "missing fingers",
                 "extra limbs", "missing limbs", "bad anatomy"):
        assert term in neg, f"missing anatomy term: {term}"
    assert len(neg.split(",")) <= 26, "term count creeping toward CLIP truncation"
    assert len(neg) <= 500, "character length creeping toward CLIP truncation"


def test_negatives_can_be_disabled(monkeypatch):
    monkeypatch.setattr(local_generator, "LOCAL_NEGATIVE_PROMPT", "")
    assert local_generator._negative_prompt("") is None
    assert local_generator._negative_prompt("no hats") == "no hats"


# ── hires fix ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ar", ["1:1", "3:4", "4:3", "9:16", "16:9"])
def test_sd15_gets_a_hires_pass(ar):
    """SD 1.5 is what the fix exists for — its faces don't resolve at 512."""
    w, h = local_generator._dimensions("sd15", ar, 0, 0)
    target = local_generator._hires_target(w, h)
    assert target is not None
    tw, th = target
    assert tw * th > w * h                       # genuinely larger
    assert tw % 64 == 0 and th % 64 == 0
    assert (tw > th) == (w > h)                  # orientation preserved


@pytest.mark.parametrize("ar", ["1:1", "3:4", "16:9"])
def test_sdxl_skips_the_hires_pass_by_default(ar):
    """SDXL already renders faces well; a second pass would add ~85 s for little."""
    w, h = local_generator._dimensions("sdxl", ar, 0, 0)
    assert local_generator._hires_target(w, h) is None


def test_hires_respects_the_pixel_ceiling(monkeypatch):
    monkeypatch.setattr(local_generator, "LOCAL_HIRES_MAX_PIXELS", 400_000)
    target = local_generator._hires_target(512, 512)
    if target:
        assert target[0] * target[1] <= 400_000 * 1.15


def test_hires_disabled_by_scale_one(monkeypatch):
    monkeypatch.setattr(local_generator, "LOCAL_HIRES_SCALE", 1.0)
    assert local_generator._hires_target(512, 512) is None


def test_hires_skipped_when_the_gain_is_marginal(monkeypatch):
    """Not worth a whole extra diffusion pass for a few percent more pixels."""
    monkeypatch.setattr(local_generator, "LOCAL_HIRES_SCALE", 1.02)
    assert local_generator._hires_target(512, 512) is None


# ── sampler ─────────────────────────────────────────────────────────────────

def test_default_sampler_is_not_the_diffusers_legacy_default():
    from config import LOCAL_SAMPLER
    assert LOCAL_SAMPLER in local_generator.SAMPLERS
    assert LOCAL_SAMPLER != "pndm"


def test_unknown_sampler_leaves_the_pipeline_untouched(monkeypatch):
    """A bad LOCAL_SAMPLER must not cost the user their generation."""
    class FakeScheduler:
        config = {}

    class FakePipe:
        scheduler = FakeScheduler()

    pipe = FakePipe()
    monkeypatch.setattr(local_generator, "LOCAL_SAMPLER", "not-a-sampler")
    assert local_generator._apply_sampler(pipe) == "FakeScheduler"
    assert isinstance(pipe.scheduler, FakeScheduler)


# ── availability reporting ──────────────────────────────────────────────────

def test_available_explains_an_empty_models_dir(models_dir):
    ok, reason = local_generator.available()
    assert ok is False
    assert "No .safetensors" in reason


def test_available_explains_a_missing_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(local_generator, "LOCAL_MODELS_DIR", str(tmp_path / "nope"))
    ok, reason = local_generator.available()
    assert ok is False
    assert "No models directory" in reason


# ── degradation without the optional extras ─────────────────────────────────

def test_no_models_offered_when_extras_are_missing(models_dir, monkeypatch):
    """Checkpoints on disk are irrelevant if torch/diffusers can't be imported.

    Discovery is pure filesystem work and would happily list them, but a model
    that cannot load must not reach the Settings picker — that moves the
    failure from a visible "unavailable" line to the middle of a generation
    the user is already waiting on.
    """
    _fake_checkpoint(models_dir, "base.safetensors")
    assert local_generator.discover_models()          # sanity: present when ready

    monkeypatch.setattr(local_generator, "_runtime_ready", lambda: False)
    assert local_generator.discover_models() == []

    ok, reason = local_generator.available()
    assert ok is False
    assert "requirements-local.txt" in reason


def test_dispatcher_offers_only_cloud_when_extras_are_missing(models_dir, monkeypatch):
    import image_backends as ib
    _fake_checkpoint(models_dir, "base.safetensors")
    monkeypatch.setattr(local_generator, "_runtime_ready", lambda: False)

    assert {m["backend"] for m in ib.list_models()} == {"gemini"}
    assert ib.backend_for("local:base") is None


# ── NaN-poisoning guard ─────────────────────────────────────────────────────

def test_looks_poisoned_flags_exact_black():
    from PIL import Image
    assert local_generator._looks_poisoned(Image.new("RGB", (64, 64), (0, 0, 0)))


def test_looks_poisoned_passes_normal_and_near_black_images():
    from PIL import Image
    assert not local_generator._looks_poisoned(Image.new("RGB", (64, 64), (200, 30, 90)))
    # A very dark but not exact-black image is a legitimate render, not NaN.
    assert not local_generator._looks_poisoned(Image.new("RGB", (64, 64), (1, 0, 0)))


def test_evict_pipeline_clears_the_cache(monkeypatch):
    local_generator._pipe = object()
    local_generator._pipe_model_id = "local:x"
    local_generator._evict_pipeline()
    assert local_generator._pipe is None
    assert local_generator._pipe_model_id is None


def test_cache_unsafe_models_evict_before_and_after(monkeypatch, models_dir):
    """Once a model has poisoned a cached run, every later generation loads
    fresh — one wasted render total, not one per generation."""
    from PIL import Image as PILImage
    _fake_checkpoint(models_dir, "unstable.safetensors")

    calls = {"loads": 0, "gens": 0}
    good = PILImage.new("RGB", (8, 8), (100, 100, 100))
    black = PILImage.new("RGB", (8, 8), (0, 0, 0))
    # first attempt poisoned, all later ones clean
    outputs = [black, good, good]

    class FakePipe:
        def __call__(self, **kw):
            calls["gens"] += 1
            out = outputs.pop(0) if outputs else good
            return type("R", (), {"images": [out]})()

    def fake_load(mid):
        calls["loads"] += 1
        return FakePipe()

    monkeypatch.setattr(local_generator, "_load", fake_load)
    monkeypatch.setattr(local_generator, "_apply_sampler", lambda p, n=None: "X")
    monkeypatch.setattr(local_generator, "_torch", lambda: __import__("torch"))
    monkeypatch.setattr(local_generator, "_hires_target", lambda w, h, s=None: None)
    local_generator._CACHE_UNSAFE.discard("local:unstable")

    img1, _ = local_generator.generate(content_prompt="x", model_id="local:unstable", seed=1)
    assert not local_generator._looks_poisoned(img1)      # retry recovered
    assert calls["gens"] == 2                              # one wasted render
    assert "local:unstable" in local_generator._CACHE_UNSAFE

    img2, _ = local_generator.generate(content_prompt="x", model_id="local:unstable", seed=1)
    assert not local_generator._looks_poisoned(img2)
    assert calls["gens"] == 3                              # no second wasted render
    local_generator._CACHE_UNSAFE.discard("local:unstable")
