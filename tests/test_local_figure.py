"""Local figure engine: availability gating, backends endpoint, submit guards.

Offline — the Hunyuan pipeline itself is exercised by the M1 spike and live
verification, which these tests could only fake.
"""
import pytest
from fastapi.testclient import TestClient

import local_figure_generator as lfg
import main


client = TestClient(main.app)


# ── availability gating ─────────────────────────────────────────────────────

def test_unavailable_without_extras_or_port(monkeypatch):
    monkeypatch.setattr(lfg, "_deps_missing", lambda: ["timm", "pymeshlab"])
    ok, reason = lfg.available()
    assert ok is False and "requirements-3d.txt" in reason


def test_unavailable_without_port_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(lfg, "_deps_missing", lambda: [])
    monkeypatch.setattr(lfg, "HY3D_DIR", str(tmp_path / "nowhere"))
    ok, reason = lfg.available()
    assert ok is False and "port not found" in reason


def test_available_when_deps_and_port_present(monkeypatch, tmp_path):
    monkeypatch.setattr(lfg, "_deps_missing", lambda: [])
    (tmp_path / "hy3dshape").mkdir()
    monkeypatch.setattr(lfg, "HY3D_DIR", str(tmp_path))
    ok, reason = lfg.available()
    assert ok is True


# ── /figure/backends ────────────────────────────────────────────────────────

def test_backends_lists_meshy_only_with_key(monkeypatch):
    monkeypatch.setattr(main.settings_store, "get_key",
                        lambda name: "k" if name == "MESHY_API_KEY" else None)
    monkeypatch.setattr(lfg, "available", lambda: (False, "extras missing"))
    data = client.get("/figure/backends").json()
    assert [e["id"] for e in data["engines"]] == ["meshy"]
    assert data["local"]["available"] is False


def test_backends_lists_local_when_ready(monkeypatch):
    monkeypatch.setattr(main.settings_store, "get_key", lambda name: None)
    monkeypatch.setattr(lfg, "available", lambda: (True, "Ready"))
    data = client.get("/figure/backends").json()
    ids = [e["id"] for e in data["engines"]]
    assert ids == ["local-hunyuan3d"]
    assert data["engines"][0]["backend"] == "local"


# ── submit guards ───────────────────────────────────────────────────────────

def test_local_engine_unavailable_is_503(monkeypatch):
    monkeypatch.setattr(lfg, "available", lambda: (False, "extras missing"))
    r = client.post("/figure/generate", json={
        "prompt": "a dragon", "engine": "local-hunyuan3d"})
    assert r.status_code == 503
    assert "extras missing" in r.json()["detail"]


def test_local_text_mode_requires_valid_image_model(monkeypatch):
    monkeypatch.setattr(lfg, "available", lambda: (True, "Ready"))
    monkeypatch.setattr(main.image_backends, "backend_for", lambda mid: None)
    r = client.post("/figure/generate", json={
        "prompt": "a dragon", "engine": "local-hunyuan3d",
        "image_model": "bogus"})
    assert r.status_code == 400
    assert "image model" in r.json()["detail"]


def test_local_from_image_spawns_without_meshy_key(monkeypatch, tmp_path):
    monkeypatch.setattr(lfg, "available", lambda: (True, "Ready"))
    monkeypatch.setattr(main.settings_store, "get_key", lambda name: None)
    src = tmp_path / ("a" * 32 + ".png")
    src.write_bytes(b"png")
    monkeypatch.setattr(main, "_resolve_image_path", lambda fn: str(src))
    spawned = {}

    class FakeThread:
        def __init__(self, *a, **k):
            spawned.update(k)
        def start(self):
            pass

    monkeypatch.setattr(main.threading, "Thread", FakeThread)
    r = client.post("/figure/generate-from-image", json={
        "filename": "a" * 32 + ".png", "engine": "local-hunyuan3d"})
    assert r.status_code == 200 and "job_id" in r.json()
    assert spawned["target"] is main._run_local_figure_job


def test_meshy_path_unchanged_without_engine(monkeypatch):
    monkeypatch.setattr(main.settings_store, "get_key", lambda name: None)
    r = client.post("/figure/generate", json={"prompt": "a dragon"})
    assert r.status_code == 503
    assert "MESHY_API_KEY" in r.json()["detail"]
