# Connectors

Labels: REAL (verified in vendor docs or package source), DOCUMENTED (in vendor docs, details not verified),
MOCK REQUIRED (competition rule or missing capability), UNKNOWN (not established; not on the demo path).
Verification dates refer to the Opus plan pass (2026-10-01) unless a different source is named.

## Summary

| Connector                              | Kind in repo                                                   | Mode               | In this repo  | Label                                                                                                                                                                |
| -------------------------------------- | -------------------------------------------------------------- | ------------------ | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Venue inventory + holds + declare pool | mock (budgeted, 1 of 3)                                        | mock               | yes           | MOCK REQUIRED (no rail offers time-boxed holds)                                                                                                                      |
| Pine Labs order/refund (UAT)           | real, official `pinelabs-python` SDK called from `mock_server` | real (UAT sandbox) | yes (ADR-019) | REAL, optional — env-gated, off by default; the AgenticOrg `pinelabs_plural` connector itself is registered but uncredentialed and unused (`has_credentials: false`) |
| Pine Labs mandate hold/release         | mock (budgeted, 1 of 3)                                        | mock               | yes           | MOCK REQUIRED (no AgenticOrg or Pine Labs connector exposes authorize/hold/release)                                                                                  |
| Vachana (Gnani.ai STT/TTS)             | real, custom AgenticOrg connector                              | real (platform)    | no            | DOCUMENTED (`api.vachana.ai`, PyPI `gnani-vachana`, `docs.gnani.ai`)                                                                                                 |
| Twilio (call leg)                      | real, native AgenticOrg connector                              | n/a (platform)     | no            | REAL — in AgenticOrg catalog (`make_call`, `send_sms`, `send_whatsapp`)                                                                                              |
| Delhivery Express                      | mock, mandatory, additional to the 3-slot budget               | mock               | yes           | MOCK REQUIRED (competition rule); paths DOCUMENTED                                                                                                                   |
| DIFD allocator (fair draw)             | mock/internal (budgeted, 1 of 3)                               | mock               | yes           | KIRRO-owned; never an external capability (ADR-002)                                                                                                                  |
| Delhivery Maps MCP                     | not built                                                      | -                  | no            | REAL per plan (stretch, dropped — see ADR-010)                                                                                                                       |

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
  `POST /pinelabs/payments/{id}/refund`. The execute/refund responses additionally carry `real_order`/
  `real_refund` when `PINELABS_CLIENT_ID`/`PINELABS_CLIENT_SECRET` are set (ADR-019) — absent by default and in
  every test.
- **DIFD draw** (capability 3 of 3): `POST /allocator/draw`.
- **Delhivery Express** (mandatory, additional): `GET /delhivery/c/api/pin-codes/json/`,
  `POST /delhivery/api/cmu/create.json`, `GET /delhivery/api/v1/packages/json/`.

### Declare-interest pool

The pool is the store behind ADR-011 §4 item 8 (the Declare Agent writes a bid; the Window Allocation Workflow reads
it). Keyed per run by `release_id → declaration_id → bid`:

- `POST /venue/releases/{release_id}/declarations` — body carries the bid: `declaration_id?` (generated if absent),
  `user_contact?`, `notify_phone` (**required**), `mandate_id?`, `acceptable_slot_ids[]`, `group_size`,
  `min_group_size`, `max_price_paise`, plus any extra fields. `notify_phone` is the number the draw's result is
  delivered to over WhatsApp: it is normalised to E.164 (spaces, dashes, brackets and a leading `00` are accepted)
  and anything else — empty, no country code, letters, an implausible length — is 400 `BAD_REQUEST`, because a wrong
  number here means a silent delivery failure. Required int fields and a non-empty `acceptable_slot_ids` are
  validated the same way; unknown release → 404 `NOT_FOUND`, a closed release (see `declarations_open` below) →
  409 `POOL_CLOSED`. Returns `{declaration_id, release_id, status: "DECLARED"}`; a second call with the **same**
  `declaration_id` is a no-op (the stored bid is not overwritten) and returns the same body plus
  `duplicate: true`, so a caller can tell a retry from a first success.
