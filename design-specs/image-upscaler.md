# Image Upscaler — 2× / 4× / 8× from the Character Generator

*Planned 2026-09-01. Status: spec — not yet built.*

## What it is

An "🔎 Upscale" action on the active Character Generator image: three buttons
(2× / 4× / 8×) that produce a **new** image at higher resolution via a real
super-resolution model (Real-ESRGAN family), not a resample. Results are new
files with lineage back to the source, saved to the gallery like everything
else. Works on any saved image regardless of which backend generated it —
cloud portraits are valid sources, exactly as they are for Refine.

## UX

- **Placement**: a row in the existing Refine panel area of
  `character_generator.html`, visible when an image is active. Three buttons:
  `2×`, `4×`, `8×`, each captioned with the concrete output size it would
  produce for *this* image ("4× → 3584×4608"), computed client-side from the
  displayed image's natural size. Honest sizes beat abstract factors.
- **Gating**: shown only when `GET /upscale/status` says the engine is ready
  (torch extras + at least one upscaler model on disk). Otherwise the row
  collapses to one line explaining what's missing, linking to Settings —
  same pattern as the Refine panel's "needs an On this Mac model" state.
  Unlike Refine, upscaling does **not** require a local *generation* model to
  be selected; it needs only the upscaler weights.
- **Progress**: job-based (see below), reusing the CG poll/resume machinery
  (`localStorage` job persistence, single-flight guard). An 8× pass may take
  a minute-plus; it must survive navigation like every other long job.
- **Result**: becomes the active image, joins the session strip, and the
  worker gallery-saves it server-side (upsert-by-filename, per the
  generation-job precedent). The card's ⓘ Info shows "↰ View original"
  lineage via `parent_filename` — the same UI Refine results already get.
- **8× warning**: before submitting an 8× job whose output would exceed
  ~40 MP, the client shows the output dimensions and asks for confirmation —
  a 67 MP PNG (SDXL/Krea 2 source at 8×) is a ~100 MB file some mobile
  browsers will not render.

## Engine

- **Models**: Real-ESRGAN weights in **`models/upscalers/`** (gitignored,
  re-downloadable — weights, not user content):
  - `RealESRGAN_x4plus.pth` (~64 MB) — general/photographic.
  - `RealESRGAN_x4plus_anime_6B.pth` (~18 MB) — flat-shaded illustration and
    line art; usually the right choice for this app's output.
  - Optionally `RealESRGAN_x2plus.pth` for a native 2×.
