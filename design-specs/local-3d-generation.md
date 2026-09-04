# Local 3D Figure Generation — Feasibility & Plan

*Researched 2026-09-04. Status: analysis + phased plan — nothing built.*

## What it would take

Today's figure pipeline (Meshy.AI): child's prompt → Claude rewrite →
Meshy preview → refine → GLB download → print report → gallery save, all
inside a `_figure_jobs` daemon worker the frontend polls. A local path
replaces exactly one link in that chain — **the mesh generation** — and
keeps everything around it: the job store and stages, `FIGURES_DIR`, the
three.js viewer, client-side GLB→STL export, the gallery manifest.

The natural local input is an **image, not text**: every serious local 3D
model of the last two years is image-to-3D, and this app already makes
character images on demand. "Local text-to-3D" therefore falls out for
free as a chain — generate the portrait with an existing image backend
(cloud or local), then image→3D — reusing `/figure/generate-from-image`'s
shape. Pieces to build:

1. **`local_figure_generator.py`** — same posture as `local_generator`:
   heavy imports inside functions, `available() -> (bool, reason)`,
   models resolved server-side by opaque key. Wraps the chosen model's
   Python pipeline: image → (background removal) → mesh → GLB/STL bytes.
2. **Dependencies** — a third extras file (`requirements-3d.txt`): the
   model package, `rembg` (background matting), `trimesh`/`pymeshlab`
   (mesh cleanup/decimation/export). Kept out of `requirements-local.txt`
   so the image extras don't balloon.
3. **Weights** — a one-time multi-GB HF download, pinned revision, cached
   under `models/` territory (re-downloadable, not user content).
4. **Routing** — the figure endpoints grow a `backend` choice the same way
   images did: id-is-backend, discovery as the allow-list, honest absence
   when extras/weights are missing.

## Feasibility on this hardware (M4, 32 GB, MPS)

| Candidate | Mac/MPS status (verified 2026-09) | Memory | Time (M-series) | Notes |
|---|---|---|---|---|
| **Hunyuan3D-2.1** (Tencent) | Working community ports (Brainkeys, VladimirTalyzin) — native MPS, **no custom compiled ops**, `PYTORCH_ENABLE_MPS_FALLBACK` for gaps | shape ~4 GB, texture ~8 GB | shape 2–5 min; +8–9 min texture (M4 Pro/24 GB measured: 344 s + 512 s) | Python API (`Hunyuan3DDiTFlowMatchingPipeline`), exports GLB/OBJ/PLY/STL. Texture stage is the fragile half on macOS (one port disables it, one claims PBR works). Tencent community license — verify terms before shipping |
| **TRELLIS.2** (Microsoft) | Community MPS port; ~5 min on M4 Pro, 400 K-vertex meshes | higher | ~5 min | Best quality tier; port maturity and license need verification |
| **TripoSR** (Stability/Tripo) | Runs on MPS/CPU for years; simplest install | ~2 GB | ~1–2 min | MIT. Quality noticeably below the two above — blobby geometry, vertex colors only. The fallback, not the pick |
| TRELLIS 1 / SF3D / SPAR3D | CUDA custom ops (nvdiffrast, spconv) or mixed Mac reports | — | — | Not the primary path |

**Verdict: feasible.** The decisive facts: Hunyuan3D-2.1's shape stage
needs ~4 GB — it coexists with everything else on this machine (even a
resident SDXL pipeline; only a Comfy-resident Krea 2 squeezes it, and the
idle-unload watchdog already handles that) — and the Mac port needs no
custom compiled ops, which is where Mac ML integrations usually die.
Lessons from our own MPS history apply directly: expect op gaps (the
fallback env var is load-bearing), verify dtype behavior empirically, and
never trust a README's CUDA timings.

