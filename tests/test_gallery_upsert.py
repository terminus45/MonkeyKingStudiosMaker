"""Gallery images manifest: upsert-by-filename.

A generation job is gallery-saved from both the worker and the polling page;
the manifest must end up with one record per image, merged, never duplicated.
Offline — the manifest is redirected to a temp file.
"""
import pytest

import main


@pytest.fixture
def tmp_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_IMAGES_MANIFEST", tmp_path / "images.json")
    return main._IMAGES_MANIFEST


def test_first_save_appends(tmp_manifest):
    rec = main._manifest_upsert_image(
        {"id": "aaaaaaaa", "filename": "f1.png", "prompt": "a fox",
         "story": None, "model": "comfy:krea2-turbo", "created_at": "t0"})
    items = main._manifest_read(tmp_manifest)
    assert len(items) == 1 and rec["id"] == "aaaaaaaa"


def test_second_save_merges_not_duplicates(tmp_manifest):
    main._manifest_upsert_image(
        {"id": "aaaaaaaa", "filename": "f1.png", "prompt": "a fox",
         "story": None, "style_prompt": None,
         "model": "comfy:krea2-turbo", "created_at": "t0"})
    # The page's later save knows story/style the worker didn't.
    merged = main._manifest_upsert_image(
        {"id": "bbbbbbbb", "filename": "f1.png", "prompt": "a fox",
         "story": "fox tale", "style_prompt": "watercolor",
         "model": "comfy:krea2-turbo", "created_at": "t1"})
    items = main._manifest_read(tmp_manifest)
    assert len(items) == 1
    # Identity and timestamp of the first save win; empty fields fill in.
    assert merged["id"] == "aaaaaaaa" and merged["created_at"] == "t0"
    assert merged["story"] == "fox tale" and merged["style_prompt"] == "watercolor"


def test_merge_never_overwrites_existing_values(tmp_manifest):
    main._manifest_upsert_image(
        {"id": "aaaaaaaa", "filename": "f1.png", "prompt": "original prompt",
         "model": "m1", "created_at": "t0"})
    merged = main._manifest_upsert_image(
        {"id": "bbbbbbbb", "filename": "f1.png", "prompt": "different prompt",
         "model": "m2", "created_at": "t1"})
    assert merged["prompt"] == "original prompt" and merged["model"] == "m1"


def test_different_filenames_stay_separate(tmp_manifest):
    main._manifest_upsert_image({"id": "aaaaaaaa", "filename": "f1.png",
                                 "prompt": "x", "created_at": "t0"})
    main._manifest_upsert_image({"id": "bbbbbbbb", "filename": "f2.png",
                                 "prompt": "y", "created_at": "t1"})
    assert len(main._manifest_read(tmp_manifest)) == 2
