# AgenticOrg setup runbook

Order follows ADR-011 §8. Nothing here has been executed yet — this is the instruction sheet for when
implementation starts. Field names for `Register Connector` are confirmed live (2026-10-02); everything else about
the Agent/Workflow builder UI is ADR-011 Risk 2/4 — verify as you go and correct this file in the same change.

## 1. Prerequisites (external, not in our control)

- A Vachana API key: email `speechstack@gnani.ai` (free credits, no card) — needed before step 3.
- A public URL for our mock server (`mock_server/`) — AgenticOrg cannot reach `localhost`. **Deployed and
  verified**: `https://api-kirro.upayan.dev` (k8s Deployment/Service/Ingress in `k8s/`, image built by the repo's CI
  on `main`; `/health`, `/venue/catalogue`, `/allocator/draw` and the declare pool all confirmed over public HTTP).
- Confirm the already-connected `pinelabs_plural` connector's credentials are the ones to use for the real charge
  leg, or whether a separate merchant/sandbox binding is needed for the demo.

## 2. Register Vachana (real, custom connector)

`Dashboard > Connectors > Register Connector`:

| Field               | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Provider            | `Custom / Generic Connector`                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Connector Name      | `vachana_kirro` (must be globally unique in the org — pattern `ActualName_yourRequirement` per the form's own guidance)                                                                                                                                                                                                                                                                                                                                                                                 |
| MCP checkbox        | **Unchecked** unless Risk 2's fallback (an MCP shim) is needed — try unchecked first and verify a usable tool appears before falling back                                                                                                                                                                                                                                                                                                                                                               |
| Base URL            | `https://api.vachana.ai`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Category            | `Comms` (closest fit; `Custom` is the alternative)                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Auth Type           | `Api Key`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Rate Limit (RPM)    | keep **low** — Vachana returned `429 RATE_LIMITED` during verification, so do not assume the 100 default is safe                                                                                                                                                                                                                                                                                                                                                                                        |
| API Key             | the Gnani key (obtained; stored locally only in the gitignored `.env` as `VACHANA_API_KEY_ID`). **Verified working 2026-10-02**: authenticated TTS returned a payload error (`400 "'model' is required"`) while the same call without the key returned `401 MISSING_API_KEY`.                                                                                                                                                                                                                           |
| Extra config (JSON) | if the form requires explicit operation declarations for a non-MCP connector (Risk 2), name exactly: TTS `POST /api/v1/tts/inference`, STT `POST /stt/v3`, realtime STT `wss://api.vachana.ai/stt/v3/stream` — all authenticated by header `X-API-Key-ID` (ADR-012's `docs/connectors.md` has the verified list). Supported TTS model is **`timbre-v2.5`**. Send a conventional `User-Agent`: Cloudflare answers a bare `python-urllib/x` with `403` (error code 1010) before the API sees the request. |

## 3. Confirm Twilio, WhatsApp, Pine Labs are usable as-is

- Twilio: native, already in the catalog (not yet registered in this tenant per the connector-catalog snapshot in
  ADR-010 — register it with real Twilio account credentials if not already done by the time this is implemented).
- WhatsApp: `whatsapp_kirro` already connected and active — reuse, no action.
- Pine Labs: `pinelabs_plural` already connected and active — reuse for the real order/payment-link/refund leg.

## 4. Register the Delhivery mock (mandatory, MCP connector)

Once `mock_server/` is deployed publicly (prerequisite, §1) and trimmed to the 4 surfaces (ADR-011 §2):

| Field          | Value                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------- |
| Provider       | `Custom / Generic Connector`                                                                 |
| Connector Name | `delhivery_mock_kirro`                                                                       |
| MCP checkbox   | **Checked** — tool catalog auto-discovered from the mock server's MCP endpoint               |
| Base URL       | `https://api-kirro.upayan.dev/delhivery/mcp`                                                 |
| Category       | `Ops` or `Custom`                                                                            |
| Auth Type      | `None` (internal mock, no real credentials) unless we choose to gate it with a shared secret |

Expected discovered tools: `pincode_serviceability`, `create_shipment`, `track` (ADR-012).

## 5. Register the 3 budgeted mock capabilities

Same mechanism as §4, each as its own Custom/Generic connector, MCP checked, pointed at the same deployed mock
server's MCP endpoint for its surface (ADR-012):

| Connector Name            | Base URL                                     | Category  | Discovered tools                                                                                                                                            |
| ------------------------- | -------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `venue_inventory_kirro`   | `https://api-kirro.upayan.dev/venue/mcp`     | `Ops`     | `list_releases`, `get_release`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`, `declare_interest`, `list_pool_entries`, `cancel_declaration` |
| `pine_labs_mandate_kirro` | `https://api-kirro.upayan.dev/pinelabs/mcp`  | `Finance` | `create_mandate`, `get_mandate_balance`, `execute`, `release`, `refund`                                                                                     |
| `difd_allocator_kirro`    | `https://api-kirro.upayan.dev/allocator/mcp` | `Ops`     | `draw`                                                                                                                                                      |

Do **not** grant the Declare Agent the `create_hold`/`confirm_booking`/`execute`/`release`/`refund` tools — those
belong to the Window Allocation Workflow (`agent-spec.md` §5 lists its Authorized Tools).

## 6. Build the Kirro Declare Agent

`Dashboard > Agents > Create Agent > Skip to manual setup`, 5 steps — paste from `agent-spec.md`:

1. Persona: Employee Name `Kirro`, Designation `Declared-Interest Booking Agent`, Domain `Ops`.
1. Role: `agent-spec.md` §2.
1. Prompt: `agent-spec.md` §3 (verbatim block).
1. Behavior: `agent-spec.md` §4.
1. Review: select Authorized Tools exactly per `agent-spec.md` §5 — do not grant more than listed (Risk 5).

## 7. Build the Kirro Window Allocation Workflow

`Dashboard > Workflows` (or `client.workflows.create(...)`) from `workflow-spec.md`. Wire the Agent Scheduler
trigger per `workflow-spec.md` §1.

## 8. Environment / secrets needed (by whoever runs implementation, not committed to this repo)

| Secret                                                             | Used for                                                                                            | Where it lives                                                                      |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Vachana API key                                                    | `vachana_kirro` connector auth                                                                      | AgenticOrg connector registration form, not this repo's `.env`                      |
| Twilio account credentials                                         | Twilio connector, if not already bound                                                              | AgenticOrg connector registration (native connector binding, not ours to configure) |
| AgenticOrg platform API key                                        | `client.agents.*` / `client.workflows.*` SDK calls, if any setup is scripted instead of done via UI | environment variable on whatever machine runs the setup script, never committed     |
| Public mock-server deploy credentials (Vercel token or equivalent) | deploying `mock_server/` publicly                                                                   | deploy tooling's own secret store, not this repo                                    |

Nothing above goes in `.env`/`.env.example` in this repo — the mock server needs no vendor credentials, so the
repo's env surface is `MOCK_SERVER_URL` and `MOCK_LOG_DIR` only. The old `agent/core.py` oracle path and the
connector credentials it needed were removed with the migration; `docs/connectors.md`'s "Needs real credentials"
section now covers platform-side config only.

## 9. Demo runbook (once 1–7 are done)

The mock keys its state by the `X-Run-Id` header (ADR-013). If AgenticOrg lets a connector send extra headers, give
the Declare Agent and the Workflow the **same** value; if it does not, both fall back to `default`, which is shared
anyway. Do not configure different run ids for the two sides — they would not see each other's pool.

1. Reset the mock server's state for a clean run (`POST /__admin/reset`, unchanged from today's mock).
1. Call the Kirro Declare Agent's number (or WhatsApp) as a judge/demo user; declare a badminton slot for 4 people
   at a 300/person ceiling, as in historical case E01 (`docs/evals.md`).
1. Confirm the read-back, confirm yes; observe the mandate-hold tool call and the "you're in the pool" message.
1. Trigger the release's `opens_at` (either wait for the real scheduled time or use whatever manual-trigger path
   the Agent Scheduler/Workflow builder exposes for a demo — not yet identified, needs verification during
   implementation).
1. Observe the Window Allocation Workflow run: draw, hold, capture, booking confirm, WhatsApp notification.
1. Pull AgenticOrg's own Audit Log / Observatory for the run as the judge-facing evidence trail (ADR-010/011 open
   question: whether this fully replaces the removed local `logging_/decision_log.py` JSONL as the Q1.2 source, or
   whether both are shown — there is no local JSONL path any more; see ADR-011 §7.6).
