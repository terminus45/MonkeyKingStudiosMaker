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
PRACTICE_DIR   = os.getenv("PRACTICE_DIR", "./output/practice")
KEYS_FILE      = os.getenv("KEYS_FILE", "./config.json")

# Child-safety guardrail explicitly appended to every Style Prompt used for
# image/model generation. Override via env if needed.
SAFETY_STYLE_SUFFIX = os.getenv(
    "SAFETY_STYLE_SUFFIX",
    " suitable for six year old, nothing scary, nothing violent",
)

# ── Accounts & Credits (Phase 1) ─────────────────────────────────────────────
# All billing config comes from environment only — never from config.json/Settings UI.
# Set BILLING_ENABLED=true to activate the wallet/auth/Stripe subsystem.
# When false (default), no DB is opened, no new routes are registered, and the app
# behaves exactly as without this feature.

BILLING_ENABLED: bool = os.getenv("BILLING_ENABLED", "false").lower() in ("1", "true", "yes")

# SQLite path for local dev (default). Postgres-portable schema.
# Production: set DATABASE_URL=postgres://... (requires asyncpg swap — see billing_db.py).
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./billing.db")

# DEV_AUTH: when True (default when billing on), accepts X-Dev-User / Bearer dev:<id>
# headers instead of real JWT. Set to false only after wiring a real JWT verifier.
DEV_AUTH: bool = os.getenv("DEV_AUTH", "true").lower() in ("1", "true", "yes")

# Stripe secrets — loaded from .env / host secret store ONLY. Never in config.json.
STRIPE_SECRET_KEY:      str = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET:  str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")  # non-secret, for frontend

# Return URLs for Stripe Checkout (must be absolute). Defaults point at localhost.
STRIPE_SUCCESS_URL: str = os.getenv(
    "STRIPE_SUCCESS_URL", "http://localhost:8000/account.html?return=success"
)
STRIPE_CANCEL_URL: str = os.getenv(
    "STRIPE_CANCEL_URL", "http://localhost:8000/account.html?return=cancel"
)
