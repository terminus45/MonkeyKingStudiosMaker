#!/bin/bash
cd "$(dirname "$0")"

PORT=${PORT:-8000}

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  PORT=${PORT:-8000}
fi

PIDS=$(lsof -ti tcp:"$PORT")
if [ -z "$PIDS" ]; then
  echo "No process found on port $PORT."
  exit 0
fi

kill $PIDS
echo "Stopped BookBuilderBot (port $PORT, PID $PIDS)."
