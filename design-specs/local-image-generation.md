# Local Image Generation — Build Plan

**Status:** Plan only — not yet designed in detail, not implemented.
**Goal:** Re-introduce on-device image generation as a *selectable option* alongside the Gemini/Imagen cloud models, chosen from the existing Settings model picker.

---

## Context: what was removed, and why

Two commits took this out, and both reasons still apply:

- **`9341b1d`** (2026-06-14) deleted `generator.py` (281 lines: diffusers pipelines, 8 samplers, LoRA discovery, SDXL detection), the `/models` · `/loras` · `/load` endpoints, the eager startup model load, and ~13 SD fields on `GenerateRequest`. Motivation: *"app now boots with no heavy ML deps and no first-run model download."*
- **`7742eab`** (2026-07-19) uninstalled the leftover stack — torch, diffusers, transformers, accelerate, peft plus transitives — as part of a security audit. It cut **41 known CVEs across 11 packages down to 20 across 6**.

**This plan must not simply revert those commits.** Re-adding `torch`/`diffusers` to `requirements.txt` would restore the CVE surface the audit removed and the multi-GB cold-start the app was freed from. The design below keeps local generation entirely optional and lazily loaded, which is already the established convention in this codebase (`google-genai`, `httpx`, and Playwright are all lazily imported so the server starts without them).

### Target hardware

Apple M4 / 32 GB / 272 GB free. SDXL at 1024² via MPS is comfortably in range. This is a single-user, single-GPU machine, which drives the concurrency design in Phase 3.

---

## The three seams

Everything routes through a small number of places:

| Seam | Location | Today |
|---|---|---|
| Sync generate | `main.py:134` | `gemini_generator.generate()` → `save_image()` |
| SSE generate | `main.py:173` | same, emits `{"step":0,"total":1}` then done |
| Book-PDF worker | `main.py:1730` | same, in a loop over pages |
| Model registry | `gemini_generator.py:25` | `GEMINI_MODELS` list |
| Registry endpoint | `main.py:213` | `GET /gemini/models` |
| Settings picker | `settings.js:214` | clears `<select>`, populates from that endpoint |
| Selected model | `localStorage['monkeyking_cg_draft'].model` | read by CG, Book Builder, (and MKS Mobile when built) |

Because the picker is already data-driven and the chosen id already flows everywhere, **the model id is the natural carrier of backend choice**. No new "provider" toggle is needed in the UI — that was the old design (`provider: "sd" | "gemini"`, `main.py` pre-`9341b1d`) and it forced a parallel set of fields on every request.

---

## Cross-cutting decisions (settle before Phase 1)

### D1. How is the local model executed? *(biggest fork)*

| Option | Deps in app venv | Notes |
|---|---|---|
| **A. `diffusers` + `torch` (MPS), lazy-imported, optional extra** | heavy, but opt-in | Closest to the deleted `generator.py`; known-good path; full control. **Recommended.** |
| **B. Out-of-process HTTP (Draw Things / ComfyUI / A1111)** | none | Lowest risk — zero CVE surface added, model management is someone else's problem. Costs a hard dependency on a separate app being installed and running. |
| **C. MLX (`mlx-diffusion`)** | moderate | Fastest on Apple silicon, but a smaller ecosystem and no LoRA parity. Good Phase 6 optimisation, poor Phase 2 foundation. |

Recommend **A**, with the module written behind an interface narrow enough that **B** could be swapped in later without touching the seams.

### D2. Dependencies must stay out of the default install

`requirements.txt` stays as-is. Add `requirements-local.txt` (torch, diffusers, safetensors, accelerate). `local_generator.py` imports them *inside* functions, exactly as `gemini_generator._client()` does with `google-genai`, and raises a clear "not installed — run `pip install -r requirements-local.txt`" error otherwise. The app must boot, and every existing test must pass, with none of it installed.

### D3. Security — do not restore the old model-loading surface

The deleted code has two properties that must **not** come back to an unauthenticated API:

- **`discover_models()` globbed `*.ckpt`.** Loading a `.ckpt` is a pickle deserialisation — arbitrary code execution. **Restrict to `.safetensors` only.**
- **`GenerateRequest` accepted free-text `model_id`, `lora_path`, `lora_path_2`.** Raw filesystem paths from an unauthenticated request body is a path-traversal / arbitrary-file-load primitive. **The API must accept only an opaque id that is looked up in the server-side discovered allow-list.** Never a path.

This is the same class of issue as the `/upload-image` filename validation already in `main.py:858` — follow that precedent. Worth a `cyber-architect` pass on the diff per the workflow in CLAUDE.md.

### D4. Where do model files live?

A new `LOCAL_MODELS_DIR` (default `./models/`, gitignored). **Not** under `output/` — that directory is covered by the data-safety rules in CLAUDE.md, and multi-GB weights are re-downloadable, not irreplaceable. `.safetensors` SDXL checkpoints are ~7 GB each.

---

## Phases

### Phase 0 — Spike and benchmark *(no product code)*

Prove the runtime before committing to it. In a scratch venv, load one SDXL `.safetensors` on MPS and generate at 1024² and at the aspect ratios in `gemini_generator.ASPECT_RATIOS`.

