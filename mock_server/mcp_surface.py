"""MCP surface over the mock server (ADR-012).

Each of the four AgenticOrg-facing surfaces gets its own MCP server, mounted at
`/<surface>/mcp` so it lines up with the Base URLs in `docs/agenticorg/setup-runbook.md`:

    venue       -> /venue/mcp       (inventory, holds, bookings, declare pool)
    pinelabs    -> /pinelabs/mcp    (mandate hold/release/capture, refund)
    allocator   -> /allocator/mcp   (DIFD draw)
    delhivery   -> /delhivery/mcp   (serviceability, create, track)

Every tool is a thin adapter: it calls the *same* ASGI app in-process via
`httpx.ASGITransport`, so validation, idempotency replay, scenario control, request
logging and the state store are literally the same code path the REST routes use. There is
no second implementation of any contract to drift.

Tools take an optional `run_id` (sent as the `X-Run-Id` header) so the Declare Agent and the
Window Allocation Workflow can share one pool; both fall back to `"default"` when omitted,
which also shares the pool. See `docs/connectors.md` and ADR-013.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

DEFAULT_RUN = "default"

# The MCP transport validates the request Host header (DNS-rebinding protection) and
# `streamable_http_app` defaults the allow-list to 127.0.0.1. Behind the TLS-terminating ingress the
# Host is the public domain, so without this every MCP call is rejected with
# `421 Invalid Host header` — which is exactly what happened on the first deploy. Override with
# MOCK_ALLOWED_HOSTS (comma-separated; a `host:*` entry matches any port) if the domain changes.
DEFAULT_ALLOWED_HOSTS = "localhost,localhost:*,127.0.0.1,127.0.0.1:*,api-kirro.upayan.dev,kirro-mock,kirro-mock:*"


def _split_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def transport_security() -> TransportSecuritySettings:
    """Host/Origin allow-list for the MCP endpoints.

    DNS-rebinding protection stays on: the mock is called server-to-server, but the protection is
    free and a rejected Host is loud (421) rather than silent. `MOCK_ALLOWED_ORIGINS` defaults to
    empty, which accepts requests that send no Origin (normal for an MCP client) and rejects
    browser-originated ones.
    """
    return TransportSecuritySettings(
        allowed_hosts=_split_env("MOCK_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
        allowed_origins=_split_env("MOCK_ALLOWED_ORIGINS", ""),
    )


SURFACE_INSTRUCTIONS = {
    "venue": "Mock venue inventory, time-boxed holds, bookings and the declare-interest pool.",
    "pinelabs": "Mock Pine Labs mandate: reserve, inspect balance, capture, release, refund.",
    "allocator": "DIFD declared-interest fair draw. Pure and deterministic for a given (release, window).",
    "delhivery": "Mock Delhivery Express: pincode serviceability, shipment creation, tracking.",
}


def _client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mock")


async def _call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    run_id: str,
    idem: str | None = None,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Call the mock's own REST route and return `{status_code, body}`.

    Mirrors the connector contract a real caller would see: a `malformed` scenario returns
    HTML with HTTP 200, so a non-JSON body is surfaced verbatim rather than crashing the tool.
    """
    headers = {"X-Run-Id": run_id}
    if idem:
        headers["Idempotency-Key"] = idem
    resp = await client.request(method, path, json=json, params=params or {}, headers=headers)
    try:
        body: Any = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    return {"status_code": resp.status_code, "body": body}


