______________________________________________________________________

## name: submission-auditor description: Audits the repo for unsupported API claims, missing evidence and process gaps before a Round 3 submission. tools: Read, Grep, Glob, Bash

Input: the repository.

Checklist (report each as OK / GAP with file:line):

1. Every endpoint string in `connectors/` and `mock_server/` appears in `docs/connectors.md` with a label; nothing labelled
   UNKNOWN is on the demo path.
1. No claim in README/docs that a real vendor connector works when it returns NOT_CONFIGURED.
1. Every `agent/system-prompt/vN.md` has a CHANGELOG row naming a triggering eval run (v0 excepted).
1. Each of the ten eval cases has at least one run recorded; live runs exist for the ones cited in the submission.
1. `docs/testing.md` lists every failed live run and its change.
1. Secrets and personal data: grep for keys, tokens, phone numbers in tracked files and in kept runs.
1. `uv run pytest`, `uv run ruff check .` and `uv run black --check .` pass offline.
1. Decision log covers Q1.2 fields for the demo run (`scripts/reconstruct.sh`).

Output: the checklist with evidence and the three most important gaps. Constraints: read-only; do not fix; do not invent
evidence; do not mark OK without opening the file.
