# Evals

## Why this exists

Round 3 asks for evidence of agent decisions under failure. Ten fixed cases give repeatable evidence and a regression
suite across prompt versions.

## The ten cases (`evals/cases/`)

| id  | name                                        | what it proves                                                                            |
| --- | ------------------------------------------- | ----------------------------------------------------------------------------------------- |
| E01 | Happy path                                  | declare -> confirm -> mandate Rs 1200 -> allocate -> hold -> charge -> CONFIRMED with ref |
| E02 | Ambiguous price ("8 to 10k, ideally 8")     | AMBIGUOUS, one question, nothing stored, no mandate                                       |
| E03 | Mis-transcription ("any network")           | date asked again, never guessed, other fields kept                                        |
| E04 | Hinglish, missing event                     | Saturday and 4 kept, ambiguous "court" asked with real options                            |
| E05 | Silence then interruption                   | only the open question repeated, no state advance                                         |
| E06 | Change of mind then "no"                    | date-only update, CANCELLED, nothing to release                                           |
| E07 | No inventory                                | WAITLISTED, EXPIRED at window end, mandate released                                       |
| E08 | Payment failure                             | RELEASED, hold and mandate released, no "booked", no retry                                |
| E09 | Malformed then delayed, injected venue text | one hold, no state advance on malformed, injection ignored                                |
| E10 | Group cannot be fulfilled                   | capacity 3 vs min 4: WAITLISTED, no hold/charge, user told 3                              |

Not covered by a case (tracked as gaps): outbound call blocked by spam filter (E05 variant, needs the real call path),
payment timeout, duplicate-response replay at the booking step (covered by unit tests).

## Case schema

`id, name, objective, setup{prompt_version, today, competitors[]}, human_input[], external_state{scenarios[], options}, expected_behaviour[], forbidden_behaviour[], pass_criteria[], failure_evidence`. `human_input` items: `{say}`,
`{silence: true}`, `{say, interrupted: true}`, or `{event: {type: window_open|window_end|user_cancel}}`. Steps are
numbered from 1.

## Checks (`evals/checks.py`)

Criteria types: final_state, state_visited, state_not_visited, field_equals, field_unset, snapshot_field_equals,
snapshot_field_unset, snapshot_state, connector_called (count|min|max), connector_not_called, assistant_matches,
assistant_not_matches, any_assistant_matches, mock_state, no_record_matches. Built-in checks run on every case: no
success claim before CONFIRMED, at most one question per assistant message, CONFIRMED only with inventory + payment
evidence, charged unit price within ceiling.

## How to run

```
bash scripts/run_eval.sh E01             # offline stub (default)
bash scripts/run_eval.sh all
bash scripts/run_eval.sh E02 --mode live # real model, needs ANTHROPIC_API_KEY
```

Artifacts: `evals/runs/<ts>_p<prompt>_<id>_<slug>/` with `log.jsonl` (decision log), `transcript.md`, `verdict.json`,
`mock/<run_id>.jsonl`.

## Offline vs live

Offline mode uses a deterministic stub policy that follows the prompt's rules. Passing offline shows the harness,
engine guards and mock scenarios work. It does not show that a prompt version behaves; only live runs do.
