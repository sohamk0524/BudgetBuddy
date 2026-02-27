#!/usr/bin/env bash
# Gracefully stop the local Datastore emulator.
#
# Usage:
#   bash stop_local_db.sh

set -euo pipefail

PORT="${DATASTORE_EMULATOR_PORT:-8081}"

echo "Shutting down Datastore emulator on port $PORT..."
curl -s -X POST "http://localhost:$PORT/shutdown" && echo "Emulator stopped." || {
    echo "Shutdown endpoint failed. Killing process on port $PORT..."
    PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill "$PID"
        echo "Killed PID $PID."
    else
        echo "No process found on port $PORT."
    fi
}
