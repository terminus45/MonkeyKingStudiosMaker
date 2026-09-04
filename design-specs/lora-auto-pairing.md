# LoRA Support, Auto-Paired — Build Plan

**Status:** Plan only.
**Goal:** LoRAs that ship *inside* a model choice. The user picks one entry in
the Settings picker — e.g. "Krea 2 Turbo + Realism Engine" — and the LoRA
loads, applies, and is recorded invisibly. The word "LoRA" appears nowhere in
the UI.
**First target (user-directed):** Krea 2 Turbo paired with the
"Realism Engine Krea 2" LoRA.

---

## The UX principle

LoRA support in every other tool (A1111, Comfy) exposes plumbing: pick a
base, pick adapters, set per-adapter weights, mind architecture matching.
This app's audience is a family, and its convention (per-model sidecars,
allow-listed ids, no knobs the image doesn't need) already points the other
way: **a paired LoRA is part of what the model IS**, declared server-side,
applied automatically, reproduced automatically. One picker entry, zero new
controls.

## What was established about Krea 2 (verified 2026-08-31)

- Krea 2 is a **DiT (Diffusion Transformer)** from Krea AI — not SD/SDXL.
  Two variants: **RAW** (base; the one LoRAs are trained against) and
  **Turbo** (8-step distill — the speed profile that fits this app).
- Components: **Qwen3VL-4B** text encoder, **Qwen-Image VAE**, DiT weights.
  Distribution is ComfyUI-first (Comfy-Org repackages, fp8-scaled and bf16
  files; community GGUFs exist).
- Therefore Krea 2 does NOT load through anything in `local_generator.py`
  today: new pipeline, new text encoder, new VAE — a backend phase, exactly
  like the Qwen-Image/FLUX.2 assessment concluded for that family.

**Unverified (interrupted mid-check; Phase 0 resolves):** exact file sizes
and 32 GB fit; whether diffusers ships a Krea 2 pipeline yet or only ComfyUI
runs it; fp8-scaled weights on MPS (no fp8 compute — needs bf16 or dequant);
and the "Realism Engine Krea 2" LoRA itself (likely Civitai; license, size,
and whether it targets RAW or Turbo — LoRAs trained on RAW usually apply to
Turbo, but "usually" is a Phase 0 question).

---

## Phases — v2, reordered 2026-08-31 (Krea 2 first)

> User direction after the Phase 0 spike: get Krea 2 working as a selectable
> model FIRST; LoRA pairing follows. Auth + license are done (verified 200 on
> the gated repo); the ~36 GB diffusers-format download is in flight.

### K1 — Acquire *(in progress)*

`krea/Krea-2-Turbo` diffusers folder → `models/krea2-turbo/` (transformer
shards, Qwen3VL-4B text encoder, VAE, tokenizer, scheduler,
model_index.json). The redundant 26 GB single-file variant is excluded.
Verify shard completeness against the repo manifest before building on it.

### K2 — Backend: the `krea2` kind

- **Folder-model discovery.** `discover_models()` additionally scans
  `models/*/model_index.json`; the directory name becomes the id
  (`local:krea2-turbo`) and the `_class_name` maps to the kind
  (`Krea2Pipeline`/Turbo → `krea2`). Ids-not-paths holds — the API never
  sees a directory, only the id.
- **Loading.** `_load()` branches: folder → `DiffusionPipeline.from_pretrained`
  in bf16. Single-resident-pipeline policy and the GPU semaphore apply
  unchanged. Memory strategy is K4's experiment, in order of preference:
  plain `.to("mps")` (35.7 GB — likely swaps), `enable_model_cpu_offload()`
  (staged residency; on unified memory this bounds peak MPS allocation, not
  total RAM), and freeing the text encoder post-encode.
