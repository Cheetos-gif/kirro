# Connectors

Labels: REAL (verified in vendor docs or package source), DOCUMENTED (in vendor docs, details not verified),
MOCK REQUIRED (competition rule or missing capability), UNKNOWN (not established; not on the demo path).
Verification dates refer to the Opus plan pass (2026-10-01) unless a different source is named.

## Summary

| Connector | Kind in repo | Config mode | Implemented | Label |
|---|---|---|---|---|
| Venue inventory + holds | mock | `venue_inventory: mock` | yes | MOCK REQUIRED (no rail offers time-boxed holds) |
| Pine Labs mandate/charge | mock now, real later | `pine_labs: mock\|real` | mock yes, real NOT_CONFIGURED | REAL (P3P sandbox exists) / mock schemas are MOCK |
| Gnani Inya | real later | `gnani: mock\|real` | extractor yes (deterministic), platform client skeleton | DOCUMENTED |
| Delhivery Express | mock | `delhivery: mock` | yes | MOCK REQUIRED (competition rule); paths DOCUMENTED |
| Delhivery Maps MCP | not built | - | no | REAL per plan (stretch) |

## Pine Labs
- **Verified from package source** (`pinelabs-online-p3p-server-sdk` 1.3.0, import `pinelabs_p3p_server`, inspected from
  the PyPI wheel): server instance methods `create_mandate`, `get_mandate`, `get_mandate_balance`, `revoke_mandate`,
  `capture`, `create_refund`; REST paths `POST /mpp/v1/pre-authorize`, `GET /mpp/v1/authorization/{id}`,
  `GET /mpp/v1/balance`, `POST /mpp/v1/revoke`, `POST /api/pay/v1/refunds/{order_id}`; sandbox base
  `https://pluraluat.v2.pinepg.in`; config needs `clientId`, `clientSecret`, `merchantId`, `paymentGateway`,
  `availablePaymentMethods`. Env names (`PINELABS_CLIENT_ID`, ...) are from the plan, not the package.
- **Correction to the plan**: the client SDK (`pinelabs-online-p3p-client-sdk` 1.3.0) no longer creates mandates; it only
  creates payment tokens bound to a 402 challenge (`client.methods.create_token`). Charging is a two-party flow
  (server challenge -> client token -> server `capture`). The mock's single `execute_charge` call is a simplification.
- **Not implemented** (`connectors/pine_labs/sandbox.py`): needs credentials and the capture flow. UNKNOWN: whether the
  Pine Labs MCP server has a sandbox flag; whether the hackathon tenant exposes a native Pine Labs connector.
- Mock endpoints (MOCK schema, `connectors/mock_schemas.py`): `POST /pinelabs/mandates`, `GET .../{id}/balance`,
  `POST .../{id}/execute`, `POST .../{id}/release`, `POST /pinelabs/payments/{id}/refund`. Names `authorizationId`,
  `Amount(value, currency)`, `RESERVE_PAY` mirror documented names; response bodies are KIRRO mock shapes.

## Gnani
- DOCUMENTED: Inya base `https://api.inya.ai/platform`, header `x-api-key`; `POST /v1/agents/{botId}/trigger_call`
  (outbound only to whitelisted numbers); `POST /v1/conversations/logs`. Vachana STT/TTS REST/WebSocket exist (fallback
  voice path, not built). UNKNOWN: mapping API responses back into conversation variables.
- Implemented: `connectors/gnani/extract.py` (our deterministic extractor, heuristic confidence) and a skeleton
  `GnaniPlatformConnector`. Mock `POST /gnani/extract` exposes the extractor as a capability (B in the plan).
- Platform config needed: agent with the voice prompt, Allow Interruptions on, silence timeouts, whitelisted numbers,
  a post-call Custom API action pointing at `POST /intake/gnani` on KIRRO Core.

## Delhivery (mock)
Paths mirror the documented Express shapes: `GET /delhivery/c/api/pin-codes/json/?filter_codes=`,
`POST /delhivery/api/cmu/create.json` (form `format=json&data=`), `GET /delhivery/api/v1/packages/json/?waybill=`.
The `filter_codes` query name is DOCUMENTED via community sources only. Response bodies are mock shapes; real create
and track responses were not verified. Failures: non-serviceable pincode (empty list), duplicate order id, 500, delay.

## Mock server scenarios
Set with `POST /__admin/scenario {"run_id", "target", "scenario" | "sequence", "delay_s"?, "options"?}`; the agent's
requests carry only `X-Run-Id` (correlation), `X-Request-Id`, `Idempotency-Key`. Scenarios: success, no_inventory,
insufficient_balance, timeout (default 12 s), malformed (HTML with 200, request still processed), duplicate (409
DUPLICATE_REQUEST on a replayed key), booking_expired, payment_failure, partial_group (capacity 3), upstream_500,
delayed (default 4 s). Targets: `venue.list_releases|release|hold|hold_get|hold_release|booking`,
`pinelabs.create_mandate|balance|execute|release|refund`, `delhivery.serviceability|create|track`, `gnani.extract`, `*`.
A sequence pops one scenario per call; the last sticks. `options: {"inject_label": true}` appends a prompt-injection
string to venue slot labels (E09). `GET /__admin/state?run_id=` returns counts for eval assertions.
Logs: `logs/mock/<run_id>.jsonl` with ts, request_id, upstream_request_id, path, target, scenario, request, response,
status, latency_ms.

## Failure and retry behaviour
Timeout/5xx retried once with the same idempotency key; 4xx and malformed not retried by the connector. The engine
makes one same-key re-attempt on malformed hold/charge/booking responses (ADR-007). After the budget: FAILED with
unwinding. A malformed or timed-out charge is reported as "could not confirm", never as success or failure.

## Needs real credentials or platform config
See the end of the repo report and `.env.example`: Pine Labs sandbox (client id/secret, merchant id, Grantex agent),
Gnani Inya (API key, agent id, whitelisted numbers), AgenticOrg platform (connector inventory, tool binding),
optional Delhivery staging token.
