---
name: bump-prompt
description: Create the next system prompt version from a documented failure, update CHANGELOG and the current pointer. Use only after a failing eval or real-test finding.
---
Inputs: the failing eval id and run directory (or a documented real-test failure), and the intended change.

Steps:
1. Refuse if no failure evidence is given.
2. Read `agent/system-prompt/current.md` for version N; copy `vN.md` to `v(N+1).md`. Never edit an existing version.
3. Edit only the new file, minimally, for the failure.
4. Add a CHANGELOG row: version, date, triggered_by (eval id + run dir), change, expected effect.
5. Write `v(N+1)` into `current.md`.
6. Run `uv run pytest tests/test_evals.py` (checks versions have CHANGELOG rows), then re-run the failing case and `all`.
7. Suggest a commit prefixed `prompt:` containing only prompt files.

Constraints: policies in `agent/policies/` are not prompt versions; do not add rules to the prompt that code already enforces unless the failure shows the model needs them.
