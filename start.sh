#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate venv if present
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

# Load .env if present (handles values with spaces/special chars safely).
# Tighten its permissions first — it holds API keys.
if [ -f .env ]; then
  chmod 600 .env 2>/dev/null || true
  set -a
  . ./.env
  set +a
fi

echo "BookBuilderBot → http://localhost:${PORT:-8000}"
uvicorn main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" --reload