- **Loader**: **`spandrel`** (the maintained model-arch loader ComfyUI and
  chaiNNer use) + the torch already in `requirements-local.txt`. This
  deliberately avoids the abandoned `realesrgan`/`basicsr` packages and their
  torchvision breakage. `spandrel` goes in `requirements-local.txt` — the
  base app stays free of ML deps, and cloud-only installs simply don't get
  the feature (mirrors local generation's posture).
- **Factors**: the 4× model is the workhorse. 2× = one 4× pass downsampled
  (Lanczos) — or the x2 model if present; 8× = two chained 4× passes.
  Deterministic: same input + model + factor → identical output.
- **Tiling**: fixed 512-px tiles with 32-px overlap and feather-blend,
  unconditionally — a 16 MP intermediate does not fit MPS attention-free
  conv memory either, and tiling costs little. (Plain convs, so no
  attention-slicing hazard here — different mechanism entirely.)
- **Residency**: upscaler models are small; load lazily, keep one resident,
  and run under the existing `BoundedSemaphore(1)` discipline — the GPU is
  still not parallel-safe, and an upscale contending with a Krea 2 render
  is exactly the collision the semaphore exists for.

## Choosing the upscaler from the source's own recipe

The point of embedding `mk_meta` in every PNG pays off here: the source
image tells us what made it, and that decides how to upscale it.

Resolution order (first hit wins), implemented server-side in one function:

1. **Per-checkpoint sidecar** — `models/<stem>.json` gains an optional
   `"upscaler": "anime" | "general"` key (validated like every other sidecar
   key; malformed = absent). The user's own judgment about a checkpoint
   outranks any heuristic. Applies when the source's `meta.model_file.name`
   matches a checkpoint we have a sidecar for.
2. **Checkpoint-name heuristic** — mirrors the turbo-name precedent:
   `animagine`/`pony`/`anime`/`toon` in the source's recorded checkpoint
   name → **anime** model.
3. **Kind/backend defaults** —
   - `kind: sd15` or `sdxl` with an illustration-style checkpoint → anime;
     photoreal checkpoints (`cyberrealistic`, `juggernaut`, `realistic`) →
     general.
   - `backend: gemini` (Imagen/Gemini) and `kind: krea2` → **general**:
     their output has photographic texture/gradients even in illustration
     styles, and the anime model flattens it.
4. **No meta at all** (legacy images, uploads) → general model, the safe
   default.

Also derived from the recipe, not just the pixels:

- **Suggested factor**: the UI pre-highlights the factor that lands nearest
  a print-quality target (~3300 px long edge ≈ A4 @ 300 dpi): 8× for an
  SD 1.5 512-base source, 4× for 768–1024 sources, 2× for Krea 2/Imagen
  ~1152 sources. All three stay clickable — this is a default, not a gate.
- **Hires-fix awareness**: a source whose `meta.hires.ran` is true already
  had one Lanczos+img2img pass; note in the ⓘ meta that further upscaling
  is pure SR from here (no behavioral change in v1, recorded for honesty).

The chosen model and why (`"upscaler_choice": {"model": ..., "source": "sidecar|heuristic|default"}`)
goes into the result's meta — debuggability beats magic.

## Backend

- **`upscaler.py`** — new module, `local_generator`'s posture: torch/spandrel
  imported inside functions; `available() -> (bool, reason)`;
  `discover_models()` scans `models/upscalers/` (`.pth`/`.safetensors`,
  ids opaque, no request paths — D3 applies); `upscale(image, factor,
  model_key, on_step)` returns `(PIL.Image, meta)` with per-tile progress
  callbacks driving the job's real progress bar.
- **Routes** (declared before the static mount):
  - `GET /upscale/status` — `{available, reason, models: [...]}` for UI gating.
  - `POST /upscale/job {filename, factor}` — validates factor ∈ {2,4,8} and
    filename via `_resolve_image_path`, resolves the upscaler model
    server-side from the source's embedded meta (section above), submits to
    the shared `_image_jobs` store. Synchronous 400s for bad factor/missing
    file; 503 when the engine isn't available.
  - Status/polling: the existing `GET /generate/status/{job_id}` — same
    store, no new poll endpoint.
- **Result handling**: new uuid filename; meta `{backend: "upscaler",
  parent_filename, upscale: {factor, model, tiles, source_size,
  output_size}, upscaler_choice: {...}, reproducible: false}` —
  `reproducible: false` because 🎲 Regenerate means "re-run the *generation*
  recipe," which this is not (deterministic though it is); lineage lives in
  `parent_filename` like Refine. Worker gallery-saves via
  `_gallery_save_record` (upsert makes the client's save a merge).

## Phases

- **U1 — engine**: `upscaler.py` + spandrel dep + weights acquisition
  (download the two Real-ESRGAN models into `models/upscalers/`); prove
  tile-blend seamlessness and measure MPS timing at 2×/4×/8× on one SD 1.5
  and one SDXL/Krea 2 source. Offline tests: tiling math, factor chaining,
  discovery gating.
- **U2 — recipe-driven choice + API**: the choose-upscaler function (sidecar
  key, heuristics, defaults — pure, unit-testable), routes, job worker,
  meta/lineage, server-side gallery save.
- **U3 — CG UI**: the button row with computed output sizes and suggested
  factor, job persistence/resume, 8×/40 MP confirmation, gating states.
- **U4 (optional, later)**: Upscale action on Gallery cards (same job API —
  the Gallery page doesn't poll, which the server-side save already covers);
  batch-upscale a book's pages before PDF export.

## Risks, named

- **MPS timing unknown** until U1 measures it — chained 8× on a Krea 2
  source is 67 MP of conv output; if it lands in multi-minute territory the
  UI copy must say so (the job machinery already tolerates it).
- **Memory at 8×**: the final assembled float tensor at 67 MP is ~800 MB —
  fine, but assemble on CPU, not MPS, and stream tiles.
- **PNG size**: 8× outputs are ~50–100 MB files in `output/images/`; the
  40 MP confirmation keeps this deliberate. No cleanup mechanism — same
  standing gap as everything else in `output/` (tracked in the backlog).
- **License**: Real-ESRGAN weights are BSD-3 — fine to download, fine to use.
- **Model download**: ~82 MB total from GitHub releases; U1 scripts it, and
  absence degrades to a one-line explanation, never an error.
