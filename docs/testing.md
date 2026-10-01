# Testing

## Why this exists

Everything that can be proven offline is proven offline, so a hackathon team can change the agent quickly without keys
or phones.

## What runs

`uv run pytest` runs offline in a few seconds: money parsing, field parsers, state machine guards, allocator
properties, connector contracts (provenance, retry policy, malformed handling), mock server scenarios (including a real
uvicorn thread for timeout/delay), engine safety tests, decision log redaction, eval harness (all ten cases through the
stub), and the Anthropic policy wiring with a fake client. Live API calls are never made by tests.

The six bootstrap proofs: invalid price rejected (`test_money`, `test_engine`), missing field creates no claim
(`test_missing_field_blocks_claim_and_authorisation`), cancellation (`test_user_cancellation_releases_in_order`,
cancel from every pre-CONFIRMED state), no CONFIRMED without external confirmation (`test_state_machine`,
`test_booking_needs_external_confirmation_end_to_end`), duplicate responses create no duplicate action
(`test_duplicate_window_event_creates_no_second_action`, `test_ledger_returns_stored_result_without_second_call`),
malformed responses handled safely (`test_malformed_*`).

## Loop

Eval case -> run -> verdict -> on failure add a row below -> change prompt (new version) or code -> rerun -> before
recording run `all` with the final prompt version. Naming: runs `YYYYMMDD-HHMMSS_p<ver>_E0X_<slug>`, commits
`feat|fix|prompt|eval|docs:`.

## Testing log

Every failed live run goes here.

| date                                    | run id | case | prompt | outcome | evidence path | change made |
| --------------------------------------- | ------ | ---- | ------ | ------- | ------------- | ----------- |
| (none yet: no live runs have been made) |        |      |        |         |               |             |

## Failure cases to test by hand once credentials exist

Outbound call blocked by handset spam filter; Gnani silence/interruption timeouts; real Hinglish transcription of
"any day"; Pine Labs sandbox mandate creation needing OTP.
