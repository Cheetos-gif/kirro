# AgenticOrg setup runbook

Order follows ADR-011 §8. Nothing here has been executed yet — this is the instruction sheet for when
implementation starts. Field names for `Register Connector` are confirmed live (2026-10-02); everything else about
the Agent/Workflow builder UI is ADR-011 Risk 2/4 — verify as you go and correct this file in the same change.

## 1. Prerequisites (external, not in our control)

- A Vachana API key: email `speechstack@gnani.ai` (free credits, no card) — needed before step 3.
- A public URL for our mock server (`mock_server/`) once it has the 4 trimmed surfaces (ADR-011 §2) — AgenticOrg
  cannot reach `localhost`. Deploy target not yet chosen; needs a decision (Vercel serverless adapter for FastAPI,
  a small VM, or similar) — out of scope for this doc, flag before step 5.
- Confirm the already-connected `pinelabs_plural` connector's credentials are the ones to use for the real charge
  leg, or whether a separate merchant/sandbox binding is needed for the demo.

## 2. Register Vachana (real, custom connector)

`Dashboard > Connectors > Register Connector`:

| Field | Value |
|---|---|
| Provider | `Custom / Generic Connector` |
| Connector Name | `vachana_kirro` (must be globally unique in the org — pattern `ActualName_yourRequirement` per the form's own guidance) |
| MCP checkbox | **Unchecked** unless Risk 2's fallback (an MCP shim) is needed — try unchecked first and verify a usable tool appears before falling back |
| Base URL | `https://api.vachana.ai` |
| Category | `Comms` (closest fit; `Custom` is the alternative) |
| Auth Type | `Api Key` |
| Rate Limit (RPM) | leave default (100) unless Vachana's docs specify a lower limit |
| API Key | the key from `speechstack@gnani.ai` |
| Extra config (JSON) | if the form requires explicit operation declarations for a non-MCP connector (Risk 2), this is where they'd go — confirm the exact shape live; likely something naming the STT REST path, the WS stream URL (`wss://api.vachana.ai/stt/v3/stream`), and the TTS path, all using header `X-API-Key-ID` |

## 3. Confirm Twilio, WhatsApp, Pine Labs are usable as-is

- Twilio: native, already in the catalog (not yet registered in this tenant per the connector-catalog snapshot in
  ADR-010 — register it with real Twilio account credentials if not already done by the time this is implemented).
- WhatsApp: `whatsapp_kirro` already connected and active — reuse, no action.
- Pine Labs: `pinelabs_plural` already connected and active — reuse for the real order/payment-link/refund leg.

## 4. Register the Delhivery mock (mandatory, MCP connector)

Once `mock_server/` is deployed publicly (prerequisite, §1) and trimmed to the 4 surfaces (ADR-011 §2):

| Field | Value |
|---|---|
| Provider | `Custom / Generic Connector` |
| Connector Name | `delhivery_mock_kirro` |
| MCP checkbox | **Checked** — tool catalog auto-discovered from the mock server's MCP endpoint |
| Base URL | `<public mock server URL>/delhivery` (or the root, depending on how the MCP shim is mounted) |
| Category | `Ops` or `Custom` |
| Auth Type | `None` (internal mock, no real credentials) unless we choose to gate it with a shared secret |

## 5. Register the 3 budgeted mock capabilities

Same mechanism as §4, each as its own Custom/Generic Connector, MCP checked, pointed at the same deployed mock
server's respective route group:

| Connector Name | Base URL suffix | Category |
|---|---|---|
| `venue_inventory_kirro` | `/venue` | `Ops` |
| `pine_labs_mandate_kirro` | `/pinelabs` | `Finance` |
| `difd_allocator_kirro` | `/allocator` | `Ops` |

## 6. Build the Kirro Declare Agent

`Dashboard > Agents > Create Agent > Skip to manual setup`, 5 steps — paste from `agent-spec.md`:
1. Persona: Employee Name `Kirro`, Designation `Declared-Interest Booking Agent`, Domain `Ops`.
2. Role: `agent-spec.md` §2.
3. Prompt: `agent-spec.md` §3 (verbatim block).
4. Behavior: `agent-spec.md` §4.
5. Review: select Authorized Tools exactly per `agent-spec.md` §5 — do not grant more than listed (Risk 5).

## 7. Build the Kirro Window Allocation Workflow

`Dashboard > Workflows` (or `client.workflows.create(...)`) from `workflow-spec.md`. Wire the Agent Scheduler
trigger per `workflow-spec.md` §1.

## 8. Environment / secrets needed (by whoever runs implementation, not committed to this repo)

| Secret | Used for | Where it lives |
|---|---|---|
| Vachana API key | `vachana_kirro` connector auth | AgenticOrg connector registration form, not this repo's `.env` |
| Twilio account credentials | Twilio connector, if not already bound | AgenticOrg connector registration (native connector binding, not ours to configure) |
| AgenticOrg platform API key | `client.agents.*` / `client.workflows.*` SDK calls, if any setup is scripted instead of done via UI | environment variable on whatever machine runs the setup script, never committed |
| Public mock-server deploy credentials (Vercel token or equivalent) | deploying `mock_server/` publicly | deploy tooling's own secret store, not this repo |

Nothing above goes in `.env`/`.env.example` in this repo unless a *local* dev/test path needs it (the existing
`agent/core.py` oracle path already documents its own needs in `docs/connectors.md`'s "Needs real credentials"
section, unchanged by this ADR).

## 9. Demo runbook (once 1–7 are done)

1. Reset the mock server's state for a clean run (`POST /__admin/reset`, unchanged from today's mock).
2. Call the Kirro Declare Agent's number (or WhatsApp) as a judge/demo user; declare a badminton slot for 4 people
   at a 300/person ceiling, as in `evals/cases/E01_happy_path.yaml`.
3. Confirm the read-back, confirm yes; observe the mandate-hold tool call and the "you're in the pool" message.
4. Trigger the release's `opens_at` (either wait for the real scheduled time or use whatever manual-trigger path
   the Agent Scheduler/Workflow builder exposes for a demo — not yet identified, needs verification during
   implementation).
5. Observe the Window Allocation Workflow run: draw, hold, capture, booking confirm, WhatsApp notification.
6. Pull AgenticOrg's own Audit Log / Observatory for the run as the judge-facing evidence trail (ADR-010/011 open
   question: whether this fully replaces `logging_/decision_log.py`'s JSONL for Q1.2 reconstruction, or whether
   both are shown).
