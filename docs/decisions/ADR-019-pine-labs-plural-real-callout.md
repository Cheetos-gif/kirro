# ADR-019: an optional, env-gated real call-out to Pine Labs Plural's UAT sandbox

Status: accepted (2026-10-03)

## Context

ADR-010 decision 2 is unchanged and not reopened here: Pine Labs Plural has no authorize-then-hold-then-
capture-or-release primitive, so KIRRO's mandate (reserve `group_size x max_price`, hold it through the draw,
capture `<= ceiling`, release the rest) stays this repo's own mock, in `mock_server/app.py` and
`mock_server/state.py` — source of truth for ceiling enforcement, idempotency and offline tests.

What prompted this ADR is a separate, narrower question: is there a real Pine Labs connection anywhere in this
build, and if so, is our backend actually using it? Live inspection of the AgenticOrg tenant
(`docs/agenticorg/platform-map.md` §13) answered no — the native `pinelabs_plural` connector is `status: active` in the catalog but `has_credentials: false`, `base_url: ""`, `health_check_at: null`. It is a
registered placeholder, never wired with real keys, and nothing in this repo calls it (`grep` across
`mock_server/`, `voice_bridge/`, `allocator_bridge/`, `allocator/`, `web/src` finds zero references to
`pinelabs_plural`, `create_order`, `create_payment_link`, `initiate_refund` or `get_payout_analytics`). So
`docs/connectors.md`'s "REAL — already connected in the AgenticOrg tenant" claim was wrong and is corrected in
the same change as this ADR.

Separately, Pine Labs publishes a real, official SDK for exactly this gap: `pinelabs-python` (PyPI, MIT,
`docs.pluralonline.com`), OAuth2 client_credentials, a free UAT sandbox
(`https://pluraluat.v2.pinepg.in`, "no production credentials required" per Pine Labs' own quick-start guide)
with `orders.create_order` / `refunds.create_refund` — the two operations ADR-010 decision 2's consequences
bullet already anticipated ("fronting whichever of create_order/create_payment_link actually moves money when
a hold converts to a charge"), just never implemented.

## Decision

`mock_server/pinelabs_plural.py` adds a `RealPinelabsClient`: a thin, synchronous wrapper around the official
SDK. It is **disabled by default** — `enabled = bool(PINELABS_CLIENT_ID and PINELABS_CLIENT_SECRET)` — and
every public method short-circuits to `None` when disabled, making zero network calls. `uv run pytest` stays
offline exactly as `AGENTS.md` requires: no test in this repo sets those two env vars, so every existing test
is unaffected (verified: the full suite passes unchanged before and after this wiring).

When the two env vars are set, `mock_server/app.py` fronts two existing mock legs with a real UAT call:

- `capture()` (shared by `pinelabs.execute` and the one-shot `venue.buy`): on a `SUCCESS` capture, also calls
  `create_order(amount_paise, payment_id)`. The result — `{"order_id", "status"}` or `{"error": ...}` — is
  attached to the payment record and, only when present, to the response body as `real_order`. Absent (the
  default), the response is byte-identical to before this change.
- `POST /pinelabs/payments/{id}/refund`: if that payment carries a `real_order.order_id`, also calls
  `create_refund(order_id, amount_paise, payment_id)`, surfaced the same way as `real_refund`.

**The mock's own mandate bookkeeping never depends on the real call's outcome.** A failed or unreachable UAT
sandbox is caught inside `RealPinelabsClient` and returned as `{"error": ...}` — it never raises, and it never
changes the mock's status code or its own fields. A flaky sandbox must not break the KIRRO demo; the mandate
mock is still what enforces the ceiling, still what the Declare/Allocator agents and the web portal actually
read balances from.

Token handling: `RealPinelabsClient` authenticates once (`POST /api/auth/v1/token`, client_credentials) and
caches the bearer token until 30 seconds before its `expires_at`, re-authenticating lazily on the next call
past that point — one extra round trip per cold start, not per request. **This bypasses the SDK's own
`authentication.generate_token` for the token call specifically**: `pinelabs-python` 0.2.1's client wrapper
unconditionally sends `Authorization: Bearer {token}`, so its own documented bootstrap pattern
(`PinelabsApi(token="")`) sends `Bearer ` (trailing space, empty value) and `httpx`/`h11` reject that as an
illegal header value before the request leaves the process — reproduced directly against the live UAT
sandbox, independent of any credential. A plain `httpx.Client().post(...)` to the same endpoint, same
credentials, returns `200` with a real token normally. Every call *after* that — `orders.create_order`,
`refunds.create_refund` — goes through the SDK as documented, since by then the token is real.

Testability: the SDK's `httpx_client=` constructor parameter accepts an arbitrary `httpx.Client`, so tests
construct a `RealPinelabsClient` directly with an `httpx.MockTransport` stub (no real network, no real
credentials) and monkeypatch `mock_server.app.get_real_pinelabs_client` to return it — covering the
disabled-by-default no-op, the enabled happy path (`real_order`/`real_refund` present with the stub's
values), and a stubbed sandbox failure (mock response still `200 SUCCESS`, error surfaced, not raised).

## Consequences

- New dependency: `pinelabs-python` (added via `uv add`, `pyproject.toml` + `uv.lock`). First exception to
  "no new dependencies without an ADR" since the initial stack — scoped to one optional module, not imported
  anywhere else.
- New env vars, documented in `.env.example`: `PINELABS_CLIENT_ID`, `PINELABS_CLIENT_SECRET`,
  `PINELABS_BASE_URL` (default the UAT sandbox). All three blank is the shipped default and every CI run.
- `docs/connectors.md`'s Pine Labs section and summary table are corrected: `pinelabs_plural` on AgenticOrg is
  registered but uncredentialed and unused; the real call-out, when configured, happens from `mock_server`
  directly against Pine Labs' own UAT sandbox, not through the AgenticOrg connector.
- **Verified live, 2026-10-03**, against a real UAT account (test-mode credentials from
  `dashboardv2.pluralonline.com` -> Settings -> Credentials, after switching the dashboard to Test Mode — the
  live-mode `Credentials` tab stays KYC-gated and blank regardless): a real capture through the mock placed a
  real order on Plural's UAT sandbox — `201 Created`, `order_id: v1-261003174706-aa-9NHfQ9` — surfaced as
  `real_order` on the `pinelabs.execute` response exactly as designed. A refund attempt against that same order
  returned a real `404 ORDER_NOT_FOUND`, caught and surfaced as `real_refund.error`, not raised — **expected,
  not a defect**: the order was created but never paid through Plural's own hosted checkout (`challenge_url`),
  since KIRRO's capture moves money through its own mandate mock, not through Plural's checkout flow. A
  `real_refund` only has something to refund once a real payment has actually been completed against the
  order by some other channel; this call-out does not attempt to drive that checkout itself.
- Does not touch `create_mandate`, `get_mandate_balance` or `release` — Plural has no matching primitive, so
  those three stay pure mock regardless of credentials, unchanged by this ADR.
