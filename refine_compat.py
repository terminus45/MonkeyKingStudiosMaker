"""Refine-model compatibility: which local models may refine which images.

A generated-and-saved table (models/.refine_compat.json), rebuilt lazily
whenever the checkpoint set or any sidecar changes, with hand-editable
allow/ban overrides that survive regeneration. The server NEVER picks a
refine model — callers choose from the ranked candidates and /refine/job
merely validates the explicit choice against this table.

Ranking rules (design-specs/image-metadata-and-refine.md, Refine
compatibility F3):
  same-model    the checkpoint that made the image        — listed first
  same-family   same architecture kind (sd15 / sdxl)      — listed after
  cross-family  different kind                            — excluded unless
                an `allow` override names the pair
Within same-family: models without the cache_unsafe reload tax rank first,
then matching prompt_style (natural vs tags), then name.

The overrides block is the one escape hatch and the future landing spot for
learned pair quality — there is no `force` request flag.
"""
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import local_generator

_lock = threading.Lock()


def _dir() -> str:
    # Read through local_generator so tests monkeypatching its LOCAL_MODELS_DIR
    # redirect this module too.
    return local_generator.LOCAL_MODELS_DIR


def table_path() -> str:
    return os.path.join(_dir(), ".refine_compat.json")


def _inputs_checksum() -> str:
    """Fingerprint of the checkpoint set + sidecar contents."""
    h = hashlib.sha256()
    for model_id, filename, size in local_generator._checkpoints():
        try:
            mtime = int(os.stat(os.path.join(_dir(), filename)).st_mtime)
        except OSError:
            mtime = 0
        h.update(f"{filename}|{size}|{mtime}".encode())
        sidecar = os.path.join(_dir(), filename[:-len(".safetensors")] + ".json")
        try:
            with open(sidecar, "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(b"-")
    return h.hexdigest()


def _model_infos() -> dict:
    """{model_id: {kind, prompt_style, cache_unsafe}} for every local model."""
    infos = {}
    for model_id, filename, size in local_generator._checkpoints():
        kind = "sdxl" if size >= local_generator._SDXL_MIN_BYTES else "sd15"
        ms = local_generator._model_settings(model_id)
        infos[model_id] = {
            "kind": kind,
            "prompt_style": ms.get("prompt_style", "natural"),
            "cache_unsafe": bool(ms.get("cache_unsafe", False)),
        }
    return infos


def _rank_same_family(source_id: Optional[str], infos: dict, kind: str) -> list:
    """same-family candidates for `kind`, best first, source excluded."""
    src_style = infos.get(source_id, {}).get("prompt_style", "natural")
    peers = [(mid, i) for mid, i in infos.items()
             if i["kind"] == kind and mid != source_id]
    peers.sort(key=lambda p: (
        p[1]["cache_unsafe"],                       # no reload tax first
        p[1]["prompt_style"] != src_style,          # matching dialect first
        p[0],                                       # stable name order
    ))
    return [{"model_id": mid, "tier": "same-family"} for mid, _ in peers]


def _build(overrides: dict) -> dict:
    infos = _model_infos()
    pairs = {}
    for source_id, info in infos.items():
        row = [{"model_id": source_id, "tier": "same-model"}]
        row += _rank_same_family(source_id, infos, info["kind"])
        pairs[source_id] = row
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs_checksum": _inputs_checksum(),
        "models": infos,
        "pairs": pairs,
        "overrides": overrides,
    }


def _read() -> Optional[dict]:
    try:
        with open(table_path(), encoding="utf-8") as f:
            t = json.load(f)
        return t if isinstance(t, dict) else None
    except Exception:
        return None


def load_table() -> dict:
    """The current table, regenerated if the model set or sidecars changed.

    Overrides are carried over verbatim on regeneration — they are the saved
    part; everything else is derived.
    """
    with _lock:
        existing = _read()
        checksum = _inputs_checksum()
        if existing and existing.get("inputs_checksum") == checksum:
            return existing

        overrides = (existing or {}).get("overrides") or {}
        overrides = {
            "allow": [list(p) for p in overrides.get("allow", []) if isinstance(p, (list, tuple)) and len(p) == 2],
            "ban":   [list(p) for p in overrides.get("ban", [])   if isinstance(p, (list, tuple)) and len(p) == 2],
        }
        table = _build(overrides)
        try:
            tmp = table_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(table, f, indent=2)
            os.replace(tmp, table_path())
        except Exception:
            pass  # an unwritable table still works this process
        return table


def candidates(source_model_id: Optional[str], source_kind: Optional[str]) -> list:
    """Ranked refine candidates for an image.

    `source_model_id` is the model that made the image when it was local and
    still resolves; `source_kind` covers everything else (cloud images and
    legacy/deleted-model images, via metadata or the dimension fallback).
    Overrides apply last: bans remove, allows append cross-family pairs.
    """
    table = load_table()
    infos = table["models"]

    if source_model_id and source_model_id in table["pairs"]:
        row = list(table["pairs"][source_model_id])
        kind = infos[source_model_id]["kind"]
    elif source_kind in ("sd15", "sdxl"):
        row = _rank_same_family(None, infos, source_kind)
        kind = source_kind
    else:
        return []

    ov = table.get("overrides") or {}
    src_key = source_model_id or f"kind:{kind}"
    banned = {tuple(p) for p in ov.get("ban", [])}
    row = [c for c in row if (src_key, c["model_id"]) not in banned
           and (source_model_id, c["model_id"]) not in banned]
    for pair in ov.get("allow", []):
        if pair[0] in (source_model_id, src_key) and pair[1] in infos:
            if not any(c["model_id"] == pair[1] for c in row):
                row.append({"model_id": pair[1], "tier": "override-allow"})
    return row


def kind_for_image(meta: dict, image_path: str) -> Optional[str]:
    """Best-effort architecture family for a source image.

    Preference: recorded metadata kind → the source model's current kind →
    dimension heuristic (>700 px long edge is SDXL-class; SD 1.5 output tops
    out around 704 even after the hires pass at default config).
    """
    if meta.get("kind") in ("sd15", "sdxl"):
        return meta["kind"]
    mid = meta.get("model_id")
    if mid:
        try:
            _, kind = local_generator._resolve(mid)
            return kind
        except ValueError:
            pass
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            return "sdxl" if max(im.size) > 700 else "sd15"
    except Exception:
        return None
