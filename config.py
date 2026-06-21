import os

# Server
# Default to loopback so the API (which is unauthenticated and drives paid
# third-party calls) is not reachable from the LAN out of the box. Set
# HOST=0.0.0.0 to access from another device (e.g. a phone on your network).
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Output
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MESHY_API_KEY  = os.getenv("MESHY_API_KEY", "")
FIGURES_DIR    = os.getenv("FIGURES_DIR", "./output/figures")
PRACTICE_DIR   = os.getenv("PRACTICE_DIR", "./output/practice")
KEYS_FILE      = os.getenv("KEYS_FILE", "./config.json")

# Child-safety guardrail explicitly appended to every Style Prompt used for
# image/model generation. Override via env if needed.
SAFETY_STYLE_SUFFIX = os.getenv(
    "SAFETY_STYLE_SUFFIX",
    " suitable for six year old, nothing scary, nothing violent",
)