- `GET /venue/releases/{release_id}/declarations` — returns `{release_id, declarations: [...]}`, every entry carrying
  its declared fields plus `status: "DECLARED"` (this is the Workflow's `list_pool_entries`).
- `DELETE /venue/releases/{release_id}/declarations/{declaration_id}` — removes the entry, 404 `NOT_FOUND` if absent.
- `GET|PUT /venue/users/{user_contact}/profile` — the portal's per-user settings document:
  `{user_contact, notify_phone?, push_subscription?}`. `PUT` merges rather than overwrites — a caller may send
  `notify_phone`, `push_subscription`, or both, and the field it omits is left as stored; at least one is
  required. `notify_phone` applies the same E.164 rule and 400 as the declaration route. `push_subscription` is
  a Web Push `PushSubscription.toJSON()` object (`{endpoint, keys: {p256dh, auth}}`) or `null` to clear it;
  stored as-is, never validated or dereferenced by the mock — the portal's own Next.js server sends the actual
  push directly to the browser's push service using it (`web-push`, VAPID), not through this mock. The portal
  reads this instead of asking for a number on every declaration, so a user sets it once in `/settings` and
  every later bid reuses it. Portal-facing and deliberately **not** on the MCP surface: the
  agent collects the number in conversation instead (see `agent-spec.md` §3).

The MCP `declare_interest` tool (below) additionally accepts `mandate_id`/`authorization_id` (the id
`create_mandate` returned earlier in the same conversation) and keys the fallback `declaration_id` on it —
`decl_{run_id}_{release_id}_{mandate_id}` instead of `decl_{run_id}_{release_id}` — so two different callers'
bids on the same release, each with their own mandate, no longer overwrite each other. A model that omits it
falls back to the run's most recently created mandate, same as before (unaffected in a single-caller run).

### Organisers, events and releases (ADR-015)

The venue portal's write surface. Events and releases used to be a static read of `catalogue.json`; they are now
durable store documents (`mock_server/state.py`), and `catalogue.json` is seed data loaded into a fresh run only.
Each event carries an `organiser_id` and a `status` (`draft`|`published`); each release carries an
`allocation_mode` (`fair_draw`|`instant_buy`, default `fair_draw`), surfaced on `GET /venue/releases` and
`GET /venue/releases/{release_id}`.

Both release routes also carry `declarations_open` (MOCK field): `true` only for a `fair_draw` release whose
`opens_at` is still in the future, computed from the wall clock at request time. The draw runs when the window
opens, so a release past `opens_at` can no longer be declared on — the agent reads this field instead of doing
date arithmetic, and `POST .../declarations` enforces it server-side (409 `POOL_CLOSED` above). A fresh run's
catalogue fixture is seeded with dates computed relative to that seed's own clock (`mock_server/state.py`
`_seed_domain`), not pinned to a calendar date, so its releases are open right after a reset regardless of when
that happens to be. The detail and listing routes also carry: the release's `date`; `weekday` (its day name,
MOCK field, so the agent never reads one back wrong); `opens_at_ist` (`opens_at` converted to IST, a fixed
UTC+5:30 offset, MOCK field, so the agent does not do that arithmetic either); and
`min_price_per_person_paise` (the cheapest slot's price, MOCK field, so the agent can tell a bidder their
ceiling is below every slot without computing it). On the MCP surface, an event word (`"tennis"`) passed to
`get_release` or `declare_interest` that matches several releases resolves to the one whose
`declarations_open` is `true` when exactly one is; otherwise the tool answers with the candidate list, dates
included.

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
  `NOT_FOUND`. See `docs/allocation.md` for the mechanism. As a side effect, a release that exists in the mock's
  own release store gets `drawn: true` — surfaced on `GET /venue/releases` and the detail route (MOCK field,
  additive alongside `declarations_open`) so the allocator-trigger bridge (ADR-018) never asks for the
  same release twice. Not set when the handler never ran (e.g. an `upstream_500` scenario), so a draw that
  genuinely failed is retried on the next pass.

**Nothing calls this automatically on the platform.** The "Kirro Window Allocation" Workflow that was meant to
(`docs/agenticorg/workflow-spec.md`) executes zero steps (`platform-bugs.md` Bug 2). `allocator_bridge/` — a
k8s CronJob, ADR-018 — drives "Kirro Allocator" over its chat API instead: once per pass, every release with
`declarations_open: false`, `drawn: false` and at least one pool entry gets the same sentence
(`"Run the allocation for release_id <id>: draw its bids and settle every one."`) that was already verified
against the live agent (`docs/testing.md`). The script decides only *when* to ask; every allocation, hold,
capture and release decision stays the Allocator agent's.

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

- **AgenticOrg's own `pinelabs_plural` connector is registered but not actually wired.** Live `GET /api/v1/connectors` on the tenant (2026-10-03, `docs/agenticorg/platform-map.md` §14): `status: active` but
  `has_credentials: false`, `base_url: ""`, `health_check_at: null` — a catalog placeholder, never given real
  keys. Tools advertised: `create_order, check_order_status` (two, not the six ADR-010 originally recorded). No
  code in this repo calls it; it is unused.
- **Gap (why the mandate stays mocked)**: neither `pinelabs_plural` nor the wider Plural API has an
  authorize-then-hold-then-capture-or-release primitive. KIRRO's mandate (reserve `group_size x max_price`,
  hold, capture \<= ceiling, release unused) has no native match — see ADR-010 decision 2. This is unchanged;
  `create_mandate`, `get_mandate_balance` and `release` are pure mock regardless of what follows.
