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

# Generation defaults
DEFAULT_STEPS = 20
DEFAULT_GUIDANCE_SCALE = 7.5
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_SEED = -1  # -1 = random
