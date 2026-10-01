# Evals

## Why this exists

Round 3 asks for evidence of agent decisions under failure. The local E01–E10 oracle harness was removed with the
AgenticOrg migration (see ADR-011) — the cases below are kept as historical design record, not as a runnable suite.
Live evals are now `docs/agenticorg/evals.md` (L01–L22), run against the platform agent.

## The ten cases (`evals/cases/`, historical)

Historical: the local harness and its run script were removed with the AgenticOrg migration (ADR-011). The inputs
below survive as the regression test set for the platform agent.

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

## Historical harness detail

Removed with the AgenticOrg migration — see ADR-011. The notes that follow describe the removed harness and are kept
for reference only.

- Case schema: `id, name, objective, setup{prompt_version, today, competitors[]}, human_input[], external_state{scenarios[], options}, expected_behaviour[], forbidden_behaviour[], pass_criteria[], failure_evidence`. `human_input` items: `{say}`, `{silence: true}`, `{say, interrupted: true}`, or `{event: {type: window_open|window_end|user_cancel}}`.
- Checks: final_state, state_visited, state_not_visited, field_equals, field_unset, snapshot\_\* , connector_called,
  connector_not_called, assistant_matches, assistant_not_matches, any_assistant_matches, mock_state, no_record_matches.
  Built-in checks: no success claim before CONFIRMED, at most one question per assistant message, CONFIRMED only with
  inventory + payment evidence, charged unit price within ceiling.
- Artifacts: `<run>/` with a decision log, transcript and verdict.

## Live evals

Evals run against the platform agent now: see `docs/agenticorg/evals.md` (L01–L22). The E01–E10 inputs above remain
the regression set to exercise there.
