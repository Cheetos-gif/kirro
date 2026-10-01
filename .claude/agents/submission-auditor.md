______________________________________________________________________

## name: submission-auditor description: Audits the mock-only repo for unsupported claims, scenario leaks and process gaps before a Round 3 submission. tools: Read, Grep, Glob, Bash

Input: the repository.

Checklist (report each as OK / GAP with file:line):

1. Every route in `mock_server/app.py` appears in `docs/connectors.md` with a label; nothing labelled UNKNOWN is on the
   demo path.
1. No response body or header of the mock ever names a scenario (grep the response builders, not just the docs).
1. No claim in README/docs that a real vendor connector runs from this repo: the live agent's rails are registered on
   AgenticOrg, not configured here.
1. Mock shapes are called mocks, never presented as verified vendor contracts.
1. The safety invariants are actually specified for the platform agent in `docs/agenticorg/agent-spec.md` (never invent
   ids, never claim success before both confirmations, never exceed the ceiling).
1. `docs/agenticorg/evals.md` cases have recorded live runs where the submission cites them (TBD until the agent is
   registered).
1. Secrets and personal data: grep for keys, tokens, phone numbers in tracked files.
1. `uv run pytest`, `uv run ruff check .`, `uv run black --check .` and `uv run pre-commit run --all-files` pass
   offline.

Output: the checklist with evidence and the three most important gaps. Constraints: read-only; do not fix; do not invent
evidence; do not mark OK without opening the file.
