# ADR-010: AgenticOrg platform scope, Vachana over Inya, mock-capability budget

Status: accepted (2026-10-02)

## Context

The competition requires KIRRO to run as a Virtual Employee on Pine Labs' own agent platform
(`agenticorg.hackathon.pinelabs.com`, product name "AgenticOrg"), not as a standalone FastAPI service judges reach
directly. The platform's brief, as given to us, is explicit and binding:

- The agent runs and decides inside the platform; it talks to the outside world only through registered connectors.
- Gnani must be a registered connector; the agent calls its speech-to-text and text-to-speech APIs — every voice
  input and reply goes through it.
- Delhivery is mocked: host our own API server and register it as a custom connector, using endpoints named and
  shaped exactly like Delhivery's documentation (same request/response fields).
- Pine Labs: use the platform's working Pine Labs connector wherever it covers what we need; mock only the parts it
  doesn't, the same way as Delhivery.
- Up to 3 capabilities that Gnani, Pine Labs, or Delhivery don't offer today may also live on our mock server.
- Every other connector must be the real tool (WhatsApp, Gmail, etc.); a team member may play "the user" on the
  other end, but only through an actual tool, never a stub.
- Outside-world inputs (e.g. a bank SMS) are routed through a real tool (e.g. forwarded to the agent's Gmail).
- The mock server must behave like the real one: varied responses, including realistic failures (no rider/slot,
  insufficient balance, timeout, malformed reply), and the agent must handle all of them.

ADR-005 treated the AgenticOrg tenant's capabilities as unknown and deferred platform binding. They are no longer
unknown: the tenant was inspected live (browser relay, authenticated as the account owner) on 2026-10-02. This ADR
supersedes ADR-005's context and records what was found plus the resulting decisions.

### Platform capability inventory (verified live, 2026-10-02)

- **Agent creation**: `Dashboard > Agents > Create Agent` opens a "Create Virtual Employee" flow — either a
  free-text generator (`Describe the employee you need`, backed by `client.agents.generate(...)` /
  `client.workflows.generate(...)` in the SDK) or `Skip to manual setup`, a 5-step wizard: **Persona** (name,
  designation, domain) **-> Role -> Prompt -> Behavior -> Review**. There is also `Create from SOP` and
  `Agent Templates` (Buyer/Seller type, domain, prompt template, a flat **Authorized Tools** checklist spanning
  every connector's tools — this is the platform's only tool-permission primitive; it is per-agent and static, not
  per-state, so KIRRO's `allowed_actions(state)` gating still has to live in our own prompt/behavior/code, not in
  the platform's ACL).
- **Connector catalog**: 101 native connectors (`Dashboard > Connectors > Marketplace`). Confirmed present:
  **Twilio** (`comms`: `make_call, send_sms, send_whatsapp, get_recordings, get_message_status`), **WhatsApp**,
  **Gmail**, **Pine Labs (Plural)** (`create_order, create_payment_link, get_order_status, get_payout_analytics,
  get_settlement_report, initiate_refund` — already registered and active in this tenant as `pinelabs_plural`),
  **Pinelabs Online payment** (QR create/status/cancel, not yet registered). Confirmed **absent**: Gnani, Vachana,
  Delhivery, Exotel, Telegram, Google Sheets. Nothing in the catalog models a time-boxed inventory hold, a
  payment mandate (authorize-then-capture-then-release), or a fair-draw allocation — closest neighbours
  (`Restaurant Reservation`, `Easemytrip Flights`) are plain CRUD with no hold-queue or mandate semantics.
- **Custom/mock connector registration**: `Dashboard > Connectors > Register Connector`, provider
  "Custom / Generic Connector": connector name (must be globally unique in the org), an **MCP checkbox**
  ("this is a Model Context Protocol server; its tool catalog is discovered automatically from the URL below at
  registration time"), Base URL, Category, Auth Type, Rate Limit, API key / secret reference, optional JSON extra
  config. This is the single mechanism used below for Vachana, the Delhivery mock, and the Pine Labs mandate mock.
- **Governance already native to the platform**: `Observatory`, `Approvals`, `Scope Dashboard`, `Enforce Audit`,
  `Audit Log`, `SLA Monitor` pages exist and are populated per-agent. KIRRO's own `logging_/decision_log.py`
  (JSONL DecisionRecord) and the `/log`, `/declarations/{id}/full` dashboard endpoints in `agent/api.py` may
  duplicate what the platform's Audit Log / Observatory already provide for a platform-hosted agent. Not
  reconciled by this ADR — see Open Questions.
- The tenant already has 5 unrelated shadow agents (Vendor Manager, Support Triage, Compliance Guard, IT
  Operations, Contract Intelligence) and 7 connected connectors (`whatsapp_kirro` — active, `META_BUSINESS` auth,
  reusable as-is for the "team member plays the user" channel — plus `tally`, `zoho_books`, `gstn`, `banking_aa`,
  `stripe`, `pinelabs_plural`). No naming conflicts for a new Kirro agent.

## Decision

1. **Voice: Vachana, not Inya `trigger_call`.** Vachana is Gnani.ai's own STT/TTS model line (vachana.ai's
   `og:url` resolves to `inya.ai`; same vendor), with documented REST and WebSocket endpoints
   (`https://api.vachana.ai`, STT stream at `wss://api.vachana.ai/stt/v3/stream`, TTS REST), auth header
   `X-API-Key-ID`, and a reference client (`gnani-vachana` on PyPI, docs at `docs.gnani.ai`). This is a strictly
   better fit for the platform brief's literal wording ("call its speech-to-text and text-to-speech APIs") than
   Inya's `trigger_call` call-orchestration endpoint, which never exposed raw STT/TTS and had a documented gap
   (response-to-conversation-variable mapping marked "Coming Soon", treated as UNKNOWN in
   `docs/architecture-plan-v1.md`). Register Vachana as a **real**, non-MCP Custom/Generic Connector: Base URL
   `https://api.vachana.ai`, Auth Type API Key, header `X-API-Key-ID`.
   Telephony (dialing out, answering in) is **Twilio**, native to the platform — Exotel is not in the catalog and
   is dropped. Twilio carries the call; Vachana turns the audio into text and back, replacing Inya entirely.
2. **Pine Labs**: real, native `pinelabs_plural` connector covers `create_order`, `create_payment_link`,
   `get_order_status`, `get_payout_analytics`, `get_settlement_report`, `initiate_refund`. It has no
   authorize/hold/release primitive — KIRRO's mandate (reserve `group_size x max_price`, hold, capture <= ceiling,
   release unused) is not representable with those six operations. The mandate hold/release step is mocked (one of
   the 3 budgeted capabilities below), fronting whichever of `create_order`/`create_payment_link` actually moves
   money when a hold converts to a charge.
3. **Delhivery**: mocked, mandatory per the brief, registered as an **MCP** Custom/Generic Connector (checkbox on)
   pointing at our own hosted mock server (Vercel or equivalent). Endpoints and field names mirror the documented
   Delhivery Express shapes exactly (`docs/connectors.md`). **Delhivery's mock does not count against the 3-slot
   budget** — the brief's own wording scopes the 3 slots to "capabilities that Gnani, Pine Labs or Delhivery don't
   offer today"; Delhivery's own (mocked) surface is the mandatory baseline, not an extra.
4. **Mock-capability budget: exactly 3**, all load-bearing to the core booking loop, none of which any native
   connector (Vachana, Twilio, Pine Labs, or the other 98 catalog connectors) provides:
   - Venue/slot inventory with a time-boxed hold (`POST .../holds`, `DELETE .../holds/{id}`) — no rail anywhere
     exposes inventory with an expiring claim.
   - Pine Labs mandate hold/release (authorize, balance, capture, release) — see (2).
   - The deterministic fair-draw allocator (DIFD) — KIRRO's own mechanism by design (ADR-002); never an external
     capability.
   **Priority if a stricter reading ever forces a hard global cap of 3 including Delhivery**: drop Delhivery first.
   It is explicitly non-core to the booking loop (ADR-004: "Delhivery is not in the core booking loop"; the primary
   demo recording uses digital inventory and never calls it). The three capabilities above are not droppable —
   without any one of them there is no booking loop.
5. **Everything else stays real**, consistent with the brief: `whatsapp_kirro` (already connected) for the "team
   member plays the user" channel; Gmail for any routed external input (e.g. a forwarded bank SMS) if that need
   arises.

## Consequences

- Supersedes ADR-005's framing ("tenant capabilities are unknown; platform binding is a later, human-verified
  step") — capabilities are now known and binding choices above are made; ADR-005 is marked superseded, not
  deleted.
- `connectors/gnani/` becomes a Vachana client (`api.vachana.ai`, `X-API-Key-ID`) plus a Twilio call leg; the Inya
  `trigger_call`/post-call-action design in `docs/architecture-plan-v1.md` section 8 (Gnani) is no longer the plan
  and should be read as historical, not current.
- `connectors/pine_labs/` keeps its mandate mock (hold/balance/execute/release) but the real charge path now binds
  to AgenticOrg's native `pinelabs_plural` tools, not raw P3P sandbox credentials.
- `mock_server/` scope is fixed at exactly 4 mocked surfaces: venue inventory+hold, Pine Labs mandate hold/release,
  DIFD allocator, Delhivery (mandatory, additional). No fifth mock capability without revising this ADR.
- `config/connectors.yaml` modes and `docs/connectors.md` need updating to match (done in the same change as this
  ADR).

## Open questions (explicitly not decided here)

- Whether KIRRO's existing orchestration (`agent/core.py` Engine, `agent/state/machine.py` guards) keeps running as
  a separate process behind a thin AgenticOrg tool-calling shell, or whether that logic is re-expressed inside the
  AgenticOrg agent's own Prompt/Behavior steps and Workflows. The platform's per-agent tool ACL is static, not
  per-state, so moving the state machine itself onto the platform is not a drop-in change. Needs a human decision
  before any Engine code is touched.
- Whether KIRRO's own decision log (`logging_/decision_log.py`) duplicates or must feed the platform's native
  Audit Log / Observatory / Enforce Audit pages for Q1.2 reconstruction.
