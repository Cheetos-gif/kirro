#!/usr/bin/env bash
# Start the mock server on :8081 in the foreground. Ctrl-C stops it.
#
# `--reload` matches Dockerfile.dev, so the native dev flow and the containerised one behave the
# same way: an edit to mock_server/ restarts the server with no manual step. Development only —
# production runs gunicorn from the image's own CMD (ADR-021).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
export MOCK_SERVER_URL="${MOCK_SERVER_URL:-http://localhost:8081}"
uv run uvicorn mock_server.app:app --port 8081 --reload
