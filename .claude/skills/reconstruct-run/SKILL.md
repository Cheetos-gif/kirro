---
name: reconstruct-run
description: Turn a KIRRO decision log into the Round 3 Q1.2 decision table (markdown or csv).
---
Input: a run directory under `evals/runs/` or a `logs/<run_id>.jsonl` path.

Steps:
1. `bash scripts/reconstruct.sh <path>/log.jsonl` (add `--csv` for CSV).
2. Check the table has the columns timestamp, state, input, source, decision, rule, action/message, connector, result.
3. Spot-check three rows against the raw JSONL (state transitions, a connector call, a user message).
4. Save the markdown to `docs/submission/` only if the user asked.

Constraints: output only what is in the log; never fill gaps from memory; the log is already redacted, do not reintroduce phone numbers or keys.
