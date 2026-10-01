#!/usr/bin/env bash
# usage: scripts/reconstruct.sh evals/runs/<run>/log.jsonl [--csv]   -> Q1.2 table on stdout
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m logging_.reconstruct "$@"
