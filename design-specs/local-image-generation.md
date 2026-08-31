# Local Image Generation — Build Plan

**Status:** Phases 0–5 built and verified (dispatcher, local backend, quality fixes, job-based generation, NaN-poisoning guard); Phase 6 partially built (metadata/refine shipped separately — see `image-metadata-and-refine.md`). **Per-model settings section at the bottom is the current open plan.**
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

### Results — 2026-08-28 (Apple M4, 32 GB, torch 2.13.0, MPS)

Benchmarked at the *wrong* resolutions first, which turned out to be the whole story:

| Checkpoint | Size | Steps | Time | Per step | Cold load |
|---|---|---|---|---|---|
| `sdXL_v10` | 1024² | 20 | 91.1 s | 4.56 s | 12.0 s |
| `sdXL_v10` | 1024² | 30 | 132.1 s | 4.40 s | — |
| `dreamshaper_8` (SD 1.5) | 768² | 20 | 102.9 s | 5.15 s | 4.4 s |
| `dreamshaper_8` (SD 1.5) | 768² | 30 | 156.9 s | 5.23 s | — |

SD 1.5 came out *slower per step* than SDXL, which is backwards — its UNet is far smaller. The cause is resolution: 768² is not SD 1.5's native size, and off-native generation on MPS is disproportionately expensive.

**At native resolution the picture inverts.** Through the real endpoint, SD 1.5 at its 512 base (3:4 → 384×512):

- **22.3 s** cold, including the 4.4 s pipeline load
- **8 s** warm, pipeline already resident

**Verdict — the gate is split, not failed:**

- **SD 1.5 at native 512 passes comfortably** (8 s warm vs. the 60 s bar) and is the usable local tier. `_dimensions()` in `local_generator.py` snaps to native size precisely because of this finding.
- **SDXL at 1024 fails** at ~4.4 s/step — 91 s for a single image. Selectable, but not something to default to.

Two consequences:

1. **Local generation is viable for Character Generator one-offs, and not for books.** The book-PDF worker loops over up to 19 images: ~2.5 min at SD 1.5/512, but ~29 min at SDXL/1024 — against the ~10 min Phase 3 assumed. Whether to offer local generation for whole books is a product decision, and the honest answer is probably "not for SDXL".
2. **MLX deserves promotion from Phase 6.** ~4.4 s/step for SDXL on an M4 suggests torch-MPS, not the hardware, is the ceiling. Untried optimisations remain (attention/VAE slicing, fewer steps, torchvision installed).

Quality caveat: SD 1.5 at 384×512 renders faces poorly — the sample generated during this spike had a coherent body and a mangled face. Fine for props and creatures, weak for character portraits, which is exactly what Character Generator is for. Worth an SDXL-quality comparison before recommending a default.

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

---

## Per-model generation settings — plan (2026-08-30)

**Problem.** `LOCAL_STEPS=35 / LOCAL_GUIDANCE=7` are process-wide, but they are
*model* properties, not app properties. A Turbo/Lightning checkpoint
(DreamShaper XL v2 Turbo, now in `./models`) is distilled for ~8 steps at
guidance ~2 — run at 35/7 it produces burned, oversaturated output, and run
correctly it makes every non-turbo model wrong. Global knobs cannot hold both.

**Key enabler already in place:** `generate()`/`refine()` grew per-call
overrides (`steps`, `guidance`, `sampler`, `hires_scale`, `hires_denoise`) for
the regeneration feature. Per-model settings are just a third tier feeding the
same parameters. Precedence, highest first:

1. **Per-request override** — regeneration's stored recipe. Never touched by
   this feature, so old images keep reproducing exactly.
2. **Per-model settings** — this plan.
3. **Env config** (`LOCAL_STEPS` etc.) — unchanged fallback.

### Where settings come from (two sources, merged)

