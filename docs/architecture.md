# Architecture

## Why this exists
KIRRO has to be safe with money and honest about external actions while talking to a person in noisy voice
conversations. So the LLM is kept to conversation and legal-action choice; everything verifiable is code.

## Components
- **Engine** (`agent/core.py`): the only orchestrator. Intake (`set_field`, `ask_user`, `confirm_readback`),
  authorisation, post-authorisation events (`window_open`, `window_end`, `user_cancel`), allocation, hold, charge,
  booking, unwinding, fulfilment. Writes a DecisionRecord for every decision.
- **State machine** (`agent/state/machine.py`): transition table plus guards. `transition()` is the only writer of
  `Declaration.state`.
- **Parsers** (`agent/state/fields.py`, `agent/policies/money.py`): turn the user's words into validated values or
  refuse (ambiguous / invalid / absent).
- **Allocator** (`allocator/`): pure function `(slots, bids, release_id, window_open) -> results`.
- **Connectors** (`connectors/`): `ConnectorResult` with provenance. Mock or real by config.
- **Mock server** (`mock_server/`): venue inventory + holds, Pine Labs mandate mock, Delhivery mock, Gnani extract mock.
- **Runners** (`agent/runner/`): `Session` + a Policy. `StubPolicy` is deterministic and offline; `AnthropicPolicy`
  drives the same tools with the Anthropic SDK (default claude-sonnet-5-5).
- **Core API** (`agent/api.py`): thin HTTP wrappers for the platform and Gnani post-call action (scaffold).

## Data flow (happy path)
1. User turn -> `receive_user_turn` -> policy calls `set_field(field, evidence)` -> parser validates -> state updates.
2. When all required fields are set, code asks the read-back. User says yes -> `confirm_readback` -> VALIDATED.
3. `request_authorisation` -> mandate = group_size x max_price (paise) -> AUTHORISED -> WAITING_FOR_WINDOW.
4. `window_open` event -> balance check -> release lookup -> DIFD allocation -> hold -> verify hold alive -> charge
   (<= ceiling x group and <= mandate) -> booking confirmation -> CONFIRMED -> release unused mandate -> CLOSED.
5. Any failure unwinds in order hold -> mandate and tells the user exactly what was and was not confirmed.

## What is deterministic
Everything except wording and choice of the next legal action. See the table in `docs/architecture-plan-v1.md` section 1.

## Prompt layers (`agent/runner/prompt.py`)
1 versioned prompt, 2 policy block, 3 declaration state from code, 4 connector data (fenced), 5 tool results.
Layers 1-3 never contain external text.

## Hosts
The same Engine/tools run (a) locally for evals and (b) behind the Pine Labs platform via the core API. Platform
binding is not done; see `docs/connectors.md`.

## Failure cases
See the mock scenario table in `docs/connectors.md` and the eval cases in `docs/evals.md`.

## How to test
`uv run pytest` (offline) and `scripts/run_eval.sh all`.
