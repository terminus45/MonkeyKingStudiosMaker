"""Checkpoint identity for generation metadata.

A filename is not an identity — `sdXL_v10.safetensors` can be replaced and
every recorded generation would silently point at a different model. The
honest identity is a content digest, but SHA-256 of a 6.9 GB file costs ~7 s,
which must never be paid on the generation path.

So: `identity()` returns the cheap facts (size, mtime) synchronously, plus the
sha256 **if it is already known** — from an on-disk cache keyed by
(path, size, mtime). When it isn't, a background thread computes it once and
the *next* generation's metadata carries it. The first image generated after a
new checkpoint appears records `sha256: null`; every one after that is exact.
"""
import hashlib
import json
import os
import threading
from typing import Optional

from config import LOCAL_MODELS_DIR

_CACHE_PATH = os.path.join(LOCAL_MODELS_DIR, ".model_digests.json")
_lock = threading.Lock()
_inflight: set[str] = set()


def _cache_read() -> dict:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _cache_write(cache: dict) -> None:
    try:
        tmp = _CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, _CACHE_PATH)
    except Exception:
        pass  # a failed cache write only means re-hashing later


def _key(path: str, size: int, mtime: int) -> str:
    return f"{os.path.abspath(path)}|{size}|{mtime}"


def _hash_in_background(path: str, size: int, mtime: int) -> None:
    key = _key(path, size, mtime)
    with _lock:
        if key in _inflight:
            return
        _inflight.add(key)

    def work():
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(1 << 22):     # 4 MB chunks
                    h.update(chunk)
            with _lock:
                cache = _cache_read()
                cache[key] = h.hexdigest()
                _cache_write(cache)
        except Exception:
            pass
        finally:
            with _lock:
                _inflight.discard(key)

    threading.Thread(target=work, daemon=True, name="model-digest").start()


def identity(path: str) -> Optional[dict]:
    """Cheap identity now; exact identity once the background hash lands.

    Folder models (diffusers-format directories) get an aggregate identity —
    total component size + newest mtime, no sha256 (hashing ~36 GB of shards
    has no payoff; a swapped folder model changes size/mtime anyway).
    """
    if os.path.isdir(path):
        total, newest = 0, 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    st = os.stat(os.path.join(root, f))
                    total += st.st_size
                    newest = max(newest, int(st.st_mtime))
                except OSError:
                    pass
        return {"name": os.path.basename(path), "size": total,
                "mtime": newest, "sha256": None}
    try:
        st = os.stat(path)
    except OSError:
        return None
    size, mtime = st.st_size, int(st.st_mtime)

    with _lock:
        sha = _cache_read().get(_key(path, size, mtime))
    if sha is None:
        _hash_in_background(path, size, mtime)

    return {
        "name": os.path.basename(path),
        "size": size,
        "mtime": mtime,
        "sha256": sha,          # null until the background hash completes
    }
