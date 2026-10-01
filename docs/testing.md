# Testing

## Why this exists

Everything that can be proven offline is proven offline, so the mock services the AgenticOrg-hosted agent calls stay
trustworthy without keys, network or phones. The agent's own behaviour is tested on the platform — see
`docs/agenticorg/evals.md`.

## What runs

`uv run pytest` runs offline in a few seconds and covers exactly two things:

- **Mock-server scenarios** (`tests/test_mock_server.py`): the whole scenario table, idempotency and replay, isolated
  runs, the declared-interest pool round trip, the Delhivery shapes, request/response logging, and the timeout/delay
  scenarios driven through a real `uvicorn` thread over real HTTP so the client timeout path is genuinely exercised.
  It also asserts that no response ever names a scenario, and that a bad scenario is rejected.
- **Allocator properties** (`tests/test_allocator.py`): determinism and input-order independence, capacity respected,
  ceiling respected with UNALLOCATED when nothing fits, min-group partial rules, time constraints as a hard filter,
  one win per user per release, speed buying nothing, and the seed/weights being reproducible.

There is no LLM in the test suite and no code in this repo that makes one. Live API calls are never made by tests.

## Loop

Mock behaviour change -> update `tests/test_mock_server.py` and `docs/connectors.md` in the same change. The agent's
behaviour loop lives on AgenticOrg: eval case -> run -> verdict -> on failure record it below and change the agent's
Prompt/Behavior configuration.

## Testing log

Every failed run against the live agent goes here. The first live run is recorded too, for the baseline.

Channel: `Chat with Agent` (the agent page), agent `Kirro` id `4aec1080-fc25-4b0d-bf5a-cc9642fc18be`, shadow, one
aggregate MCP connector (`mcp_kirro_all`), four authorized tools.

| date       | agent id                               | case | prompt                                     | outcome                                                                      | evidence                                                 | change made |
| ---------- | -------------------------------------- | ---- | ------------------------------------------ | ---------------------------------------------------------------------------- | -------------------------------------------------------- | ----------- |
| 2026-10-02 | `4aec1080-fc25-4b0d-bf5a-cc9642fc18be` | L01  | v0 (prompt pasted from `agent-spec.md` §3) | **pass** — asked for a single maximum per person, did not echo 8000 or 10000 | `docs/agenticorg/platform-map.md` §8 (chat reply quoted) | none needed |

## Failure cases to test by hand once credentials exist

Outbound call blocked by handset spam filter; Gnani silence/interruption timeouts; real Hinglish transcription of
"any day"; Pine Labs sandbox mandate creation needing OTP.
