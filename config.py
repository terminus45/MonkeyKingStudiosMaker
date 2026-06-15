import os

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

# Child-safety guardrail explicitly appended to every Style Prompt used for
# image/model generation. Override via env if needed.
SAFETY_STYLE_SUFFIX = os.getenv(
    "SAFETY_STYLE_SUFFIX",
    " suitable for six year old, nothing scary, nothing violent",
)
