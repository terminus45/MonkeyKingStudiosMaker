import os

# Server
# Default to loopback so the API (which is unauthenticated and drives paid
# third-party calls) is not reachable from the LAN out of the box. Set
# HOST=0.0.0.0 to access from another device (e.g. a phone on your network).
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Output
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
# Generated/uploaded images are written here (a subfolder of OUTPUT_DIR by
# default). Reads fall back to OUTPUT_DIR too, so images produced before this
# split — and any recovered originals dropped into OUTPUT_DIR — still resolve.
IMAGES_DIR = os.getenv("IMAGES_DIR", os.path.join(OUTPUT_DIR, "images"))

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MESHY_API_KEY  = os.getenv("MESHY_API_KEY", "")
FIGURES_DIR    = os.getenv("FIGURES_DIR", "./output/figures")
PRACTICE_DIR   = os.getenv("PRACTICE_DIR", "./output/practice")
BOOK_PDF_DIR   = os.getenv("BOOK_PDF_DIR", "./output/book_pdfs")
KEYS_FILE      = os.getenv("KEYS_FILE", "./config.json")

# ── Local (on-device) image generation ───────────────────────────────────────
# Optional: only active when the extras in requirements-local.txt are installed
# and LOCAL_MODELS_DIR holds .safetensors checkpoints. See
# design-specs/local-image-generation.md.
#
# Deliberately NOT under OUTPUT_DIR: model weights are large and
# re-downloadable, not the irreplaceable user content that directory holds.
LOCAL_MODELS_DIR = os.getenv("LOCAL_MODELS_DIR", "./models")
# "mps" on Apple silicon, "cuda" on an NVIDIA box, "cpu" as the slow fallback.
# Resolved at call time so an absent torch never breaks import.
LOCAL_DEVICE     = os.getenv("LOCAL_DEVICE", "auto")
LOCAL_STEPS      = int(os.getenv("LOCAL_STEPS", "35"))
LOCAL_GUIDANCE   = float(os.getenv("LOCAL_GUIDANCE", "7.0"))
# Sampler. diffusers' from_single_file default is PNDM — the legacy scheduler,
# which is the weakest of the common choices and does not reward extra steps.
# See local_generator.SAMPLERS for the accepted values.
LOCAL_SAMPLER    = os.getenv("LOCAL_SAMPLER", "dpm++2m_karras")
# ── Hires fix ────────────────────────────────────────────────────────────────
# Generate at the model's native resolution, then upscale and run a short
# img2img pass over it. This is the standard cure for SD 1.5's mangled faces:
# the base pass composes, the second pass redraws detail at a size where a face
# occupies enough pixels to resolve. Set the scale to 1.0 to disable.
LOCAL_HIRES_SCALE   = float(os.getenv("LOCAL_HIRES_SCALE", "1.5"))
# How much the second pass is allowed to change. Low values refine, high
# values re-imagine (and drift from the composition the first pass chose).
LOCAL_HIRES_DENOISE = float(os.getenv("LOCAL_HIRES_DENOISE", "0.40"))
# Ceiling on the upscaled area, which is also what decides *who* gets the pass.
# At 900k: SD 1.5 (512² base) upscales freely to 768² and benefits; SDXL
# (1024² = 1.05 MP base) is already above the ceiling, so the pass is skipped
# rather than run at a size that would add ~85 s to an already slow render.
# SDXL faces resolve on their own — this fix exists for SD 1.5. Raise this to
# opt SDXL in.
LOCAL_HIRES_MAX_PIXELS = int(os.getenv("LOCAL_HIRES_MAX_PIXELS", "900000"))
# Decode the VAE in float32 (SDXL only — its VAE overflows in fp16). This sets
# vae.config.force_upcast so diffusers' own upcast-at-decode path runs; it does
# NOT cast the VAE module, which would disable that path and produce all-black
# images on MPS. Turn off only to reproduce the fp16 artefacts.
LOCAL_VAE_FP32 = os.getenv("LOCAL_VAE_FP32", "1") not in ("0", "false", "False", "")

# Quality-floor negatives composed with whatever the caller sends. Stable
# Diffusion models respond strongly to these; the cloud models have no
# equivalent knob. Set to "" to disable entirely.
#
# Curated against the real CLIP tokenizer, not concatenated from community
# lists: CLIP truncates at 77 tokens and the popular "mega negative" blocks
# measure 100+ — everything past the cut is silently ignored. This set is 60
# tokens, priority-ordered (hands/fingers → limbs → anatomy → face → quality
# → text/watermark), leaving ~15 tokens of headroom for caller additions
# before anything truncates. Near-duplicate embeddings ("extra digit" beside
# "extra fingers", "mutated" beside "deformed") were dropped — they spend
# token budget without adding signal.
#
# Note: at guidance <= 1 (turbo/lightning models) CFG's negative branch is
# off and this string has no effect — anatomy there rides on the checkpoint.
LOCAL_NEGATIVE_PROMPT = os.getenv(
    "LOCAL_NEGATIVE_PROMPT",
    "bad hands, mutated hands, fused fingers, extra fingers, missing fingers, "
    "extra limbs, missing limbs, malformed limbs, bad anatomy, bad proportions, "
    "deformed, disfigured, poorly drawn face, "
    "worst quality, low quality, blurry, watermark, signature, text, cropped",
)

# Child-safety guardrail explicitly appended to every Style Prompt used for
# image/model generation. Override via env if needed.
SAFETY_STYLE_SUFFIX = os.getenv(
    "SAFETY_STYLE_SUFFIX",
    " suitable for six year old, nothing scary, nothing violent",
)
