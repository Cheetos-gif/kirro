# Connectors

Labels: REAL (verified in vendor docs or package source), DOCUMENTED (in vendor docs, details not verified),
MOCK REQUIRED (competition rule or missing capability), UNKNOWN (not established; not on the demo path).
Verification dates refer to the Opus plan pass (2026-10-01) unless a different source is named.

## Summary

| Connector                           | Kind in repo                                          | Config mode               | Implemented   | Label                                                                               |
| ----------------------------------- | ----------------------------------------------------- | ------------------------- | ------------- | ----------------------------------------------------------------------------------- |
| Venue inventory + holds             | mock (budgeted, 1 of 3)                               | `venue_inventory: mock`   | yes           | MOCK REQUIRED (no rail offers time-boxed holds)                                     |
| Pine Labs order/payment-link/refund | real, native AgenticOrg connector (`pinelabs_plural`) | `pine_labs: real`         | not yet bound | REAL — already connected in the AgenticOrg tenant                                   |
| Pine Labs mandate hold/release      | mock (budgeted, 1 of 3)                               | `pine_labs_mandate: mock` | mock yes      | MOCK REQUIRED (no AgenticOrg or Pine Labs connector exposes authorize/hold/release) |
| Vachana (Gnani.ai STT/TTS)          | real, custom AgenticOrg connector                     | `vachana: real`           | not yet bound | DOCUMENTED (`api.vachana.ai`, PyPI `gnani-vachana`, `docs.gnani.ai`)                |
| Twilio (call leg)                   | real, native AgenticOrg connector                     | n/a (platform-native)     | not yet bound | REAL — in AgenticOrg catalog (`make_call`, `send_sms`, `send_whatsapp`)             |
| Delhivery Express                   | mock, mandatory, additional to the 3-slot budget      | `delhivery: mock`         | yes           | MOCK REQUIRED (competition rule); paths DOCUMENTED                                  |
| DIFD allocator (fair draw)          | mock/internal (budgeted, 1 of 3)                      | n/a                       | yes           | KIRRO-owned; never an external capability (ADR-002)                                 |
| Delhivery Maps MCP                  | not built                                             | -                         | no            | REAL per plan (stretch, dropped — see ADR-010)                                      |

Platform facts (connector catalog, registration mechanism, governance pages) verified live on
`agenticorg.hackathon.pinelabs.com` on 2026-10-02 — see `docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md`
for the full inventory and the mock-capability budget decision (3 slots: venue inventory+hold, Pine Labs mandate
hold/release, DIFD allocator; Delhivery mocked in addition, not counted against the 3).

## Pine Labs

- **Native on AgenticOrg**: `Pine Labs (Plural)` connector, already registered and active in this tenant as
  `pinelabs_plural` (`Auth: API_KEY`). Tools: `create_order, create_payment_link, get_order_status, get_payout_analytics, get_settlement_report, initiate_refund`. A second native connector, `Pinelabs Online payment` (QR `create_payment/create_qr_transaction/check_payment_status/cancel_payment/cancel_qr_transaction/ get_qr_transaction_status`), exists but is not registered in this tenant. Use `pinelabs_plural` for the real
  charge/order/refund leg.
- **Gap (why we still mock)**: none of the above is an authorize-then-hold-then-capture-or-release primitive.
  KIRRO's mandate (reserve `group_size x max_price`, hold, capture \<= ceiling, release unused) has no native
  match — see ADR-010 decision 2.
- **Verified from package source** (`pinelabs-online-p3p-server-sdk` 1.3.0, import `pinelabs_p3p_server`, inspected from
  the PyPI wheel): server instance methods `create_mandate`, `get_mandate`, `get_mandate_balance`, `revoke_mandate`,
  `capture`, `create_refund`; REST paths `POST /mpp/v1/pre-authorize`, `GET /mpp/v1/authorization/{id}`,
  `GET /mpp/v1/balance`, `POST /mpp/v1/revoke`, `POST /api/pay/v1/refunds/{order_id}`; sandbox base
  `https://pluraluat.v2.pinepg.in`; config needs `clientId`, `clientSecret`, `merchantId`, `paymentGateway`,
  `availablePaymentMethods`. Env names (`PINELABS_CLIENT_ID`, ...) are from the plan, not the package. This SDK
  path is a fallback only if the mandate mock needs a real-shaped reference; the primary real path is the native
  AgenticOrg `pinelabs_plural` connector above.
- **Correction to the plan**: the client SDK (`pinelabs-online-p3p-client-sdk` 1.3.0) no longer creates mandates; it only
  creates payment tokens bound to a 402 challenge (`client.methods.create_token`). Charging is a two-party flow
  (server challenge -> client token -> server `capture`). The mock's single `execute_charge` call is a simplification.
