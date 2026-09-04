"""Suite-wide hermeticity.

A real ComfyUI may be running on the dev machine; tests must not see it.
The default is "Comfy unreachable" — tests that want a Comfy stub their own
_get (test_comfy_generator's _stub_api), which re-patches over this.
"""
import pytest

import comfy_generator


@pytest.fixture(autouse=True)
def _no_real_comfy(monkeypatch):
    monkeypatch.setattr(comfy_generator, "_get",
                        lambda url, timeout=5.0: (_ for _ in ()).throw(OSError("hermetic")))
    comfy_generator._probe_cache.update(at=0.0, url=None)
    yield
    comfy_generator._probe_cache.update(at=0.0, url=None)
