---
name: run-evals
description: Run one or all KIRRO eval cases, summarise verdicts, and append failures to docs/testing.md. Use when asked to run or re-run evals.
---
Inputs: case id (E01..E10 or all), mode (offline default, live only if ANTHROPIC_API_KEY is set and the user wants real model results), optional prompt version.

Steps:
1. `bash scripts/run_eval.sh <case> [--mode live] [--prompt-version vN]`.
2. Read each failing run's `verdict.json` and `transcript.md`; open `log.jsonl` around the failing decision.
3. Report PASS/FAIL per case with the run directory.
4. For each failing LIVE run append a row to the testing log in `docs/testing.md` (date, run id, case, prompt, outcome, evidence path, change planned). Do not log offline failures there unless they show a code bug.

Outputs: summary table, paths, testing-log rows. Constraints: do not edit prompts or cases to make a run pass; do not present an offline pass as evidence about a prompt; never print secrets.
