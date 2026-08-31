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

## Phases

### Phase 0 — Krea 2 feasibility spike (gate, no product code)

1. Sizes: DiT + Qwen3VL-4B + VAE in bf16 vs fp8; total working set vs 32 GB
   unified memory. (Qwen3VL-4B alone ≈ 8 GB bf16.)
2. Runtime: does current diffusers load Krea 2 (`from_single_file` or repo
   folder)? If not: is support in diffusers main / a release away / Comfy-only?
3. MPS: bf16 path timing at Turbo's 8 steps — target ≤ 60 s/image (the
   local-gen gate).
4. The LoRA: locate "Realism Engine Krea 2" (v3), confirm license permits
   local use, confirm it applies to Turbo, measure size.
5. **Gate:** all four green → Phase 3 proceeds with Krea 2. Any red → the
   pairing architecture (Phases 1–2) still lands and ships against SDXL
   (the Chinese-style-illustration LoRAs already in `models/LORAs/` are the
   proving pair); Krea 2 waits on upstream.

### Phase 1 — Pairing core (architecture-agnostic; ships alone)

- **Sidecar key** `"loras": [{"file": "<basename in models/LORAs/>", "scale": 0.8}]`.
  Validation per the sidecar rules: basename only (any path separator
  rejected), file must exist under `LORAS_DIR`, `.safetensors` only, scale
  clamped 0–2. Sidecars are server-side trusted config (D3 posture);
  nothing from a request body ever names a LoRA file.
- `_load()` applies declared LoRAs after pipeline construction
  (`load_lora_weights` + `set_adapters`), so the cached pipeline carries
  them; the sidecar checksum already regenerates settings + compat table on
  change, and eviction on model switch already exists.
- **Architecture guard:** a LoRA that fails to load (wrong base family) must
  fail the *load* with a clear error naming the sidecar, not silently
  produce a un-LoRA'd or broken pipeline.
- **Metadata/reproducibility:** `meta["loras"] = [{file, sha256?, scale}]`
  recorded like everything else; regenerate replays via per-call override
  (`loras` joins the explicit-override tier so old recipes beat sidecar
  edits — same invariant, same test).
- Picker: the sidecar `label` already names the pairing ("… + Realism
  Engine"); no new UI.

### Phase 2 — Pairing verification on SDXL (proof, cheap)

Pair `SDXL version of Chinese style illustration model.Pbxg.safetensors`
(already on disk) with an SDXL checkpoint via sidecar; verify: applies
(visible style shift at fixed seed), records in metadata, regenerates
bit-identically, refine-compat table unaffected, absent-LoRA-file fails
loudly at load. This proves the whole pairing machinery independent of the
Krea 2 gate.

### Phase 3 — Krea 2 backend (conditional on Phase 0)

- `kind: "krea2"` joins the family enum end-to-end (dimensions: DiT native
  sizes; refine-compat: krea2 pairs only with krea2; `_dimensions` bucket).
- Pipeline class per Phase 0's answer (diffusers pipeline if it exists;
  otherwise this phase parks until upstream ships — we do NOT hand-roll a
  DiT runner or add ComfyUI as a dependency).
- Folder-repo loading (DiT + text encoder + VAE live as separate files —
  the single-file `.safetensors` discovery gains a declared-folder form:
  a sidecar-only model entry pointing at component files, still ids-not-paths
  from the API's perspective).
- Turbo settings via the existing sidecar tier: `steps: 8`, low guidance,
  `label: "Krea 2 Turbo + Realism Engine"`.

### Phase 4 — Ship the pairing

Download Krea 2 Turbo (bf16 components) + Realism Engine LoRA into place,
write the sidecar, verify the full ladder: generate (~8 steps), metadata
records model+LoRA, regenerate bit-identical, refine within-family, picker
shows one entry. Cost note for the picker label if slower than SDXL Turbo.

---

## Risks, named

- **Krea 2 may simply not be runnable here yet** (diffusers support / 32 GB /
  MPS-fp8). That's why it gates Phase 3 only — Phases 1–2 deliver LoRA
  pairing regardless, on models that work today.
- **LoRA licensing** — Civitai models carry per-model licenses; verify before
  bundling anything into a sidecar we document.
- **Scale defaults matter** — a paired LoRA at the wrong scale is worse than
  none; Phase 4 includes an A/B at fixed seed before freezing the sidecar.
