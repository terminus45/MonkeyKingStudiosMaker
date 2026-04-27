#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate venv if present
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "BookBuilderBot → http://localhost:${PORT:-8000}"
uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