- Mock endpoints (MOCK schema, `connectors/mock_schemas.py`): `POST /pinelabs/mandates`, `GET .../{id}/balance`,
  `POST .../{id}/execute`, `POST .../{id}/release`, `POST /pinelabs/payments/{id}/refund`. Names `authorizationId`,
  `Amount(value, currency)`, `RESERVE_PAY` mirror documented names; response bodies are KIRRO mock shapes.

## Vachana (Gnani.ai voice)

- DOCUMENTED and REAL: `https://api.vachana.ai` — REST speech-to-text, WebSocket streaming STT at
  `wss://api.vachana.ai/stt/v3/stream`, TTS REST. Auth header `X-API-Key-ID`. Reference client: `gnani-vachana`
  (PyPI); full reference docs at `docs.gnani.ai`. Same vendor as Inya (Gnani.ai); replaces the Inya `trigger_call`
  design entirely — see ADR-010 decision 1 for why.
- Register on AgenticOrg via `Connectors > Register Connector > Custom/Generic Connector`: Base URL
  `https://api.vachana.ai`, Auth Type API Key, header `X-API-Key-ID`, MCP checkbox **off** (this is a plain REST/WS
  API, not an MCP server).
- Call leg is **Twilio** (native AgenticOrg connector, `make_call`/`send_sms`/`send_whatsapp`/`get_recordings`/
  `get_message_status`), not Gnani/Vachana — Vachana only turns the call audio into text and back.
- Not yet implemented: `connectors/gnani/platform.py` (Inya client) is obsolete under this decision; replace with a
  Vachana client. `connectors/gnani/extract.py` (our deterministic field extractor) is unaffected — it still runs
  on whatever transcript Vachana STT returns.

## Delhivery (mock, mandatory, additional to the 3-slot budget)

Paths mirror the documented Express shapes: `GET /delhivery/c/api/pin-codes/json/?filter_codes=`,
`POST /delhivery/api/cmu/create.json` (form `format=json&data=`), `GET /delhivery/api/v1/packages/json/?waybill=`.
The `filter_codes` query name is DOCUMENTED via community sources only. Response bodies are mock shapes; real create
and track responses were not verified. Failures: non-serviceable pincode (empty list), duplicate order id, 500, delay.

Registered on AgenticOrg as a Custom/Generic Connector with the **MCP checkbox on** (tool catalog auto-discovered
from our hosted mock server's URL at registration time) — see ADR-010. This surface is mandatory per the
competition brief and does not consume one of the 3 budgeted mock-capability slots.

## Mock server scenarios

Set with `POST /__admin/scenario {"run_id", "target", "scenario" | "sequence", "delay_s"?, "options"?}`; the agent's
requests carry only `X-Run-Id` (correlation), `X-Request-Id`, `Idempotency-Key`. Scenarios: success, no_inventory,
insufficient_balance, timeout (default 12 s), malformed (HTML with 200, request still processed), duplicate (409
DUPLICATE_REQUEST on a replayed key), booking_expired, payment_failure, partial_group (capacity 3), upstream_500,
delayed (default 4 s). Targets: `venue.list_releases|release|hold|hold_get|hold_release|booking`,
`pinelabs_mandate.create|balance|execute|release|refund` (the budgeted mandate mock, distinct from the native,
real `pinelabs_plural` connector), `delhivery.serviceability|create|track`, `*`.
A sequence pops one scenario per call; the last sticks. `options: {"inject_label": true}` appends a prompt-injection
string to venue slot labels (E09). `GET /__admin/state?run_id=` returns counts for eval assertions.
Logs: `logs/mock/<run_id>.jsonl` with ts, request_id, upstream_request_id, path, target, scenario, request, response,
status, latency_ms.

## Failure and retry behaviour

Timeout/5xx retried once with the same idempotency key; 4xx and malformed not retried by the connector. The engine
makes one same-key re-attempt on malformed hold/charge/booking responses (ADR-007). After the budget: FAILED with
unwinding. A malformed or timed-out charge is reported as "could not confirm", never as success or failure.

## Needs real credentials or platform config

See the end of the repo report and `.env.example`: Pine Labs native AgenticOrg connector (already connected as
`pinelabs_plural` in this tenant, no action needed) and a Pine Labs sandbox credential set only if the mandate mock
needs a real-shaped reference; Vachana (`VACHANA_API_KEY` for the `X-API-Key-ID` header); Twilio (native AgenticOrg
connector — credentials are the platform's, not ours); an AgenticOrg API key for `Register Connector` /
`client.agents.*` calls; optional Delhivery staging token if the mock is ever pointed at real staging.
