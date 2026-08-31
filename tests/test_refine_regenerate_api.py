"""Validation-path tests for /refine/job and /regenerate/job.

Only the synchronous request validation is covered here — it runs before any
worker spawns, so these tests need no torch, no models, and no generation.
The happy paths (bit-identical regeneration, lineage on refined images) are
runtime behaviour verified against real renders, which unit tests here could
only fake.
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app)


# ── /refine/job ─────────────────────────────────────────────────────────────

def test_refine_rejects_bad_filename(client):
    r = client.post("/refine/job", json={
        "filename": "../../etc/passwd", "instruction": "x",
        "model_id": "local:whatever"})
    assert r.status_code == 400
    assert "filename" in r.json()["detail"].lower()


def test_refine_rejects_empty_instruction(client):
    r = client.post("/refine/job", json={
        "filename": "a" * 32 + ".png", "instruction": "   ",
        "model_id": "local:whatever"})
    # note: 32 hex chars required — use a syntactically valid name
    r = client.post("/refine/job", json={
        "filename": "0" * 32 + ".png", "instruction": "   ",
        "model_id": "local:whatever"})
    assert r.status_code == 400
    assert "instruction" in r.json()["detail"].lower()


def test_refine_rejects_cloud_models(client):
    """Refinement is on-device only; the error must say so, not 500."""
    r = client.post("/refine/job", json={
        "filename": "0" * 32 + ".png", "instruction": "add a hat",
        "model_id": "gemini-2.5-flash-image"})
    assert r.status_code == 400
    assert "on-device" in r.json()["detail"]


def test_refine_404_for_missing_image(client, monkeypatch):
    monkeypatch.setattr(main, "_resolve_image_path", lambda f: None)
    monkeypatch.setattr(main.image_backends, "backend_for",
                        lambda m: "local" if m.startswith("local:") else "gemini")
    r = client.post("/refine/job", json={
        "filename": "0" * 32 + ".png", "instruction": "add a hat",
        "model_id": "local:some-model"})
    assert r.status_code == 404


# ── /regenerate/job ─────────────────────────────────────────────────────────

def test_regenerate_rejects_bad_filename(client):
    r = client.post("/regenerate/job", json={"filename": "not-hex.png"})
    assert r.status_code == 400


def test_regenerate_404_for_missing_image(client, monkeypatch):
    monkeypatch.setattr(main, "_resolve_image_path", lambda f: None)
    r = client.post("/regenerate/job", json={"filename": "0" * 32 + ".png"})
    assert r.status_code == 404


def test_regenerate_rejects_images_without_a_recipe(client, monkeypatch):
    monkeypatch.setattr(main, "_resolve_image_path", lambda f: "/tmp/x.png")
    monkeypatch.setattr(main.gemini_generator, "read_image_metadata", lambda p: None)
    r = client.post("/regenerate/job", json={"filename": "0" * 32 + ".png"})
    assert r.status_code == 400
    assert "recipe" in r.json()["detail"].lower()


def test_regenerate_rejects_cloud_recipes(client, monkeypatch):
    """meta.reproducible False (cloud) must be a clear 400, not an attempt."""
    monkeypatch.setattr(main, "_resolve_image_path", lambda f: "/tmp/x.png")
    monkeypatch.setattr(main.gemini_generator, "read_image_metadata",
                        lambda p: {"backend": "gemini", "reproducible": False})
    r = client.post("/regenerate/job", json={"filename": "0" * 32 + ".png"})
    assert r.status_code == 400


def test_regenerate_rejects_a_vanished_model(client, monkeypatch):
    """Recipe references a checkpoint that has since been removed."""
    monkeypatch.setattr(main, "_resolve_image_path", lambda f: "/tmp/x.png")
    monkeypatch.setattr(main.gemini_generator, "read_image_metadata",
                        lambda p: {"backend": "local", "reproducible": True,
                                   "model_id": "local:deleted-model"})
    monkeypatch.setattr(main.image_backends, "backend_for", lambda m: None)
    r = client.post("/regenerate/job", json={"filename": "0" * 32 + ".png"})
    assert r.status_code == 400
    assert "no longer available" in r.json()["detail"]
