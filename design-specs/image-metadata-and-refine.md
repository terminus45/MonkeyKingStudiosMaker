# Generation Metadata + Refine Image — Build Plan

**Status:** Plan only — not implemented.
**Depends on:** `design-specs/local-image-generation.md` (Phases 0–5, shipped: dispatcher, local backend, hires fix, job-based generation).

Two features that share one foundation:

1. **Record every generation parameter** with the image, so a result can be reproduced.
2. **Refine Image** — a text box on Character Generator that runs img2img over the displayed image.

---

## The blocking prerequisite: there is no seed

`seed` is hardcoded `-1` in every response (`GenerateResponse`, the job record, the SSE `done` event). It is a leftover from the Stable Diffusion removal. `local_generator.generate()` never constructs a `torch.Generator`, so **every render uses fresh entropy and none is reproducible today.**

Storing metadata is therefore not a storage problem first — it is a generation problem. Phase 1 below adds the seed; nothing about reproduction works until it lands.

**Cloud models cannot be reproduced at all.** Imagen and Gemini expose no seed. The metadata must record this honestly (`reproducible: false`) rather than implying a repeat is possible. This asymmetry should be visible in the UI too — offering "Regenerate identical" on an Imagen image would be a lie.

---

## What must be captured (more than the sketch listed)

To actually reproduce an image, all of this matters. The starred items are the ones easy to overlook:

| Field | Why |
|---|---|
| `seed` | The prerequisite above |
| `model_id`, `backend` | Which checkpoint, which pipeline |
| ★ `model_sha256` (or size+mtime) | A filename is not an identity. `sdXL_v10.safetensors` can be swapped; without a digest, "same model" is an assumption |
| `steps`, `guidance`, `sampler` | The knobs. Sampler especially — this repo's default changed from PNDM to DPM++ 2M Karras and old images predate it |
| `width`, `height` | Derived from aspect ratio via `_dimensions()`, which has already changed once — store the resolved pixels, not the ratio |
| ★ `prompt_final`, `negative_final` | The **composed** strings actually sent, not the user's raw inputs. `LOCAL_NEGATIVE_PROMPT` is env-configurable and the style suffix is backend-dependent; storing only raw inputs means the reproduction drifts when config changes |
| ★ `safety_suffix_applied` | Cloud gets it, local does not — a real difference in the prompt |
| `hires` block | `{ran, scale, denoise, target_w, target_h}`. The saved image is post-hires; reproducing needs both passes |
| ★ `versions` | `{diffusers, torch, app_schema}` — output shifts between library versions, and this is the first thing to check when a repro doesn't match |
| `parent_filename` | Lineage, once Refine exists (see below) |

**Honesty about determinism:** same seed and params on MPS give *visually identical* results in practice, not a bit-exact guarantee across torch versions or hardware. The UI should say "Regenerate" rather than promise an exact duplicate.

---

## Where metadata lives — store it twice, deliberately

The sketch says "add metadata to the image storage". There are three candidates and the right answer is two of them:

| Option | Pros | Cons |
|---|---|---|
| **A. PNG text chunks** (`tEXt`/`iTXt` via Pillow's `PngInfo`) | Travels *with the file* — survives download, re-upload, sharing. The industry convention (A1111/ComfyUI write exactly this) | Not queryable without opening every file |
| **B. `gallery/images.json`** | Already exists, already read by the Gallery, queryable | Only covers gallery-saved images; already 335 records and read whole on every list |
| C. Sidecar `.json` files | Simple | Two files to keep in sync; trivially separated from the image |

**Recommend A + B.** PNG chunks make the image self-describing (a user who downloads a picture keeps its recipe); the manifest makes the Gallery able to show and filter without opening 335 files. C adds nothing the other two don't cover.

`gemini_generator.save_image()` is the single choke point every backend already writes through — that is where the PNG chunk gets written, so no call site needs to change.

**Schema versioning:** put `meta_version: 1` in both. The 335 existing records have no metadata at all and must keep rendering; every consumer needs a null-safe path.

---

## Refine Image

### The good news: the pipeline already exists

`local_generator._img2img_pipe()` was built for the hires fix and does exactly what Refine needs — `AutoPipelineForImage2Image.from_pipe()` reusing the loaded weights at no extra memory. Refine is mostly plumbing, not new machinery.

### Beyond the sketch — five things a plain text box doesn't cover

**1. Strength is the whole game, and a text box has no room for it.** img2img's `strength` decides everything: 0.2 barely touches the image, 0.7 re-imagines it. "It changed too much" and "nothing happened" are the two failure modes, and both are strength problems, not prompt problems. Don't ship a raw 0–1 slider to a six-year-old — offer three buttons:

| Label | strength | Use |
|---|---|---|
| Tweak | 0.25 | Colour, small details, keeps composition |
| Change | 0.45 | Clothing, expression, added objects |
| Reimagine | 0.70 | Same subject, new take |

**2. What is the prompt for the refine pass?** Three options, and this needs a decision: (a) refinement text alone — loses the character description, drifts badly; (b) original + refinement appended — **recommended**, keeps the subject anchored; (c) let the user edit the full prompt — too much for this audience. With (b), the stored `prompt_final` from the metadata *is* the anchor — another reason the metadata work comes first.

**3. Refine must be a job.** It is a full diffusion pass at the same cost as a generation. `POST /generate/job` and its polling/resume already exist; Refine should reuse them rather than reintroduce the long-held-connection fragility just fixed.

**4. Never overwrite the original.** Save the refinement as a new image with `parent_filename` set. Gives free undo, and lineage in the Gallery ("3 refinements of this portrait"). Overwriting would also violate the repo's data-safety posture.

**5. Cloud→local refine is the sleeper feature.** An Imagen portrait can be fed straight into local img2img. Fast, high-quality cloud composition, then unlimited free local refinement. That combination is better than either backend alone and costs nothing extra to support — the img2img pass only needs *an image*, not one it produced.

### UI sketch

Appears in the existing `#cgActionRow`, only when an image is displayed:

```
┌──────────────────────────────────────────┐
│  ✨ Refine this image                     │
│  ┌────────────────────────────────────┐  │
│  │ make the cape blue and add a hat   │  │
│  └────────────────────────────────────┘  │
│  [ Tweak ] [ Change ] [ Reimagine ]      │
└──────────────────────────────────────────┘
```

Progress reuses the existing job polling and step counter. On completion the new image replaces the main frame, joins the session strip, and auto-saves to the gallery like any generation.

**Requires a local model.** If a cloud model is selected the panel should explain that refinement runs on-device and point at Settings, rather than being silently absent.

---

## Dev phases

Each phase is independently shippable and leaves the app working. Phases 1–3 are backend-only and invisible to users; the first user-facing change is Phase 4.

---

### Phase 1 — Seed plumbing *(backend only; unblocks everything)*

**Goal:** every generation has a known, recorded seed.

- `GenerateRequest.seed: int = -1` (`-1` = draw one).
- `local_generator.generate()` builds `torch.Generator(device).manual_seed(seed)`. Resolve `-1` to `random.randint(0, 2**32-1)` **and return the drawn value** — an unrecorded random seed is the same as no seed.
- **The hires pass consumes randomness too.** Seed its generator deterministically from the base seed (e.g. `seed + 1`) so a two-pass render reproduces as a whole.
- Introduce `GenerationResult(image, seed, meta)` as the return type now, with `meta` empty until Phase 2 — one signature change instead of two.
- Surface the seed on `GenerateResponse`, the job record, and the SSE `done` event (all three currently hardcode `-1`).
- Cloud backends return `seed: None`, not a fake number.

**Files:** `local_generator.py`, `image_backends.py`, `main.py` (3 call sites + 2 response shapes)

**Verification:** same seed + params twice → identical output; different seeds → different. Must be an actual generation, not a unit test — the failures in this subsystem have all been runtime-only.

**Ships alone:** yes. "Same seed, change one word" is the core iteration loop and is useful over the API before any UI exists.

---

### Phase 2 — Metadata capture *(backend only)*

**Goal:** assemble the full parameter record. Nothing is stored yet.

- `image_backends.generate()` assembles the dict — it is the only place that knows backend, composed prompt, composed negative, and whether the safety suffix was applied.
- `local_generator` contributes sampler, steps, guidance, resolved w/h, and the hires block.
- **Checkpoint identity:** hashing a 6.9 GB file costs ~7 s. Use cheap identity (`size` + `mtime`) inline, and compute `sha256` lazily, cached to a small sidecar keyed by `(path, size, mtime)`. Never hash on the generation path.
- `versions: {torch, diffusers, meta_version: 1}`.
- `reproducible: bool` — false for cloud, decided here rather than inferred by every consumer later.

**Files:** `image_backends.py`, `local_generator.py`, new `model_digest.py`

**Verification:** unit tests on dict shape; assert `prompt_final` equals what the pipeline actually received (not the raw input).

---

### Phase 3 — Persistence *(backend only)*

**Goal:** metadata survives, in both places.

- PNG `tEXt`/`iTXt` chunks via Pillow's `PngInfo`, written in `save_image()` — the single choke point all three backends already use, so no call site changes.
- `read_image_metadata(filename)` helper + `GET /image/{filename}/meta`.
- `GalleryImageRequest.meta` optional; manifest records carry it.
- **Null-safety pass:** the 335 existing records have no metadata and must keep listing and rendering.

**Files:** `gemini_generator.py` (`save_image`), `main.py`, `frontend/gallery.js`

**Verification:** round-trip — generate, reopen the PNG, compare chunks to the manifest. Confirm the Gallery still lists all 335 legacy records.

---

### Phase 4 — Surface it *(first user-visible phase)*

- Gallery card **ⓘ Info** panel: model, seed, sampler, steps, size, prompt.
- **Regenerate** action, shown only when `reproducible` is true — never offered on cloud images.
- Character Generator shows the seed beneath the image.
- Legacy images show "No generation details recorded" rather than a broken panel.

**Files:** `frontend/gallery.{js,css,html}`, `frontend/character_generator.js`

**Verification:** in-browser, including a legacy record with no metadata.

---

### Phase 5 — Refine Image *(the requested feature)*

- `POST /refine/job` → `{filename, instruction, strength}`, reusing the Phase-1 job store, polling, and `localStorage` resume from local-image-generation Phase 3. Source resolved via `_resolve_image_path`, so a cloud-generated image is a valid input.
- Prompt = stored `prompt_final` + `", "` + instruction, falling back to the gallery `prompt` when metadata is absent (legacy images stay refinable).
- Uses `local_generator._img2img_pipe()` — already built for the hires fix.
- New image saved with `parent_filename` and its own metadata, including a `refine: {instruction, strength, parent}` block. **Never overwrites.**
- CG panel in `#cgActionRow`: text box + Tweak / Change / Reimagine.
- Requires a local model; if a cloud model is selected, explain and link to Settings.

**Files:** `local_generator.py`, `main.py`, `frontend/character_generator.{js,html}`, `frontend/character_generator.css`

**Verification:** refine a local image; refine a *cloud* image (the hybrid path); refine a refinement (lineage depth 2); navigate away mid-refine and confirm resume.

---

### Phase 6 — Follow-ups *(optional)*

Lineage/undo view in the Gallery · "lock seed" toggle in CG · batch-of-4 variations from one seed · Settings toggle to omit prompts from PNG chunks before sharing · Gallery cleanup UI for the storage growth refine causes.

---

### Sequencing

```
1 Seed ──▶ 2 Capture ──▶ 3 Persist ──▶ 4 Surface
                              └────────▶ 5 Refine
```

Phase 5 needs 1–3 but not 4. If Refine is the priority, 1 → 2 → 3 → 5 is the shortest path and Phase 4 can follow. Phases 1–3 are each a session's work; 4 and 5 are larger because they touch the frontend.

---

## Risks

- **Storage growth.** Every refine is a new PNG (~1–2 MB). A dozen iterations on one character is ~20 MB. `output/images/` is gitignored user content that must never be auto-pruned (see CLAUDE.md data-safety rules) — so this needs a *visible* Gallery cleanup UI, not a background sweeper.
- **The hires pass consumes randomness.** Reproduction must seed both passes, not just the base one. Simplest correct approach: derive the second pass's generator from the same seed deterministically.
- **Prompt drift via config.** If `LOCAL_NEGATIVE_PROMPT` changes in `.env`, an old image's stored `negative_final` still reproduces correctly — but only because it was stored composed. This is the concrete reason for the ★ on that row.
- **PNG metadata is not private.** Prompts get embedded in files a user may share. Worth a Settings toggle before this is ever more than a local single-user app.
