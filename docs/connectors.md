# Connectors

Labels: REAL (verified in vendor docs or package source), DOCUMENTED (in vendor docs, details not verified),
MOCK REQUIRED (competition rule or missing capability), UNKNOWN (not established; not on the demo path).
Verification dates refer to the Opus plan pass (2026-10-01) unless a different source is named.

## Summary

| Connector                              | Kind in repo                                          | Mode            | In this repo | Label                                                                               |
| -------------------------------------- | ----------------------------------------------------- | --------------- | ------------ | ----------------------------------------------------------------------------------- |
| Venue inventory + holds + declare pool | mock (budgeted, 1 of 3)                               | mock            | yes          | MOCK REQUIRED (no rail offers time-boxed holds)                                     |
| Pine Labs order/payment-link/refund    | real, native AgenticOrg connector (`pinelabs_plural`) | real (platform) | no           | REAL — already connected in the AgenticOrg tenant                                   |
| Pine Labs mandate hold/release         | mock (budgeted, 1 of 3)                               | mock            | yes          | MOCK REQUIRED (no AgenticOrg or Pine Labs connector exposes authorize/hold/release) |
| Vachana (Gnani.ai STT/TTS)             | real, custom AgenticOrg connector                     | real (platform) | no           | DOCUMENTED (`api.vachana.ai`, PyPI `gnani-vachana`, `docs.gnani.ai`)                |
| Twilio (call leg)                      | real, native AgenticOrg connector                     | n/a (platform)  | no           | REAL — in AgenticOrg catalog (`make_call`, `send_sms`, `send_whatsapp`)             |
| Delhivery Express                      | mock, mandatory, additional to the 3-slot budget      | mock            | yes          | MOCK REQUIRED (competition rule); paths DOCUMENTED                                  |
| DIFD allocator (fair draw)             | mock/internal (budgeted, 1 of 3)                      | mock            | yes          | KIRRO-owned; never an external capability (ADR-002)                                 |
| Delhivery Maps MCP                     | not built                                             | -               | no           | REAL per plan (stretch, dropped — see ADR-010)                                      |

Mode is decided by ADR-010; the repo no longer carries a connector-mode config file (`config/connectors.yaml` was
removed with the AgenticOrg migration — see ADR-011). What this repo runs is `mock_server/`; the real connectors are
registered on the platform.

Platform facts (connector catalog, registration mechanism, governance pages) verified live on
`agenticorg.hackathon.pinelabs.com` on 2026-10-02 — see `docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md`
for the full inventory and the mock-capability budget decision (3 slots: venue inventory+hold, Pine Labs mandate
hold/release, DIFD allocator; Delhivery mocked in addition, not counted against the 3).

## Mock server (this repo)

`mock_server/` serves the four AgenticOrg-facing surfaces (ADR-010/011), each wrapped in `serve()` so scenarios,
idempotency and request logging work:

- **Venue inventory + hold + declare pool** (capability 1 of 3): `GET /venue/catalogue` (optional
  `organiser_id`/`status` filters), `GET /venue/releases`, `GET /venue/releases/{release_id}`,
  `POST /venue/releases/{release_id}/holds`, `GET|DELETE /venue/holds/{id}`, `POST /venue/bookings`, the
  declare-interest pool below, and the portal-facing organisers/events/releases surface (see the next
  subsection).
- **Pine Labs mandate** (capability 2 of 3): `POST /pinelabs/mandates`, `GET /pinelabs/mandates/{id}/balance`,
  `POST /pinelabs/mandates/{id}/execute`, `POST /pinelabs/mandates/{id}/release`,
  `POST /pinelabs/payments/{id}/refund`.
- **DIFD draw** (capability 3 of 3): `POST /allocator/draw`.
- **Delhivery Express** (mandatory, additional): `GET /delhivery/c/api/pin-codes/json/`,
  `POST /delhivery/api/cmu/create.json`, `GET /delhivery/api/v1/packages/json/`.

### Declare-interest pool

The pool is the store behind ADR-011 §4 item 8 (the Declare Agent writes a bid; the Window Allocation Workflow reads
it). Keyed per run by `release_id → declaration_id → bid`:

