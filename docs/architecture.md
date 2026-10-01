# Architecture

## Why this exists

KIRRO has to be safe with money and honest about external actions while talking to a person in noisy voice
conversations. The decision-making brain now runs as an AgenticOrg Virtual Employee
(`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md`); this repo keeps the mock services it calls and the
written spec that defines the behaviour.

## Components

- **Allocator** (`allocator/`): pure function `(slots, bids, release_id, window_open) -> results`. The DIFD seeded
  fair draw — the reference the mock server's `/allocator/draw` transcribes.
- **Mock server** (`mock_server/`): FastAPI app on :8081. Surfaces: `/venue/*` (catalogue, releases, holds,
  bookings, declared-interest pool), `/pinelabs/*` (mandate create/balance/execute/release, refunds),
  `/allocator/draw` (DIFD), `/delhivery/*` (serviceability, order create, tracking), `/health`, and the out-of-band
  `/__admin/*` control surface. Per-run state in `mock_server/state.py`.
- **Redaction** (`logging_/redact.py`): strips keys, tokens and phone numbers (last 4 only) before anything is
  written to the mock request log.
- **Spec** (`docs/agenticorg/`, `docs/decisions/`): the agent's Prompt/Behavior rules, the scheduled workflow, the
  runbook, the live eval cases, and the ADRs.
- **Engine**: Removed with the AgenticOrg migration — see ADR-011.
- **State machine**: Removed with the AgenticOrg migration — see ADR-011.
- **Parsers**: Removed with the AgenticOrg migration — see ADR-011.
- **Connectors**: Removed with the AgenticOrg migration — see ADR-011.
- **Runners**: Removed with the AgenticOrg migration — see ADR-011.
- **Core API**: Removed with the AgenticOrg migration — see ADR-011.

## Data flow (happy path)

Removed with the AgenticOrg migration — see ADR-011.

1. User turn -> `receive_user_turn` -> policy calls `set_field(field, evidence)` -> parser validates -> state updates.
1. When all required fields are set, code asks the read-back. User says yes -> `confirm_readback` -> VALIDATED.
1. `request_authorisation` -> mandate = group_size x max_price (paise) -> AUTHORISED -> WAITING_FOR_WINDOW.
1. `window_open` event -> balance check -> release lookup -> DIFD allocation -> hold -> verify hold alive -> charge
   (\<= ceiling x group and \<= mandate) -> booking confirmation -> CONFIRMED -> release unused mandate -> CLOSED.
1. Any failure unwinds in order hold -> mandate and tells the user exactly what was and was not confirmed.

## What is deterministic

Everything except wording and choice of the next legal action. See the table in `docs/architecture-plan-v1.md` section 1.
On AgenticOrg, the deterministic parsing/allocation logic is now the platform agent's Prompt/Behavior rules plus the
mock's connector-side validation; see `docs/agenticorg/agent-spec.md`.

## Prompt layers

Removed with the AgenticOrg migration — see ADR-011.

The five-layer prompt assembly was: 1 versioned prompt, 2 policy block, 3 declaration state from code, 4 connector
data (fenced), 5 tool results. Layers 1-3 never contained external text. The platform agent's Prompt/Behavior
configuration now plays this role (`docs/agenticorg/agent-spec.md`).

## Hosts

The same Engine/tools were designed to run (a) locally for evals and (b) behind the Pine Labs AgenticOrg platform via
the core API. Removed with the AgenticOrg migration — see ADR-011. The AgenticOrg tenant itself was inspected live on
2026-10-02 (connector catalog, custom/MCP connector registration, governance pages) — platform capabilities are
documented facts now, not unknowns; see
`docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md`. The move is decided by ADR-011: the agent's
Prompt/Behavior configuration and a scheduled Workflow are the sole decision-maker, and this repo hosts the mock
connectors they call. Real rails bind to AgenticOrg's native connectors (Twilio for the call leg, `pinelabs_plural`
for orders/payment-links/refunds) and to Vachana (Gnani.ai STT/TTS) as a custom-registered real connector; Delhivery
and the three budgeted mock capabilities are hosted by us and registered on AgenticOrg as custom/MCP connectors.

## Failure cases

See the mock scenario table in `docs/connectors.md` and the historical local eval cases in `docs/evals.md`. Live
evals run against the platform and are documented in `docs/agenticorg/evals.md`.

## How to test

`uv run pytest` (offline) covers the mock server scenarios and the allocator properties. The agent's behaviour is
tested on the platform — see `docs/agenticorg/evals.md`.