1. **Name heuristic** (zero-config floor): filename containing
   `turbo` / `lightning` / `hyper` (case-insensitive) →
   `{steps: 8, guidance: 2.0}`. Catches the common case with no setup —
   including files a user drops in themselves.
2. **Sidecar JSON** (explicit, wins over the heuristic):
   `<checkpoint-stem>.json` next to the file, e.g.
   `models/dreamshaperXL_v2_turbo.json`:

   ```json
   { "steps": 8, "guidance": 2.0, "sampler": "dpm++2m", "hires_scale": 1.0,
     "label": "DreamShaper XL Turbo — fast SDXL" }
   ```

   Allowed keys only: `steps` (int 1–150), `guidance` (0–30),
   `sampler` (must be in `SAMPLERS`), `hires_scale` (0–4), `hires_denoise`
   (0–1), `label` (str, display only). Unknown keys ignored, values clamped,
   malformed JSON = no sidecar (never fails discovery). No paths, ever —
   same trust model as the checkpoints themselves (whoever can write
   `./models` already controls what gets executed as a model).

### Implementation sketch

- `local_generator._model_settings(model_id) -> dict` — heuristic ∘ sidecar,
  cached per (path, mtime).
- In `generate()`/`refine()`: each `None` override consults
  `_model_settings()` before falling back to env config. One line per knob.
- `discover_models()` folds `label` into the Settings name and appends a
  speed hint (`"~8 steps · fast"`) so the picker shows *why* to choose it.
- `_checkpoints()` ignores `.json` files already (it filters on
  `.safetensors`) — no discovery change needed there.
- Metadata: **no change required.** `meta` records the *effective*
  steps/guidance/sampler, so recipes stay self-contained and regeneration
  keeps overriding per-model settings with the stored values.
- Ship sidecars for the three new checkpoints (turbo one gets 8/2.0; the
  other two get labels only).

### Tests

- Heuristic: `foo_turbo.safetensors` → 8/2.0; `foo.safetensors` → env values.
- Sidecar beats heuristic; malformed sidecar is ignored; out-of-range values
  clamp; `sampler: "not-a-sampler"` is dropped.
- Precedence: explicit `steps=` argument beats both (the regeneration
  guarantee).
- Live: one turbo generation must land in ~30–40 s and record
  `steps: 8, guidance: 2.0` in its metadata.

### Out of scope

Per-model settings in the Settings *UI* (editing sidecars from the browser),
per-model negative prompts, and per-model default aspect ratios — all easy
extensions of the same sidecar schema if wanted later.

### Build plan v2 — expanded 2026-08-30, after the NaN guard and negative-prompt work

The section above stands; this pins down what changed since it was written and
turns it into an implementable sequence.

#### Schema additions since v1

Two keys join the sidecar schema, both motivated by work that landed after v1:

| Key | Type | Why it exists now |
|---|---|---|
| `cache_unsafe` | bool | The NaN-poisoning guard learns a model is cache-unsafe by **wasting one full render**. cyberrealisticPony is *known* bad — a sidecar `"cache_unsafe": true` seeds `_CACHE_UNSAFE` at discovery, so even the first post-restart generation skips the ~3 min black render. The runtime guard stays as the safety net for undeclared models. |
| `negative` | str | Per-model negative *additions* (e.g. Animagine's documented tag-style negatives). Composes in the middle: caller → model → global floor — same truncation logic, user terms still lead. Optional; ship without using it if token budget gets tight. |

One key **changes meaning slightly**: `guidance` for turbo models. The
negative-prompt work established that CFG's negative branch is off at
guidance ≤ 1 — so the turbo sidecar ships `guidance: 2.0` (not 1.0, which some
turbo docs suggest): weak CFG keeps the anatomy negatives *slightly* alive at
nearly the same speed.

#### Sidecars to ship (concrete)

```jsonc
// models/dreamshaperXL_v2_turbo.json
{ "steps": 8, "guidance": 2.0, "sampler": "dpm++2m",
  "label": "DreamShaper XL Turbo — fast SDXL" }
// Karras sigmas misbehave on some turbo distills at very low step counts;
// plain dpm++2m is the safe choice. Verify live before committing to it.

// models/animagineXL_v40.json
{ "steps": 28, "guidance": 6.0,
  "label": "Animagine XL 4.0 — anime / character art" }

// models/juggernautXL_v9.json
{ "steps": 30, "guidance": 5.5,
  "label": "Juggernaut XL v9 — photoreal" }

// models/cyberrealisticPony_v110.json
{ "cache_unsafe": true,
  "label": "CyberRealistic Pony — reloads each run (slow)" }
```

The first three come from each model's published recommendations and must be
**verified live, not trusted** — one generation each, eyeballed, before the
sidecar values are final.

#### Implementation order (each step leaves tests green)

1. **`_model_settings(model_id) -> dict`** in `local_generator.py`.
   Resolution: sidecar (validated, clamped) over name-heuristic over `{}`.
   Cached keyed on `(path, size, mtime)` like the digest cache. A sidecar that
   fails to parse logs once and acts absent — discovery must never break on a
   bad JSON file.
2. **Wire the fallback chain** in `generate()` and `refine()`: each `None`
   override consults `_model_settings()` before env config. `refine()` today
   reads `LOCAL_STEPS`/`LOCAL_GUIDANCE` directly — that's the one real code
   path change beyond one-liners.
3. **Seed `_CACHE_UNSAFE` from sidecars** at discovery time (union with
   runtime learning; never removes a runtime-learned entry).
4. **Surface in the picker**: `discover_models()` uses `label` when present
   and appends a speed hint derived from effective steps × measured s/step
   ("~8 steps · ≈35 s" vs "~35 steps · ≈3 min"). `/models/local/status`
   unchanged.
5. **Ship the four sidecars**, run the live verification below, adjust
   values, freeze.

#### Test matrix (offline, extending test_local_generator.py)

- Heuristic: `x_turbo/`x_Lightning`/`x_HYPER` filenames → 8/2.0; plain → {}.
- Sidecar beats heuristic; partial sidecar merges over heuristic (turbo file
  with only `label` still gets 8/2.0 from the name).
- Validation: out-of-range clamps, wrong types dropped, unknown keys ignored,
  malformed JSON → absent, `sampler` not in SAMPLERS → dropped.
- Precedence: explicit argument beats sidecar beats env (the regeneration
  invariant, tested end-to-end with a stub pipe).
- `cache_unsafe: true` seeds the set at discovery; runtime-learned entries
  survive a re-discovery.
- Sidecar `.json` files do not appear as models in discovery (already true —
  the glob filters `.safetensors` — but pin it with a test).
- meta records *effective* values (existing tests already assert this shape).

#### Live verification (the part that has caught every real bug so far)

1. DreamShaper Turbo via `/generate/job`: lands in **~30–45 s**, metadata
   records `steps: 8, guidance: 2.0, sampler: "dpm++2m"`, output is not
   burned/oversaturated. Then a second generation on the cached pipe (the
   NaN-guard lesson: never certify a pipeline on one run).
2. Animagine + Juggernaut: one generation each at sidecar settings, eyeball.
3. Pony: first generation after a fresh server start must show the reload
   path (~12 s load, no wasted black render) — proving `cache_unsafe`
   seeding works.
4. Regenerate an OLD image (pre-sidecar metadata) of any model that now has a
   sidecar: output must still be bit-identical — the stored recipe must beat
   the new sidecar. **This is the invariant that must not break.**
5. `pytest` full suite; `sdXL_v10` (no sidecar) still generates at env
   defaults, proving the fallback tier intact.

#### Explicitly out of scope (unchanged from v1)

Settings-page sidecar editing, per-model aspect ratios, per-model positive
prompt prefixes (Animagine's "masterpiece" tags — tempting, but positive
prompts belong to the user's own style field).