**Measure:** cold pipeline load, warm per-image time at 25/30/40 steps, peak RSS, and output quality against the same prompt through Imagen 4.

**Gate:** if warm generation is worse than ~60 s/image, revisit D1 (MLX or out-of-process) before building anything. Deliverable is a paragraph of numbers, not code.

### Phase 1 — Backend seam *(no local deps; ships safely on its own)*

Introduce the dispatcher and unify the registry. **Behaviour is unchanged** — with no local models present, every path still runs Gemini.

- New `image_backends.py`: `generate(...)` mirroring `gemini_generator.generate()`'s signature, routing on model id → backend.
- Unified registry: each entry gains `"backend": "gemini" | "local"`. `GEMINI_MODELS` stays the cloud half.
- `GET /models` returns the union; keep `GET /gemini/models` as an alias so nothing stale breaks.
- Repoint the three seams (`main.py:134`, `:173`, `:1730`) at the dispatcher.

**Verify:** full `pytest` green, all four cloud models still generate, book-PDF still illustrates, no new dependency installed.

### Phase 2 — `local_generator.py`

Port `git show 9341b1d^:generator.py` as a starting point, but **trim rather than restore**. The old module carried 8 samplers, dual LoRA slots, clip-skip, and SDXL size-sniffing to serve a UI that no longer exists. Start with: discover, load, generate.

- `discover_models()` → `[{id, name, backend: "local"}]`, `.safetensors` only (D3), stable ids.
- `generate(...)` → matches the dispatcher signature; maps aspect ratio → (w, h) buckets, since local pipelines take dimensions and the cloud API takes ratio strings.
- **Pipeline cache:** loading costs 10–30 s and gigabytes. Cache one pipeline in a module global under a lock; a second model id evicts the first. Single-slot, not LRU — 32 GB does not hold two SDXL pipelines comfortably.
- Config additions: `LOCAL_MODELS_DIR`, `DEVICE` (default `mps` on arm64 Darwin else `cpu`), `LOCAL_STEPS`, `LOCAL_GUIDANCE`.

### Phase 3 — Concurrency, progress, and timeouts *(the underestimated phase)*

Cloud generation is network-bound and parallel-safe. Local generation is GPU-bound and is **not**. This phase is why local generation is not a drop-in.

- **Serialise it.** A module-level `BoundedSemaphore(1)` around local generation, mirroring `_BOOK_PDF_SEM` in `main.py`. Concurrent requests queue rather than thrash or OOM.
- **Book-PDF blast radius.** That worker generates up to 19 images in a loop. At ~30 s each that is a ~10-minute `illustrating` stage. Re-check the per-stage timeout, and confirm the existing retry-once-per-page logic doesn't double an already long job.
- **Real SSE progress — a genuine win.** The `{"step": i, "total": N}` protocol already exists in `/generate/stream` but currently emits only `0/1`, because a cloud call is opaque. A local pipeline exposes a per-step callback, so the progress bar can finally be real. Wire `total = steps`.
- **Interaction with `_BOOK_PDF_SEM(2)`:** two concurrent book jobs each wanting the single GPU slot will serialise anyway. Confirm no deadlock, just queueing.

### Phase 4 — Settings UI

Small, because the picker is already dynamic.

- Group the `<select>` with `<optgroup>`: "Cloud" / "On this Mac".
- Label local entries with what actually differs: `"SDXL — $0.00 · ~30s"` against `"Imagen 4 ($0.04/image)"`.
- `GET /models/local/status` → `{available, device, models, reason}` so Settings can explain *why* the section is empty — deps not installed vs. no `.safetensors` found. Render it in the existing `settings-status-chip` pattern.
- Handle the stale-selection case: `settings.js:236` already falls back to Imagen when a stored model id is no longer in the list. Confirm that path covers "user selected a local model, then uninstalled the deps."

### Phase 5 — Docs, tests, and cost framing

- `CLAUDE.md`: local backend, the optional-extra install, `LOCAL_MODELS_DIR`, and the `.safetensors`-only rule.
- `install-MKStudios.md` currently tells readers **not** to install the ML stack — update it to describe the now-deliberate optional path.
- `.env.example`, `API.md` (`/models`, `/models/local/status`).
- Tests: registry union, dispatcher routing by id, allow-list rejection of a path-like model id, and graceful degradation with deps absent. Keep them offline — no test may load a real pipeline.
- Worth a `financials-agent` pass: local is $0 marginal but slower, which changes the default-model recommendation and the Book Builder cost story (19 images/book).

### Phase 6 — Optional follow-ups

LoRA support (re-add deliberately, ids not paths); sampler choice; MLX backend for speed; model download UI.

---

## Recommended sequencing

Phases 0 and 1 are independent and low-risk — **1 is shippable on its own** and leaves the app strictly better factored even if local generation is never finished. The real work is 2 and 3. Phase 4 is genuinely small.

The one thing not to shortcut is **D3**: the deleted code's free-text `model_id`/`lora_path` fields and `.ckpt` loading, on an endpoint with no auth, is remote code execution. Everything else here is a matter of effort; that one is a matter of correctness.
