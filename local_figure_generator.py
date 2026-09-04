"""On-device image-to-3D figure generation — Hunyuan3D-2.1 shape stage.

design-specs/local-3d-generation.md (M2). Same posture as local_generator:
every heavy import lives inside a function, so this module imports cleanly
on a machine without the 3D extras and available() explains what's missing.

The model code is the pinned Mac/MPS port of Tencent's Hunyuan3D-2.1,
cloned (not vendored) into HY3D_DIR — it is re-downloadable tooling, like
weights, not application code. Weights (~6.8 GB) live in the port's own
cache (~/.cache/hy3dgen) and download on first use.

Output is an UNTEXTURED mesh — weak for the on-screen viewer, irrelevant
for 3D printing (STL carries no color). That framing is the point of v1:
free, private, print-ready figures; Meshy remains the textured path.

License note: Tencent Hunyuan 3D 2.1 Community License — commercial use
permitted below 1 M MAU; no EU/UK/South Korea distribution; outputs belong
to the user. Verified 2026-09-04.
"""
import os
import threading
import time
from typing import Callable, Optional, Tuple

HY3D_DIR = os.getenv("HY3D_DIR", os.path.join(
    os.getenv("LOCAL_MODELS_DIR", "./models"), "hy3d", "Hunyuan3D-2.1-mac"))
HY3D_MODEL_ID = "tencent/Hunyuan3D-2.1"

# Shape-stage quality/speed knobs. 30 steps / octree 256 is the community-
# measured sweet spot on Apple Silicon; env-tunable without a code change.
HY3D_STEPS = int(os.getenv("HY3D_STEPS", "30"))
HY3D_OCTREE = int(os.getenv("HY3D_OCTREE", "256"))
# Printable meshes don't need marching-cubes density; decimate to this.
HY3D_TARGET_FACES = int(os.getenv("HY3D_TARGET_FACES", "80000"))

_GPU = threading.BoundedSemaphore(1)
_resident: dict = {"pipe": None, "rembg": None}
_resident_lock = threading.Lock()


def _deps_missing() -> list[str]:
    missing = []
    for mod in ("torch", "timm", "rembg", "pymeshlab", "trimesh"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return missing


def available() -> tuple[bool, str]:
    missing = _deps_missing()
    if missing:
        return False, (f"3D extras not installed ({', '.join(missing)} — "
                       "pip install -r requirements-3d.txt)")
    if not os.path.isdir(os.path.join(HY3D_DIR, "hy3dshape")):
        return False, f"Hunyuan3D port not found at {HY3D_DIR}"
    return True, "Ready (first figure downloads ~6.8 GB of weights)"


def _load():
    """Load (or return) the resident shape pipeline. Seconds after the
    one-time weight download; ~4 GB resident."""
    with _resident_lock:
        if _resident["pipe"] is not None:
            return _resident["pipe"], _resident["rembg"]
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        import sys
        shape_dir = os.path.abspath(os.path.join(HY3D_DIR, "hy3dshape"))
        if shape_dir not in sys.path:
            sys.path.insert(0, shape_dir)
        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dshape.rembg import BackgroundRemover
        pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(HY3D_MODEL_ID)
        _resident.update(pipe=pipe, rembg=BackgroundRemover())
        return pipe, _resident["rembg"]


def _cleanup(mesh, target_faces: int):
    """Make the raw marching-cubes mesh printable: drop floaters and
    degenerate faces, decimate to a sane count. Uses the port's own
    pymeshlab-backed postprocessors."""
    from hy3dshape.postprocessors import (
        DegenerateFaceRemover, FaceReducer, FloaterRemover)
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    if len(mesh.faces) > target_faces:
        mesh = FaceReducer()(mesh, max_facenum=target_faces)
    return mesh


def generate_figure(
    image,                                    # PIL.Image
    glb_path: str,
    on_progress: Optional[Callable[[str, int], None]] = None,
) -> dict:
    """Portrait image → cleaned, printable GLB at glb_path. Returns stats.

    on_progress(stage, percent) with stages 'preparing' → 'meshing' →
    'cleanup'. Serialised behind one semaphore — the GPU is not
    parallel-safe, and a mesh job beside an image job is a memory choice
    the semaphore makes deliberate.
    """
    def report(stage: str, pct: int) -> None:
        if on_progress:
            on_progress(stage, pct)

    with _GPU:
        report("preparing", 5)
        pipe, rembg = _load()
        img = image.convert("RGB")
        img.thumbnail((1024, 1024))
        rgba = rembg(img)

        report("meshing", 15)
        t0 = time.time()
        mesh = pipe(image=rgba, num_inference_steps=HY3D_STEPS,
                    octree_resolution=HY3D_OCTREE)[0]
        shape_s = time.time() - t0

        report("cleanup", 90)
        raw_faces = len(mesh.faces)
        mesh = _cleanup(mesh, HY3D_TARGET_FACES)
        os.makedirs(os.path.dirname(glb_path) or ".", exist_ok=True)
        mesh.export(glb_path)

        import trimesh as tm
        m = tm.load(glb_path, force="mesh")
        return {
            "engine": "local-hunyuan3d",
            "model_id": HY3D_MODEL_ID,
            "steps": HY3D_STEPS,
            "octree_resolution": HY3D_OCTREE,
            "shape_seconds": round(shape_s, 1),
            "faces_raw": raw_faces,
            "faces": len(m.faces),
            "vertices": len(m.vertices),
            "watertight": bool(m.is_watertight),
            "textured": False,
        }
