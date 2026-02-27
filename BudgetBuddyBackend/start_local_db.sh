#!/usr/bin/env bash
# Start the Google Cloud Datastore emulator for local development.
# Data is ephemeral (not persisted to disk).
#
# Usage:
#   bash start_local_db.sh
#
# Then in another terminal, set USE_LOCAL_DB=true in .env and run:
#   python main.py

set -euo pipefail

PORT="${DATASTORE_EMULATOR_PORT:-8081}"

echo "Starting Datastore emulator on port $PORT (ephemeral, no data persisted)..."
exec gcloud beta emulators datastore start \
    --project=budgetbuddy-local \
    --host-port="localhost:$PORT" \
    --no-store-on-disk
