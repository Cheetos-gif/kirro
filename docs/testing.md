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

### Live runs so far (2026-10-02, agent `4aec1080-fc25-4b0d-bf5a-cc9642fc18be`, via `Chat with Agent`)

Each case run in a fresh conversation. Verdicts are against `docs/agenticorg/evals.md`.

- **L01 — pass.** `Tennis court this Saturday for 2, budget 8 to 10k, ideally 8` →
  *"What is the single maximum you will pay per person? Please provide one number without a range or any ambiguous
  terms."* Ceiling left unresolved, one question, neither 8000 nor 10000 echoed.
- **L02 — pass** (turn 1). `Tennis court for 2 people, any network works` → *"Which date do you want for the tennis
  court booking?"* The vague date is not guessed and event/group size are not re-asked. (Turn 2, "this Saturday",
  not yet run.)
- **L03 — partial.** `Shanivaar ko court chahiye, char log` → *"Which court do you want? Options include tennis and
  badminton."* Correct ambiguity handling: it does not guess and lists both options. **But it replied in English to a
  Hinglish message**, which breaks `agent-spec.md` §3 rule 15 ("Mirror the user's language — English, Hindi, or
  Hinglish"). Prompt-fix candidate.
- **L10 — pass.** `badminton or tennis, whichever` → *"Could you please specify whether you are interested in
  booking a badminton court or a tennis court?"* No guess, one question.

Every reply so far lands around 55–65% confidence and is flagged `HITL`, i.e. under the configured 88% floor. Worth
deciding whether that floor is right for a conversational agent, since it flags ordinary, correct turns.

## Live failures and the changes they triggered (2026-10-02, agent `455907ea-d9eb-4fc2-aecd-e19369febdf8`)

Deeper platform behaviour behind each of these is in `docs/agenticorg/platform-map.md` §10.

| case                      | symptom                                                                                   | cause found                                                                           | change made                                                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| L04 (tool call never ran) | every chat turn escalated `Trigger: chat_policy`, approving did not release the held call | the agent was still in **shadow** maturity; `chat_policy` was a symptom, not a policy | promoted the agent (needs ≥ 20 shadow samples **and** computed accuracy ≥ 0.800, both immutable via API)                             |
| L04 (still failed after)  | *"The amount value is missing"*                                                           | our tool signature required `amount_value`, which the model does not reliably emit    | `create_mandate`/`execute` accept `amount_value` / `amount_paise` / `amount` and an int, numeric string or `{"value": N}`            |
| L04 (mandate too small)   | mandate created with `value: 1200` for an agreed **Rs 1,200** (i.e. Rs 12)                | the model passed rupees where the contract is paise                                   | tool descriptions now state the multiplication rule with a worked example; verified `{"value": 120000}`                              |
| L05 (false success)       | agent said *"you are now in the pool"* without calling `declare_interest`                 | prompt-following: the approval record lists only `create_mandate` for that turn       | `agent-spec.md` §3 steps 9–10 rewritten; **not yet live** — prompts are locked on active agents and cloning needs `agenticorg:admin` |

Connector schema changes do not propagate on redeploy: the registered connector caches the discovered tools, so each
change needs a new connector record plus a relink and a health check, or the agent refuses to run.

## Failure cases to test by hand once credentials exist

Outbound call blocked by handset spam filter; Gnani silence/interruption timeouts; real Hinglish transcription of
"any day"; Pine Labs sandbox mandate creation needing OTP.