- **Kind-gates on SD-isms.** `_apply_sampler` no-ops for `krea2` (DiT
  flow-matching scheduler; the SAMPLERS table is SD-specific). Hires pass:
  excluded by kind (native ≥1024). `LOCAL_NEGATIVE_PROMPT`: not sent
  (distilled CFG — Turbo runs guidance ~1, negatives inert).
- **Per-model settings** work off the folder stem (`models/krea2-turbo.json`):
  `steps: 8`, label. `_model_settings` learns folder stems.
- **Unchanged and load-bearing:** seed via CPU generator, metadata capture
  (`kind: "krea2"`), step callbacks → job progress, poison guard,
  regenerate's explicit-override tier.

### K3 — Selectable + honest in the picker

Discovery entry appears in Settings under "On this Mac" with a label that
tells the truth K4 measures (e.g. "Krea 2 Turbo — best quality, ~3 min").
Refine-compat: `krea2` pairs only with `krea2`; diffusers 0.40 has no Krea 2
img2img pipeline, so refine-options returns empty for krea2 images (the
panel already explains empty states) — noted as a follow-up, not a blocker.

### K4 — Gate 3, empirically *(the go/no-go the spike couldn't run)*

First generation answers: does 35.7 GB bf16 run in 32 GB unified memory, at
what s/step, with which memory strategy. Record results here. If it thrashes
unusably, the model stays discovered but the label says so, and the phase
parks — selectable-but-honest beats hidden.

> **PR boundary (2026-09-04):** everything above merged in PR #6 (Krea 2 via
> ComfyUI + upscaler). The L-phases below are the scope of the follow-up PR
> on `feature/lora-pairing`. L3's two gates are unchanged: a Civitai-login
> download, and the explicit content decision recorded under L3.

### L1 — LoRA pairing core *(unchanged design, now after K-phases)*

Sidecar `"loras": [{"file", "scale"}]`, basename-only against
`models/LORAs/`, applied in `_load`, recorded in metadata, replayed through
the explicit-override tier. Loud failure on missing/mismatched files.

### L2 — Pairing proof on SDXL *(cheap, unchanged)*

The Chinese-style-illustration SDXL LoRA already on disk: style shift at
fixed seed, metadata, bit-identical regenerate.

### L3 — Realism Engine on Krea 2

Civitai-login download (user action), sidecar pairing at strength 0.8 with a
fixed-seed A/B before freezing. **The Phase 0 content-safety flag stands:**
the LoRA is NSFW-flagged/uncensored and this is a kids' app with no local
guardrail — pairing it is an explicit product decision recorded here, not a
silent default.

## Risks, named

- **Krea 2 may simply not be runnable here yet** (diffusers support / 32 GB /
  MPS-fp8). That's why it gates Phase 3 only — Phases 1–2 deliver LoRA
  pairing regardless, on models that work today.
- **LoRA licensing** — Civitai models carry per-model licenses; verify before
  bundling anything into a sidecar we document.
- **Scale defaults matter** — a paired LoRA at the wrong scale is worse than
  none; Phase 4 includes an A/B at fixed seed before freezing the sidecar.

---

## Phase 0 results — 2026-08-31

### Gate 1 — diffusers support: ✅ GREEN (better than assumed)

`diffusers 0.40.0` (installed) ships `Krea2Pipeline`, `Krea2Transformer2DModel`
and Turbo modular variants; `transformers 5.16.1` has Qwen3VL. No upstream
wait. Pipeline components: scheduler, vae, text_encoder (Qwen3VL-4B),
tokenizer, transformer, with `is_distilled` for Turbo.

### Gate 2 — acquisition: 🟡 BLOCKED ON USER ACTION

- The official diffusers-format repos (`krea/Krea-2-Turbo`, `-Raw`) are
  **gated** (auto-approved, but require an HF account, license acceptance on
  the model page, and `hf auth login` on this machine — none present).
- The ungated Comfy-Org single-file repackages are **unusable via diffusers**:
  `Krea2Transformer2DModel` has no `from_single_file`, which also rules out
  the community GGUFs. ComfyUI is not becoming a dependency.