- `POST /venue/releases/{release_id}/declarations` — body carries the bid: `declaration_id?` (generated if absent),
  `user_contact?`, `mandate_id?`, `acceptable_slot_ids[]`, `group_size`, `min_group_size`, `max_price_paise`,
  plus any extra fields. Required int fields and a non-empty `acceptable_slot_ids` are validated → 400 `BAD_REQUEST`;
  unknown release → 404 `NOT_FOUND`. Returns `{declaration_id, release_id, status: "DECLARED"}`.
- `GET /venue/releases/{release_id}/declarations` — returns `{release_id, declarations: [...]}`, every entry carrying
  its declared fields plus `status: "DECLARED"` (this is the Workflow's `list_pool_entries`).
- `DELETE /venue/releases/{release_id}/declarations/{declaration_id}` — removes the entry, 404 `NOT_FOUND` if absent.

### Organisers, events and releases (ADR-015)

The venue portal's write surface. Events and releases used to be a static read of `catalogue.json`; they are now
durable store documents (`mock_server/state.py`), and `catalogue.json` is seed data loaded into a fresh run only.
Each event carries an `organiser_id` and a `status` (`draft`|`published`); each release carries an
`allocation_mode` (`fair_draw`|`instant_buy`, default `fair_draw`), surfaced on `GET /venue/releases` and
`GET /venue/releases/{release_id}`.

- `GET /venue/organisers?status=` — `{organisers: [...]}`, each `{organiser_id, name, contact, status, requested_by}`.
- `POST /venue/organisers` — self-serve request; body `{name, contact, requested_by}` (all non-empty strings).
  Creates the organiser with `status: "pending"` → 400 `BAD_REQUEST` otherwise.
- `POST /venue/organisers/{id}/approve` — flips `status` to `"approved"`; unknown id → 404 `NOT_FOUND`. No auth
  layer in the mock (same trust model as `/__admin/*`): the portal's own admin check gates who may call it.
- `POST /venue/events` — body `{name, organiser_id, aliases?, generic_aliases?, fulfilment?, status?}`. The
  organiser must exist (404 `NOT_FOUND`) and be approved (403 `ORGANISER_NOT_APPROVED`). New event is
  `status: "draft"` unless `status` is given.
- `PATCH /venue/events/{id}` — partial update of `name|aliases|generic_aliases|fulfilment|status`; any other key →
  400 `BAD_REQUEST`; unknown id → 404.
- `POST /venue/releases` — body `{event_id, date, opens_at, slots: [{slot_id?, label, starts_at, capacity, price_per_person_paise}], allocation_mode?}`. Unknown event → 404; invalid mode/empty slots/non-positive
  capacity or price → 400. `slot_id` is generated when omitted.
- `POST /venue/releases/{id}/buy` — **instant_buy only.** One call: checks capacity, creates the hold, captures
  `quantity x price_per_person_paise` against the `mandate_id` in the body, confirms the booking. Returns
  `{release_id, slot_id, quantity, hold_id, payment_id, booking_ref, status: "CONFIRMED", amount_paise}`. A
  `fair_draw` release is refused **server-side** with 409 `FAIR_DRAW_REQUIRED` — the only way to take one is the
  declared-interest chain (declare → draw → hold → capture → confirm), so no caller can bypass the draw. An optional
  `user_contact` is stamped on the hold, booking and payment so the portal dashboard can attribute the purchase.
  Unknown release/mandate → 404, bad slot/quantity or missing `mandate_id` → 400, sold out / over capacity → 409,
  underfunded mandate → 402 `INSUFFICIENT_BALANCE`, a failed capture → 402 `PAYMENT_FAILED` (the hold is released in
  every refusal path, so a refused buy leaves no capacity held and no charge).

`GET /__admin/state?run_id=&user_contact=` adds a `user` block for that contact — their declarations (scanned: pool
entries carry `user_contact` from the declare body), instant-buy bookings and payments, and nothing else. Without
`user_contact` the response is the plain run-wide snapshot. This is the portal dashboard's data source, kept on the
harness endpoint on purpose rather than adding a per-user business route.

These are portal-facing writes, not agent-facing: they are deliberately **not** mirrored on the MCP surface
(`mock_server/mcp_surface.py`), which exists only for the AgenticOrg agent — exposing create/approve/buy tools there
would grant the agent privileges `docs/agenticorg/agent-spec.md` withholds. The portal calls these over REST.

### DIFD draw

`POST /allocator/draw` wraps the pure `allocator.engine.allocate` function (ADR-011 §2), so AgenticOrg can call DIFD
as a tool instead of our Python engine calling it in process:

- Request: `{release_id, window_open_iso?, bids: [{declaration_id, user_id, acceptable_slot_ids[], group_size, min_group_size, max_price_paise, allocations_last_30d?, mandate_active?, constraints?}]}`. Slots are
  read from the mock catalogue's release (with remaining capacity). `window_open_iso` defaults to the release's
  `opens_at` (the seed is `sha256(release_id + window_open_iso)`).
- Response: `{release_id, results: [{declaration_id, slot_id, group_size_allocated, status, draw_position, seed, reason}]}` — one `allocator/schemas.py::AllocationResult` per bid, in draw order. Unknown release → 404
  `NOT_FOUND`. See `docs/allocation.md` for the mechanism.

### MCP surface

Each surface is also exposed as an MCP server (ADR-012) — this is what AgenticOrg registers with the MCP checkbox
on. Transport is stateless streamable HTTP.

| Surface           | MCP endpoint     | Tools                                                                                                                                                                                                                                  |
| ----------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| venue             | `/venue/mcp`     | `list_releases`, `get_release`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`, `declare_interest`, `list_pool_entries`, `cancel_declaration`                                                                            |
| Pine Labs mandate | `/pinelabs/mcp`  | `create_mandate`, `get_mandate_balance`, `execute`, `release`, `refund`                                                                                                                                                                |
| DIFD draw         | `/allocator/mcp` | `draw`                                                                                                                                                                                                                                 |
| Delhivery         | `/delhivery/mcp` | `pincode_serviceability`, `create_shipment`, `track`                                                                                                                                                                                   |
| **all four**      | **`/all/mcp`**   | **all 18 above** — use this one for AgenticOrg: it scopes at most one untrusted custom connector per agent (see `docs/agenticorg/platform-map.md`), so the agent links a single connector and can still be granted every tool it needs |

Tools call the same routes **in process**, so validation, the idempotency ledger, the state store and the request
log are shared rather than reimplemented. The ADR-015 organisers/events/releases/buy routes above are the one
deliberate exception: they are portal-only and are not exposed as MCP tools. Every tool takes an optional `run_id` (sent as `X-Run-Id`; defaults to
`default`, which the Declare Agent and the Workflow therefore share) and every write tool takes an optional
`idempotency_key` (sent as `Idempotency-Key`). Scenario control (`/__admin/*`) is harness-only and is **not**
reachable from MCP.

### State and durability

State is durable in SQLite (ADR-013) at `MOCK_DB_PATH` — in the cluster `/app/data/mock.db` on a PVC — so the
declare-interest pool, holds, mandates, payments, the idempotency ledger and the ADR-015 events/releases/organisers
survive a pod restart. This matters
because the Declare Agent writes a bid now and the Window Allocation Workflow reads it later, and every deploy
restarts the pod.

Everything is keyed by `X-Run-Id`, so that header is the scope of a run: keep it stable across the Declare Agent and
the Workflow. Both fall back to `default`, which is also shared, so omitting it works too — just do not give the two
sides *different* run ids, or they will not see each other's pool. Single writer: the Deployment runs one replica.
`POST /__admin/reset` clears one run (with `run_id`) or all state.

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
- Mock endpoints (inline KIRRO mock contract in `mock_server/app.py`): `POST /pinelabs/mandates`, `GET .../{id}/balance`,
  `POST .../{id}/execute`, `POST .../{id}/release`, `POST /pinelabs/payments/{id}/refund`. Names `authorizationId`,
  `Amount(value, currency)`, `RESERVE_PAY` mirror documented names; response bodies are KIRRO mock shapes.

## Vachana (Gnani.ai voice)

- **REAL — verified from the official client source and a live authenticated call (2026-10-02).** Base URL
  `https://api.vachana.ai`. Auth header `X-API-Key-ID` (plus `X-API-Request-ID`); the client reads the key from
  `GNANI_API_KEY` (`gnani-vachana` 0.7.9, sdist inspected). Endpoints, from that package's own constants:
  - TTS REST `POST /api/v1/tts/inference`; also SSE `/api/v1/tts/sse` and WS `/api/v1/tts`.
  - STT REST `POST /stt/v3`; realtime STT WebSocket `wss://api.vachana.ai/stt/v3/stream`.
- **Live check, no synthesis so no credits spent:** `POST /api/v1/tts/inference` with the key answers
  `400 {"success":false,"message":"'model' is required …"}` — auth passed, payload rejected. The same call **without**
  the key answers `401 {"detail":{"error_code":"MISSING_API_KEY", …}}`. The key in use is valid.
- **Supported TTS model is `timbre-v2.5`** (from that live error message). The package's `DEFAULT_MODEL` is still
  `timbre-v2.0`, so the SDK default is stale — pass the model explicitly.
- **Cloudflare fronts the API.** A bare `python-urllib/x` User-Agent got `403 error code: 1010` *before the API saw
  the request*; a conventional library UA (`python-httpx/…`, `curl/…`) is accepted. Any caller — including the
  registered connector — must send a normal User-Agent or it looks like an auth failure.
- Rate limiting is real: `429 {"error_code":"RATE_LIMITED", …}` was hit during verification, so do not assume the
  default 100 RPM allowance.
- Registered on AgenticOrg via `Connectors > Register Connector > Custom/Generic Connector` as **`mcp_vachana_kirro`**
  (the `mcp_` prefix is required — see `setup-runbook.md` §2's naming rule): Base URL `https://api.vachana.ai`, Auth
  Type `Api Key`, header `X-API-Key-ID`, MCP checkbox **off** (plain REST/WS, not an MCP server). The key is entered
  in that form only — never in this repo. **The platform's own health check cannot verify a non-MCP custom
  connector** — it always probes for MCP tool discovery regardless of the checkbox, so this connector reports
  `not_configured` even with a valid credential (`docs/agenticorg/platform-bugs.md` Bug 3); that is a platform
  limitation, not a sign the credential is wrong.
- **Call leg is the browser, not a phone network** (ADR-016, reversed from an earlier Twilio phone-call plan
  that cost real money per number and per minute; the transport is LiveKit per ADR-017). A `web/` "Talk to
  KIRRO" page joins a LiveKit room, and a self-hosted `livekit-server` in the same cluster carries the audio.
  On the worker side, Gnani's own `livekit-plugins-gnani` supplies both speech directions around the
  AgenticOrg agent, so KIRRO runs no speech plumbing of its own. `twilio_kirro` stays registered for the
  optional outbound SMS/WhatsApp notification leg (`agent-spec.md` §5), not for carrying a call.
- The old Inya client and the deterministic field extractor (`connectors/gnani/*`) were removed with the AgenticOrg
  migration — see ADR-011. Field parsing on the live path is the agent's own reasoning constrained by the Prompt
  (`docs/agenticorg/agent-spec.md`), not code in this repo (ADR-011 Risk 1).

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
delayed (default 4 s). Targets: `venue.list_releases|release|hold|hold_get|hold_release|booking|declare_interest|list_declarations|cancel_declaration|list_organisers|create_organiser|approve_organiser|create_event|update_event|create_release|buy`, `allocator.draw`,
`pinelabs.create_mandate|balance|execute|release|refund` (the budgeted mandate mock, distinct from the native,
real `pinelabs_plural` connector), `delhivery.serviceability|create|track`, `*`.
A sequence pops one scenario per call; the last sticks. `options: {"inject_label": true}` appends a prompt-injection
string to venue slot labels (injection-resistance demo). `GET /__admin/state?run_id=` returns counts for test
assertions.
Logs: `logs/mock/<run_id>.jsonl` with ts, request_id, upstream_request_id, path, target, scenario, request, response,
status, latency_ms.

## Failure and retry behaviour

Retry policy now lives in the live agent, not this repo — the connector layer that implemented it was removed with
the AgenticOrg migration (see ADR-011; ADR-007 records the old oracle's same-key re-attempt rule and is historical).
The mock's job is to make failures realistic: `timeout`/`delayed` (sleep), `upstream_500`, `malformed` (HTML 200
while the request is still processed), and `duplicate` (409 on a replayed idempotency key). The agent must report a
malformed or timed-out call as "could not confirm", never as success or failure.

## Needs real credentials or platform config

Platform-side only now: Vachana, Twilio, `pinelabs_plural` and `whatsapp_kirro` are registered on AgenticOrg, not
configured from this repo (ADR-010/ADR-011); see `docs/agenticorg/setup-runbook.md`. This repo's env surface is
`MOCK_SERVER_URL` and `MOCK_LOG_DIR` (`.env.example`) — the mock needs no vendor credentials.
