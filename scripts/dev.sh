#!/usr/bin/env bash
# Start the mock server on :8081 in the foreground. Ctrl-C stops it.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
export MOCK_SERVER_URL="${MOCK_SERVER_URL:-http://localhost:8081}"
uv run uvicorn mock_server.app:app --port 8081
