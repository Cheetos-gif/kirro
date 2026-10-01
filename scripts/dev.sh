#!/usr/bin/env bash
# Start the mock server (8081) and KIRRO Core (8080). Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
export MOCK_SERVER_URL="${MOCK_SERVER_URL:-http://localhost:8081}"
uv run uvicorn mock_server.app:app --port 8081 &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do curl -sf localhost:8081/health >/dev/null && break; sleep 0.2; done
uv run uvicorn agent.api:app_factory --factory --port 8080