- The LoRA (below) is Civitai-login-gated as an NSFW-flagged model.

### Gate 3 — memory: 🟠 AMBER, empirically untestable until gate 2 clears

bf16 totals **35.7 GB** (transformer 26.3 + text encoder 8.9 + VAE 0.5)
against 32 GB unified memory. The only in-budget route is sequential
component use with the text encoder released after encoding — estimated peak
~27–29 GB, knife-edge above OS+app overhead. fp8-scaled files can't enter
through diffusers (no single-file path), and MPS has no fp8 compute anyway.
Expected speed if it fits: ~13B-param DiT ⇒ roughly 20 s/step on this M4 ⇒
**~2.5–3 min/image at Turbo's 8 steps** — Turbo's speed advantage does not
survive this hardware. The definitive fit/thrash test needs the download,
which needs gate 2.

### Gate 4 — the LoRA: ✅ located, with a content-safety flag

"**Realism Engine Ideogram 4 + Krea 2**" (Civitai model 2688234), version
**Krea2 v3.0**, 1.53 GB, base model "Krea 2", recommended strength **+0.8**
(range 0.5–1.0). License permits local + commercial use.
**⚠️ The model is NSFW-flagged on Civitai and marketed as an uncensored
realism finetune.** This app is built for a six-year-old and the local
generation path carries **no content guardrail** (documented in CLAUDE.md).
Pairing this LoRA invisibly into the Settings picker of a kids' storybook
app is a product decision to make with eyes open, not a default. A
photorealism LoRA without the uncensored branding may fit the app better;
the pairing machinery is identical either way.

### Verdict

**Phase 3 (Krea 2) parks** until the user: accepts the license on
huggingface.co/krea/Krea-2-Turbo while signed in, runs `hf auth login` here,
and (for the LoRA) downloads from Civitai while signed in. After that, one
~36 GB download and a timing run completes gate 3 with real numbers.
**Phases 1–2 proceed now** — the pairing core proves out on the SDXL
Chinese-style-illustration LoRA already on disk, and Krea 2 slots in later
without rework.

---

## K4 results — 2026-08-31: FAIL on this hardware. Krea 2 disabled, not deleted.

Four attempts, one consistent mechanism:

| Attempt | Outcome |
|---|---|
| Job API, cpu-offload (page cache warm) | Load ≤20 s; **denoise healthy at ~5 s/step**; VAE decode wedged 12+ min; killed |
| Standalone, cpu-offload (cold) | Python killed silently by the kernel during load |
| Offload + VAE pinned on MPS | 9+ min in uninterruptible I/O inside a weight `.to()` copy; killed |
| No offload; TE on CPU, transformer+VAE pinned | Wedged in the one-time ~26.8 GB MPS wire; killed at user request |

The DiT itself performs (~5 s/step when resident). The failure is memory: any
strategy touches a ~26 GB transfer or working set, and on a 32 GB machine
running a browser, this server and a dev session, that lands the process in
**uninterruptible page-in (state U) for minutes** — sometimes never
returning. cpu-offload is strictly worse (it repeats the transfer at every
phase boundary; the "12-minute decode" was really the transformer/VAE
staging shuffle). This is not a labelling problem; a model that wedges the
server worker must not be offered.

**Actions taken:** new `disabled: true` sidecar key — the model stays on
disk and internally resolvable, but discovery never offers it. The picker no
longer lists Krea 2. All K2 backend code stays: correct, tested, dormant.

**What would change the verdict:** (a) more unified memory (48 GB+ runs
this trivially); (b) diffusers gaining a quantized (int8/GGUF) load path for
Krea2Transformer2DModel — the community GGUFs exist but nothing in diffusers
can eat them; (c) the out-of-process route (Draw Things / ComfyUI run Krea 2
quantized today) — option B from local-image-generation D1, a real but
separate integration. Re-enabling is deleting one sidecar line.