**The honest quality/scope framing:** the local shape stage produces an
**untextured mesh**. That is weak for the on-screen GLB viewer but nearly
irrelevant for the app's endgame — **3D printing** — because STL carries
no color anyway. So the local path's v1 value proposition is: *free,
private, print-ready figures*; Meshy stays the pick for pretty textured
viewer models. Texture comes later if the MPS texture stage proves out.

## Initial implementation (M-phases)

- **M1 — Spike (gate)**: install a Hunyuan3D-2.1 Mac fork standalone in
  the scratchpad; run 3–4 of our actual character portraits (Imagen,
  SDXL, Krea 2 sources) through shape generation on MPS. Measure
  wall-clock, peak memory, and mesh quality/watertightness (does the STL
  slice in a slicer?). Also verify the license actually permits this use.
  Kill criterion: >10 min per mesh or non-printable geometry.
- **M2 — Backend + selector (ends user-testable)**: everything a user
  needs to build a local figure from the UI ships in this phase.
  - `local_figure_generator.py` + `requirements-3d.txt`; pinned weight
    download; `available()`/discovery; mesh cleanup pass (decimate to a
    sane face count, ensure manifold) via trimesh; GLB out.
  - **Figure engine selector in Settings**, mirroring the character-
    generation model selector exactly: a `#settingsFigureEngine` select
    on the Settings page, populated from a new `GET /figure/backends`
    (Meshy listed when its key resolves, local when extras + weights are
    ready), grouped **Cloud / On this Mac** with a status line beneath
    explaining an absent group — same honest-discovery contract as the
    image picker. Persisted client-side (`localStorage`, alongside the
    CG draft) and sent with figure requests; the server validates the
    requested backend against its own availability (ids-not-trust, as
    with image models). Default stays Meshy whenever its key exists.
  - The figure endpoints honor the choice; the local worker reuses
    `_figure_jobs` with stages `preparing → meshing → cleanup → done`,
    writes to `FIGURES_DIR`, gallery-saves worker-side (upsert
    precedent), and renders untextured GLBs in the existing viewer (IBL
    lighting already in place — gray PBR material reads fine).
  - **Exit criterion**: a user can open Settings, pick "On this Mac"
    for figures, and build a printable figure end-to-end — M2 closes
    when that flow is ready for user testing, not before.
- **M3 — Polish from user testing**: whatever M2's testing surfaces,
  plus the known parity items — Claude print report on the local path
  (Meshy-specific stages skip), picker copy with measured timings,
  cleanup-pass tuning against real slicer results, error-path UX (weights
  missing mid-job, memory pressure).

## Enhancements (after M3, in value order)

1. **Texture stage** — the VladimirTalyzin fork claims PBR texturing on
   MPS (+~9 min). If it survives an M1-style spike, add as an optional
   `texturing` stage so viewer models stop being gray.
2. **Local text→figure chain** — one job that runs image generation
   (existing backends, user's choice) then image→3D; fully offline
   figures when paired with a local image model.
3. **Quality tier** — TRELLIS.2-MPS as a second, slower backend once its
   port and license check out; picker copy states the time cost honestly.
4. **Print-readiness pass** — automated manifold/overhang/wall-thickness
   checks folded into the report (the current report is Claude prose;
   this adds measured facts).
5. **Idle unload** — mirror the Comfy watchdog: drop the resident 3D
   pipeline after an hour idle (it's ~4 GB, worth reclaiming).

## Risks, named

- **Texture-on-MPS maturity** — two ports disagree about whether it
  works; that's why texture is an enhancement, not v1.
- **License** — Hunyuan's community license has commercial/territory
  clauses; TRELLIS.2's terms unverified. M1 includes reading them.
- **Port drift** — community forks of a fast-moving upstream; pin
  everything (repo commit, weights revision, torch version).
- **Memory collisions** — a figure job during a Krea 2 render or an 8×
  upscale is three GPU tenants on one 32 GB machine. The job stores are
  separate semaphores today; a shared "one heavy GPU job at a time"
  gate may be warranted once M1 measures real pressure.
