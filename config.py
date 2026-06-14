import os

# Model configuration
MODEL_ID = os.getenv("MODEL_ID", "runwayml/stable-diffusion-v1-5")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "./models")
LORA_DIR = os.getenv("LORA_DIR", os.path.join(MODEL_CACHE_DIR, "LORAs"))

# Device: "cuda", "mps" (Apple Silicon), or "cpu"
DEVICE = os.getenv("DEVICE", "cpu")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Output
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MESHY_API_KEY  = os.getenv("MESHY_API_KEY", "")
FIGURES_DIR    = os.getenv("FIGURES_DIR", "./output/figures")
KEYS_FILE      = os.getenv("KEYS_FILE", "./config.json")

# Generation defaults
DEFAULT_STEPS = 20
DEFAULT_GUIDANCE_SCALE = 7.5
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_SEED = -1  # -1 = random
