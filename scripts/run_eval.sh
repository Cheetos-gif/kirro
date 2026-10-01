#!/usr/bin/env bash
# usage: scripts/run_eval.sh E01|all [--mode offline|live] [--mock-url URL] [--prompt-version vN]
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
exec uv run python -m evals.harness "$@"
