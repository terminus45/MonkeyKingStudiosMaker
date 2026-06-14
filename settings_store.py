"""Server-side key store — reads/writes config.json, falls back to os.environ.

Priority: config.json (_store) then os.environ.get(name).
Secrets are NEVER logged. config.json is written with chmod 0o600.
"""

import json
import os
import tempfile
import threading
from typing import Optional

from config import KEYS_FILE

KEY_NAMES = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MESHY_API_KEY")

_store: dict = {}
_lock = threading.Lock()


def load() -> None:
    """Read KEYS_FILE into _store. Call once at module import time."""
    global _store
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            with _lock:
                _store = {k: v for k, v in data.items() if isinstance(v, str)}
        else:
            with _lock:
                _store = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        with _lock:
            _store = {}


def get_key(name: str) -> Optional[str]:
    """Return the key value for *name*.

    Precedence: config.json (_store) then os.environ. Returns None if not set.
    Per-request override is handled at the call site, not here.
    """
    with _lock:
        value = _store.get(name)
    if value:
        return value
    return os.environ.get(name) or None


def set_keys(updates: dict) -> None:
    """Update _store with *updates* and persist to KEYS_FILE atomically.

    Rules:
    - Non-empty string value → set in _store.
    - Empty string "" → delete from _store (clear the key).
    - Keys not in KEY_NAMES are silently ignored.
    - config.json is written atomically (temp file + os.replace) and chmod 0o600.
    """
    with _lock:
        for name, value in updates.items():
            if name not in KEY_NAMES:
                continue
            if value:
                _store[name] = value
            else:
                _store.pop(name, None)
        snapshot = dict(_store)

    # Persist outside the lock (atomic write)
    _persist(snapshot)


def _persist(data: dict) -> None:
    """Write *data* to KEYS_FILE atomically and restrict permissions."""
    dir_path = os.path.dirname(os.path.abspath(KEYS_FILE)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, KEYS_FILE)
        try:
            os.chmod(KEYS_FILE, 0o600)
        except OSError:
            pass  # best-effort — Windows does not support Unix permissions
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _mask(secret: str) -> str:
    """Return a masked representation of *secret*. Never expose the full value."""
    if len(secret) >= 8:
        return secret[:3] + "…" + secret[-4:]
    if len(secret) >= 2:
        return "…" + secret[-2:]
    return "…"


def _source(name: str) -> Optional[str]:
    """Return 'config' if key is in _store, 'env' if in os.environ, else None."""
    with _lock:
        in_store = name in _store
    if in_store:
        return "config"
    if os.environ.get(name):
        return "env"
    return None


def status() -> dict:
    """Return a safe status dict for all KEY_NAMES.

    Schema: { NAME: {set: bool, masked: str|None, source: str|None} }
    Secrets are NEVER included in full.
    """
    result = {}
    for name in KEY_NAMES:
        src = _source(name)
        value = get_key(name)
        result[name] = {
            "set": bool(value),
            "masked": _mask(value) if value else None,
            "source": src,
        }
    return result