**Plan consequence:** L-phases (LoRA auto-pairing) proceed on SD/SDXL as
designed — the pairing machinery was always architecture-agnostic. The
"Realism Engine Krea 2" pairing parks with its base model.

## Route C results — 2026-08-31: ✅ WORKING. Krea 2 Turbo is selectable, via ComfyUI.

The user installed ComfyUI (Desktop, port 8001) and chose option (c) from the
K4 verdict. `comfy_generator.py` is the integration: stdlib-only HTTP client
that submits the official Krea-2 Turbo API graph (`CLIPLoader type="krea2"`,
KSampler 8 steps / cfg 1.0 / euler / simple, `ConditioningZeroOut` negative)
to a local ComfyUI, polls `/history`, fetches the PNG via `/view`. Discovery
offers `comfy:krea2-turbo` only when Comfy is up **and** every required file
is present; an unreachable Comfy can never break the registry or the app.

**DiT variant findings (empirical, on MPS):**

| Variant | Size | Outcome |
|---|---|---|
| int8 (Civitai "OfficialComfy") | 13 GB | ❌ `aten::_int_mm` has no MPS kernels (comfy_kitchen int8 matmul) |
| fp8_scaled (Comfy-Org) | 13 GB | ❌ `Float8_e4m3fn` dtype unsupported on the MPS backend |
| **bf16 (Comfy-Org)** | 26.3 GB | ✅ loads fully (24.4 GB resident), renders correctly |

`_KREA2_DIT_CANDIDATES` prefers bf16; the quantized files stay listed as
fallbacks for non-Mac hosts.

**Measured, first successful render (M4 / 32 GB, seed 42, 896×1152):**
cold render **18 min 13 s** — ~2 min model load + 8 steps at 44→134 s/step
(slowing as memory pressure builds) + VAE decode. Output quality is visibly
above our SD/SDXL checkpoints: clean linework, correct anatomy, strong
prompt adherence. Full app pipeline verified: job API → comfy backend →
PNG saved with embedded `mk_meta` (backend/model_file/seed/prompt_final,
`reproducible: true`) — pixel-identical to Comfy's own output. A repeat
submission with the identical recipe returns in ~2 s from ComfyUI's
execution cache while the model is resident.

**Operational notes:** `COMFY_TIMEOUT_S` default raised 900→2400 (the first
attempt timed out at 900 s on a render Comfy went on to finish); picker label
says "very slow (~15+ min)" — Krea 2 is a one-off portrait tool here, not a
book-pipeline default. A ComfyUI-Manager restart mid-job kills the render
(job errors at timeout); don't install custom nodes while a render runs.
Progress is coarse (0→done); Comfy's websocket would give per-step events —
noted follow-up. The in-process K2/diffusers path stays dormant behind its
`disabled: true` sidecar.

**Plan consequence:** L3's Realism Engine pairing has its hook — the official
template's `LoraLoaderModelOnly` node (strength 0.8) slots between UNETLoader
and KSampler. L1/L2 (sidecar `loras` key, SDXL proof) proceed as designed.

### Idle unload — 2026-09-01

A resident Krea 2 is 24.4 GB the rest of the machine feels (upscales and SD
renders measurably crawl beside it). `comfy_generator` now runs an idle
watchdog: every generation marks activity, and after `COMFY_IDLE_UNLOAD_S`
(default 3600 s; 0 disables) with no generation through this backend it
POSTs Comfy's `/free {"unload_models": true}`. Conservative by design — a
non-empty Comfy queue (a GUI render counts) defers the unload; an
unreachable Comfy counts as freed; the freed flag prevents repeat POSTs.
Only `unload_models` is sent, so Comfy's execution cache survives and an
identical re-prompt still returns in seconds; the next *new* prompt pays
the normal ~2 min reload. The idle clock runs from render end.