def _venue(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(description="List the booking releases. Filter by event (e.g. badminton) and/or date (YYYY-MM-DD).")
    async def list_releases(event: Any = None, date: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("list_releases", run_id, {"event": event, "date": date})
        return await _releases(client, run_id, _first_str(event), _first_str(date))

    @mcp.tool(
        description=(
            "Fetch one release with its slots. Pass the release id that list_releases returned, or an event name "
            "such as badminton. Called with no release_id it returns the released list, so you can pick from it."
        )
    )
    async def get_release(release_id: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("get_release", run_id, {"release_id": release_id})
        listing = await _releases(client, run_id, _first_str(release_id), None)
        found = listing["body"].get("releases", [])
        if not _first_str(release_id):
            # Live, the model calls this with no argument at all. The platform rejects a missing *required*
            # parameter before the call reaches us, so an empty lookup answers with the candidates instead —
            # the ids still reach the model, which a platform-side rejection cannot achieve.
            return {"status_code": 200, "body": {"releases": found, "note": "pass release_id to fetch one"}}
        if len(found) != 1:
            return {
                "status_code": 404,
                "body": {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "no single release matched; call list_releases and pass its release_id",
                    },
                    "releases": found,
                },
            }
        return await _call(client, "GET", f"/venue/releases/{found[0]['release_id']}", run_id=run_id)

    @mcp.tool(
        description=(
            "Place a time-boxed hold on a slot. release_id, slot_id and quantity (how many people to seat) are "
            "required; ttl_s is optional and defaults to 600 seconds."
        )
    )
    async def create_hold(
        release_id: Any = None,
        slot_id: Any = None,
        quantity: Any = None,
        ttl_s: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record(
            "create_hold",
            run_id,
            {"release_id": release_id, "slot_id": slot_id, "quantity": quantity, "ttl_s": ttl_s},
        )
        release = _first_str(release_id)
        slot = _first_str(slot_id)
        seats = _first_int(quantity)
        if release is None or slot is None or seats is None:
            return _bad_request(
                "release_id, slot_id and quantity are required; received "
                f"release_id={release_id!r}, slot_id={slot_id!r}, quantity={quantity!r}"
            )
        body: dict[str, Any] = {"slot_id": slot, "quantity": seats}
        ttl = _first_int(ttl_s)
        if ttl is not None:
            body["ttl_s"] = ttl
        return await _call(
            client, "POST", f"/venue/releases/{release}/holds", run_id=run_id, idem=idempotency_key, json=body
        )

    @mcp.tool(description="Check a hold's status (active | released | expired).")
    async def get_hold(hold_id: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("get_hold", run_id, {"hold_id": hold_id})
        hold = _first_str(hold_id)
        if hold is None:
            return _bad_request("hold_id is required; take it from the create_hold result")
        return await _call(client, "GET", f"/venue/holds/{hold}", run_id=run_id)

    @mcp.tool(description="Release a hold back to inventory.")
    async def release_hold(hold_id: Any = None, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        _record("release_hold", run_id, {"hold_id": hold_id})
        hold = _first_str(hold_id)
        if hold is None:
            return _bad_request("hold_id is required; take it from the create_hold result")
        return await _call(client, "DELETE", f"/venue/holds/{hold}", run_id=run_id, idem=idempotency_key)

    @mcp.tool(
        description=(
            "Confirm a booking against an active hold and a captured payment. Both hold_id and payment_id are "
            "required and must come from earlier results."
        )
    )
    async def confirm_booking(
        hold_id: Any = None,
        payment_id: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record("confirm_booking", run_id, {"hold_id": hold_id, "payment_id": payment_id})
        hold = _first_str(hold_id)
        payment = _first_str(payment_id)
        if hold is None or payment is None:
            return _bad_request(
                f"hold_id and payment_id are required; received hold_id={hold_id!r}, payment_id={payment_id!r}"
            )
        return await _call(
            client,
            "POST",
            "/venue/bookings",
            run_id=run_id,
            idem=idempotency_key,
            json={"hold_id": hold, "payment_id": payment},
        )

    @mcp.tool(
        description=(
            "Enter the user's bid into a release's declared-interest pool. "
            "release_id is required (the id from list_releases, or an event name such as badminton). "
            "group_size, min_group_size and max_price_paise are required; max_price_paise is the per-person "
            "ceiling in paise, so Rs 300 per person is 30000. acceptable_slot_ids is optional: leave it empty to "
            "bid for every slot in the release. You must call this to pool a bid: never tell the user they are in "
            "the pool unless this call has returned success."
        )
    )
    async def declare_interest(
        release_id: Any = None,
        group_size: Any = None,
        min_group_size: Any = None,
        max_price_paise: Any = None,
        acceptable_slot_ids: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record(
            "declare_interest",
            run_id,
            {
                "release_id": release_id,
                "group_size": group_size,
                "min_group_size": min_group_size,
                "max_price_paise": max_price_paise,
                "acceptable_slot_ids": acceptable_slot_ids,
            },
        )
        listing = await _releases(client, run_id, _first_str(release_id), None)
        found = listing["body"].get("releases", [])
        if len(found) != 1:
            return _bad_request(
                "release_id is required; call list_releases and pass the release_id it returns "
                f"(candidates: {found})"
            )
        resolved = found[0]["release_id"]
        slots_for_bid = _slot_ids(acceptable_slot_ids)
        if slots_for_bid is None:
            # Mock convenience: with no slot ids given, bid for the release's own slots, which is what declaring
            # interest in that release means. A model that never read the slot ids therefore cannot drop the bid.
            detail = await _call(client, "GET", f"/venue/releases/{resolved}", run_id=run_id)
            if detail["status_code"] != 200:
                return detail
            slots_for_bid = [slot["slot_id"] for slot in detail["body"].get("slots", [])]
        group = _first_int(group_size)
        minimum = _first_int(min_group_size)
        ceiling = _first_int(max_price_paise)
        if group is None or minimum is None or ceiling is None:
            return _bad_request(
                "group_size, min_group_size and max_price_paise (paise) are required; received "
                f"group_size={group_size!r}, min_group_size={min_group_size!r}, max_price_paise={max_price_paise!r}"
            )
        return await _call(
            client,
            "POST",
            f"/venue/releases/{resolved}/declarations",
            run_id=run_id,
            idem=idempotency_key,
            json={
                # A stable fallback keeps a retry of the same bid from becoming a second pool entry.
                "declaration_id": f"decl_{run_id}_{resolved}",
                "acceptable_slot_ids": slots_for_bid,
                "group_size": group,
                "min_group_size": minimum,
                "max_price_paise": ceiling,
                "user_contact": None,
                # The model does not carry the authorization id from the mandate result into the bid, and the pool
                # entry is what the allocation captures against, so a bid takes the mandate this run most recently
                # created — the declare flow reserves immediately before it bids. Exposing it as a parameter only
                # lengthened the tool's signature, which is what the model's argument emission degrades on.
                "mandate_id": _LATEST_MANDATE.get(run_id),
            },
        )

    @mcp.tool(
        description=(
            "List the release's declared-interest pool (one entry per pending bid). release_id is required — the "
            "entries this returns are the bids to pass to draw."
        )
    )
    async def list_pool_entries(release_id: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("list_pool_entries", run_id, {"release_id": release_id})
        release = _first_str(release_id)
        if release is None:
            # Live, the model calls this with a null release_id every time, even when the refusal names the
            # candidates and the conversation contains the id. A pool that actually holds bids is unambiguous, so
            # resolve to it — a documented mock convenience, like the date fallback in `_releases`. With more than
            # one non-empty pool, or none, the refusal stands and lists what it found.
            pools = []
            listing = await _releases(client, run_id, None, None)
            for candidate in listing["body"].get("releases", []):
                pool = await _call(
                    client, "GET", f"/venue/releases/{candidate['release_id']}/declarations", run_id=run_id
                )
                entries = pool["body"].get("declarations", [])
                if entries:
                    pools.append({"release_id": candidate["release_id"], "declarations": entries})
            if len(pools) == 1:
                return {"status_code": 200, "body": pools[0]}
            return _bad_request(
                "release_id is required; call list_releases and pass the release_id it returns "
                f"(pools holding bids: {[pool['release_id'] for pool in pools]})"
            )
        return await _call(client, "GET", f"/venue/releases/{release}/declarations", run_id=run_id)

    @mcp.tool(
        description=(
            "Remove a declaration from the pool. release_id and declaration_id are both required, taken from "
            "list_pool_entries."
        )
    )
    async def cancel_declaration(
        release_id: Any = None,
        declaration_id: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record("cancel_declaration", run_id, {"release_id": release_id, "declaration_id": declaration_id})
        release = _first_str(release_id)
        declaration = _first_str(declaration_id)
        if release is None or declaration is None:
            return _bad_request(
                f"release_id and declaration_id are required; received release_id={release_id!r}, "
                f"declaration_id={declaration_id!r}"
            )
        return await _call(
            client,
            "DELETE",
            f"/venue/releases/{release}/declarations/{declaration}",
            run_id=run_id,
            idem=idempotency_key,
        )


def _coerce_int(value: Any) -> int | None:
    """Models emit numbers as an int, a numeric string, or a `{"value": N}` object; the argument name varies too.
    Normalise all of those to an int, returning None when nothing usable was given."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        for key in ("value", "amount", "amount_value", "amount_paise", "price", "max_price"):
            if key in value:
                return _coerce_int(value[key])
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = value.strip().replace(",", "")
        if digits.isdigit():
            return int(digits)
    return None


def _coerce_amount(value: Any) -> int | None:
    return _coerce_int(value)


def _first_str(*candidates: Any) -> str | None:
    """First non-empty string, so a model may use any of the aliases a tool declares."""
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _first_int(*candidates: Any) -> int | None:
    """First candidate that coerces to an int, so a tool may declare several aliases for one number."""
    for candidate in candidates:
        coerced = _coerce_int(candidate)
        if coerced is not None:
            return coerced
    return None


def _bids(value: Any) -> list[dict] | None:
    """Bids as a list of entries, or a JSON-encoded string of one — models send both for array parameters."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, list):
        entries = [entry for entry in value if isinstance(entry, dict)]
        return entries or None
    return None


def _slot_ids(*candidates: Any) -> list[str] | None:
    """Slot ids as a list, a comma/space-separated string, or a single id."""
    for candidate in candidates:
        if isinstance(candidate, str):
            parts = [part for part in candidate.replace(",", " ").split() if part]
            if parts:
                return parts
        elif isinstance(candidate, (list, tuple)):
            parts = [str(part).strip() for part in candidate if str(part).strip()]
            if parts:
                return parts
    return None


def _bad_request(message: str) -> dict:
    return {"status_code": 400, "body": {"error": {"code": "BAD_REQUEST", "message": message}}}


# Set by `build_surfaces` from `app.state.mock`; None when the tools are exercised without an app (tests).
_TOOL_LOG: Any = None

# Latest mandate created per run. The declare flow reserves the mandate immediately before bidding, and the pool
# entry is what the allocation captures against, so a bid can carry it even when the model never threads the
# authorization id from one tool result into the next call's argument.
_LATEST_MANDATE: dict[str, str] = {}


def _record(tool: str, run_id: str, arguments: dict[str, Any]) -> None:
    """Append every MCP tool invocation, with the arguments as received, to the run's request log.

    The platform validates arguments before forwarding them, and our own guards answer before reaching a route,
    so without this a tool that failed inside a guard is indistinguishable from one the platform never sent.
    """
    if _TOOL_LOG is None:
        return
    _TOOL_LOG.log(
        run_id,
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "request_id": "",
            "upstream_request_id": "",
            "path": "mcp",
            "target": f"mcp.{tool}",
            "scenario": None,
            "request": arguments,
            "response": None,
            "status": None,
            "latency_ms": 0,
        },
    )


async def _releases(client: httpx.AsyncClient, run_id: str, event: str | None, date: str | None) -> dict:
    """List releases, tolerating a free-text event.

    The REST route filters `event_id` by exact match, but a model naturally sends "badminton" rather than
    "ev_badminton", which would silently return nothing. Here an event that is not already an exact id is matched
    as a substring of the event or release id, and the filtered list is returned in the route's own shape.
    """
    listing = await _call(client, "GET", "/venue/releases", run_id=run_id, params={})
    if listing["status_code"] != 200:
        return listing
    releases = listing["body"].get("releases", [])
    if event:
        exact = [item for item in releases if item["event_id"] == event]
        if exact:
            releases = exact
        else:
            needle = event.lower()
            releases = [
                item for item in releases if needle in item["event_id"].lower() or needle in item["release_id"].lower()
            ]
    if date:
        dated = [item for item in releases if item["date"] == date]
        # Mock convenience, and a deliberate one: weekday-to-date arithmetic is a known model weakness (live, the
        # agent resolved "this Saturday" to 2026-10-07 while the release is dated 2026-10-03), and an empty result
        # leaves it with no id to bid against. A date that matches nothing therefore falls back to whatever the
        # event matched, so the release stays reachable.
        releases = dated or releases
    return {"status_code": 200, "body": {"releases": releases}}


AMOUNT_ARG_NAMES = ("amount_value", "amountValue", "amount", "amount_paise", "amountPaise")


def _amount_or_error(*candidates: Any) -> tuple[int | None, dict | None]:
    """First usable amount wins. On failure the error echoes exactly what arrived, so the model's argument
    shape is visible in the agent's reply instead of only in a platform-side validation message."""
    for candidate in candidates:
        coerced = _coerce_amount(candidate)
        if coerced is not None:
            return coerced, None
    received = ", ".join(f"{name}={value!r}" for name, value in zip(AMOUNT_ARG_NAMES, candidates, strict=False))
    return None, {
        "status_code": 400,
        "body": {
            "error": {
                "code": "BAD_REQUEST",
                "message": f"amount_value (paise) is required; received {received}",
            }
        },
    }


def _pinelabs(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(
        description=(
            "Reserve (authorise) the total amount on the customer's mandate. The amount is in PAISE, not rupees: "
            "amount_paise = group size x price per person in rupees x 100. Example: 4 people at Rs 300 each is "
            "Rs 1,200 = 120000 paise. Pass that integer as `amount_value` (aliases `amount_paise`, `amount`)."
        )
    )
    async def create_mandate(
        amount_value: Any = None,
        amountValue: Any = None,
        amount: Any = None,
        amount_paise: Any = None,
        amountPaise: Any = None,
        currency: str = "INR",
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record(
            "create_mandate",
            run_id,
            {
                key: value
                for key, value in {
                    "amount_value": amount_value,
                    "amountValue": amountValue,
                    "amount": amount,
                    "amount_paise": amount_paise,
                    "amountPaise": amountPaise,
                }.items()
                if value is not None
            },
        )
        value, error = _amount_or_error(amount_value, amountValue, amount, amount_paise, amountPaise)
        if error is not None:
            return error
        result = await _call(
            client,
            "POST",
            "/pinelabs/mandates",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": value, "currency": currency}},
        )
        if result["status_code"] == 200 and result["body"].get("authorizationId"):
            _LATEST_MANDATE[run_id] = result["body"]["authorizationId"]
        return result

    @mcp.tool(description="Read the remaining authorised balance for a mandate.")
    async def get_mandate_balance(
        authorization_id: Any = None,
        authorizationId: Any = None,
        run_id: str = DEFAULT_RUN,
    ) -> dict:
        _record("get_mandate_balance", run_id, {"authorization_id": authorization_id})
        mandate = _first_str(authorization_id, authorizationId)
        if mandate is None:
            return _bad_request("authorization_id is required; take it from the create_mandate response")
        return await _call(client, "GET", f"/pinelabs/mandates/{mandate}/balance", run_id=run_id)

    @mcp.tool(
        description=(
            "Capture (charge) an amount against an active mandate. The amount is in PAISE, not rupees: for "
            "Rs 1,200 pass 120000. Pass that integer as `amount_value` (aliases `amount_paise`, `amount`)."
        )
    )
    async def execute(
        authorization_id: Any = None,
        authorizationId: Any = None,
        amount_value: Any = None,
        amountValue: Any = None,
        amount: Any = None,
        amount_paise: Any = None,
        amountPaise: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record(
            "execute",
            run_id,
            {"authorization_id": authorization_id, "amount_value": amount_value, "amount": amount},
        )
        mandate = _first_str(authorization_id, authorizationId)
        if mandate is None:
            return _bad_request("authorization_id is required; take it from the create_mandate response")
        value, error = _amount_or_error(amount_value, amountValue, amount, amount_paise, amountPaise)
        if error is not None:
            return error
        return await _call(
            client,
            "POST",
            f"/pinelabs/mandates/{mandate}/execute",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": value}},
        )

    @mcp.tool(
        description=(
            "Release the mandate's unused reserved amount. authorization_id is required — take it from the "
            "create_mandate result. Use this for a loser's mandate and for the residual after a capture."
        )
    )
    async def release(
        authorization_id: Any = None, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None
    ) -> dict:
        _record("release", run_id, {"authorization_id": authorization_id})
        mandate = _first_str(authorization_id)
        if mandate is None:
            return _bad_request("authorization_id is required; take it from the create_mandate result")
        return await _call(
            client,
            "POST",
            f"/pinelabs/mandates/{mandate}/release",
            run_id=run_id,
            idem=idempotency_key,
            json={},
        )

    @mcp.tool(
        description=(
            "Refund a captured payment. payment_id is required — take it from the execute result. Use this when a "
            "charge succeeded but the booking could not be confirmed."
        )
    )
    async def refund(payment_id: Any = None, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        _record("refund", run_id, {"payment_id": payment_id})
        payment = _first_str(payment_id)
        if payment is None:
            return _bad_request("payment_id is required; take it from the execute result")
        return await _call(
            client,
            "POST",
            f"/pinelabs/payments/{payment}/refund",
            run_id=run_id,
            idem=idempotency_key,
            json={},
        )


def _allocator(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(
        description=(
            "Run the DIFD draw for a release's pool. release_id and bids are required: bids is the list of pool "
            "entries from list_pool_entries. Deterministic for a given (release, window), so re-running it cannot "
            "change an allocation."
        )
    )
    async def draw(
        release_id: Any = None,
        bids: Any = None,
        window_open_iso: Any = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        _record(
            "draw",
            run_id,
            {"release_id": release_id, "bids": bids, "window_open_iso": window_open_iso},
        )
        release = _first_str(release_id)
        entries = _bids(bids)
        if release is None and entries is not None:
            # Same convenience, resolved precisely: a bid names a declaration, and a declaration lives in exactly
            # one release's pool, so the release is identifiable from the bids the model copied off the pool.
            listing = await _releases(client, run_id, None, None)
            wanted = {entry.get("declaration_id") for entry in entries}
            for candidate in listing["body"].get("releases", []):
                pool = await _call(
                    client, "GET", f"/venue/releases/{candidate['release_id']}/declarations", run_id=run_id
                )
                held = {entry.get("declaration_id") for entry in pool["body"].get("declarations", [])}
                if wanted & held:
                    release = candidate["release_id"]
                    break
        if release is None or entries is None:
            return _bad_request(
                "release_id and bids (the pool entries) are required; received "
                f"release_id={release_id!r}, bids={bids!r}"
            )
        payload: dict[str, Any] = {"release_id": release, "bids": entries}
        window = _first_str(window_open_iso)
        if window is not None:
            payload["window_open_iso"] = window
        return await _call(client, "POST", "/allocator/draw", run_id=run_id, idem=idempotency_key, json=payload)


def _delhivery(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(description="Pincode serviceability lookup (empty list means non-serviceable).")
    async def pincode_serviceability(filter_codes: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("pincode_serviceability", run_id, {"filter_codes": filter_codes})
        codes = _first_str(filter_codes)
        if codes is None:
            return _bad_request("filter_codes is required (a comma-separated list of pincodes)")
        _record("pincode_serviceability", run_id, {"filter_codes": codes})
        return await _call(
            client, "GET", "/delhivery/c/api/pin-codes/json/", run_id=run_id, params={"filter_codes": codes}
        )

    @mcp.tool(description="Create a shipment from a Delhivery-shaped create payload.")
    async def create_shipment(data: Any = None, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        _record("create_shipment", run_id, {"data": data})
        payload = _first_str(data)
        if payload is None:
            return _bad_request("data is required (the Delhivery create payload as a JSON string)")
        return await _call(
            client,
            "POST",
            "/delhivery/api/cmu/create.json",
            run_id=run_id,
            idem=idempotency_key,
            json={"format": "json", "data": payload},
        )

    @mcp.tool(description="Track a shipment by waybill.")
    async def track(waybill: Any = None, run_id: str = DEFAULT_RUN) -> dict:
        _record("track", run_id, {"waybill": waybill})
        number = _first_str(waybill)
        if number is None:
            return _bad_request("waybill is required; take it from the create_shipment result")
        return await _call(client, "GET", "/delhivery/api/v1/packages/json/", run_id=run_id, params={"waybill": number})


BUILDERS = {"venue": _venue, "pinelabs": _pinelabs, "allocator": _allocator, "delhivery": _delhivery}


def build_surfaces(app: Any) -> tuple[dict[str, MCPServer], MCPServer]:
    """Build one MCP server per surface plus one **aggregate** server holding every tool.

    Returns `(per_surface, aggregate)`. Mount the per-surface ones at `/<surface>/mcp` and the
    aggregate at `/all/mcp`.

    The aggregate exists because AgenticOrg scopes **at most one untrusted custom connector's tools
    per agent**: two registrations of the same mock ended up in a state where whichever connector the
    platform picked was scoped and the other's tools were rejected (`422 Invalid authorized_tools`),
    reproducibly and in both directions. Serving every tool from a single connector means the agent
    links one custom connector and can still be granted all of them. See
    `docs/agenticorg/platform-map.md`.
    """
    client = _client(app)
    global _TOOL_LOG
    _TOOL_LOG = getattr(app.state, "mock", None)
    _LATEST_MANDATE.clear()
    per_surface: dict[str, MCPServer] = {}
    for name, register in BUILDERS.items():
        mcp = MCPServer(f"kirro_{name}", instructions=SURFACE_INSTRUCTIONS[name])
        register(mcp, client)
        per_surface[name] = mcp

    aggregate = MCPServer(
        "kirro_mock",
        instructions=(
            "KIRRO mock: venue inventory/holds/declare pool, Pine Labs mandate, DIFD draw and Delhivery, "
            "all in one catalog. Prefer the `/all/mcp` endpoint when the platform can only scope one "
            "custom connector per agent."
        ),
    )
    for register in BUILDERS.values():
        register(aggregate, client)
    return per_surface, aggregate