- **REAL, optional (ADR-019, 2026-10-03): a direct call-out from `mock_server` itself**, not through
  AgenticOrg. The official SDK is `pinelabs-python` (PyPI, MIT, `docs.pluralonline.com`), OAuth2
  client_credentials against the free UAT sandbox `https://pluraluat.v2.pinepg.in` ("no production credentials
  required" per Pine Labs' own quick-start guide). `mock_server/pinelabs_plural.py` wraps it:
  `PINELABS_CLIENT_ID`/`PINELABS_CLIENT_SECRET` unset (the default, and every test) means zero network calls;
  set, a successful `pinelabs.execute`/`venue.buy` capture also places a real UAT `orders.create_order`, and a
  `pinelabs.refund` against that payment also places a real UAT `refunds.create_refund`. Results are attached
  as `real_order`/`real_refund` on the response and the payment record; a failed or unreachable sandbox is
  caught and returned as `{"error": ...}`, never raised — it cannot fail the mock's own response.
  **Verified live, 2026-10-03**, with real UAT test-mode credentials (Pine Labs dashboard -> Test Mode ->
  Settings -> Credentials; the live-mode tab stays KYC-gated): a real capture placed a real order
  (`201 Created`, `order_id: v1-261003174706-aa-9NHfQ9`). A refund attempt against it returned a real
  `404 ORDER_NOT_FOUND`, caught as `real_refund.error` — expected, since the order was never paid through
  Plural's own checkout (`challenge_url`); KIRRO's capture moves money through its own mandate mock, not
  Plural's checkout. **SDK bug found and worked around**: `pinelabs-python` 0.2.1's client wrapper
  unconditionally sets `Authorization: Bearer {token}`, so its own documented `token=""` bootstrap sends
  `Bearer ` (empty, trailing space) and `httpx`/`h11` reject it before the request leaves the process —
  `mock_server/pinelabs_plural.py` fetches the token with a plain `httpx` POST instead, then hands the SDK a
  real token for every other call. Offline tests stub the transport
  (`tests/test_mock_server.py::test_pinelabs_real_callout_*`). In the cluster (`kirro` namespace) the two
  values are the `kirro-pinelabs` Secret (SOPS-encrypted, in the private cluster repo's
  `k8s/apps/kirro/secrets/secrets.sops.yaml`) and reach `kirro-mock` via `secretKeyRef`, so prod places the
  real UAT order/refund too; `k8s/deployments.yaml` marks both refs `optional: true`, so a missing Secret
  just falls back to pure simulation.
- **Superseded investigation, kept for history**: an earlier pass inspected a different package,
  `pinelabs-online-p3p-server-sdk` 1.3.0 (`pinelabs_p3p_server`), whose server instance exposed
  `create_mandate`/`get_mandate`/`revoke_mandate`/`capture`/`create_refund` against the same UAT base URL. That
  package is not what `pinelabs-python` (used above) is, and was never wired in; it is not a dependency of this
  repo.
- Mock endpoints (inline KIRRO mock contract in `mock_server/app.py`): `POST /pinelabs/mandates`, `GET .../{id}/balance`,
  `POST .../{id}/execute`, `POST .../{id}/release`, `POST /pinelabs/payments/{id}/refund`. Names `authorizationId`,
  `Amount(value, currency)`, `RESERVE_PAY` mirror documented names; response bodies are KIRRO mock shapes, plus
  the optional real-call fields above.

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
status, latency_ms. Each line is also written to stdout, the only channel the cluster's log agent ships to Loki; the
file under `MOCK_LOG_DIR` remains the record of authority (the stdout line carries no `run_id`, only the file name does).

**`/__admin/*` answered unauthenticated on the public mock URL** (`https://api-kirro.upayan.dev/__admin/state`
returned 200 from anywhere — #12 item 2). `MOCK_ADMIN_KEY`, when set, gates every `/__admin/*` call behind a
matching `X-Admin-Key` header (`mock_server/app.py` `_admin_key_denied`); a mismatch or missing header is 403
`FORBIDDEN`. Unset — the state until an operator provisions it — is a no-op, so a cluster without the key keeps
working exactly as before. To turn it on: add a `MOCK_ADMIN_KEY` key to a `kirro-mock-admin` Secret (ksops, same
pattern as `kirro-voice` in the cluster repo's `k8s/apps/kirro/secrets/`), restart `kirro-mock`
(`k8s/deployments.yaml` wires it in as `optional: true`), and set the same value as `X-Admin-Key` on every
harness `/__admin` call thereafter. The agent is never told this header exists.

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
