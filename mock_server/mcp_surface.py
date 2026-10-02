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

import os
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

    @mcp.tool(description="List releases, optionally filtered by event_id and/or date.")
    async def list_releases(event_id: str | None = None, date: str | None = None, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", "/venue/releases", run_id=run_id, params={"event_id": event_id, "date": date})

    @mcp.tool(description="Fetch one release with its slots, remaining capacity and opens_at.")
    async def get_release(release_id: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", f"/venue/releases/{release_id}", run_id=run_id)

    @mcp.tool(description="Place a time-boxed hold on a slot.")
    async def create_hold(
        release_id: str,
        slot_id: str,
        quantity: int,
        ttl_s: int = 600,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        return await _call(
            client,
            "POST",
            f"/venue/releases/{release_id}/holds",
            run_id=run_id,
            idem=idempotency_key,
            json={"slot_id": slot_id, "quantity": quantity, "ttl_s": ttl_s},
        )

    @mcp.tool(description="Check a hold's status (active | released | expired).")
    async def get_hold(hold_id: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", f"/venue/holds/{hold_id}", run_id=run_id)

    @mcp.tool(description="Release a hold back to inventory.")
    async def release_hold(hold_id: str, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        return await _call(client, "DELETE", f"/venue/holds/{hold_id}", run_id=run_id, idem=idempotency_key)

    @mcp.tool(description="Confirm a booking against an active hold and a captured payment.")
    async def confirm_booking(
        hold_id: str,
        payment_id: str,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        return await _call(
            client,
            "POST",
            "/venue/bookings",
            run_id=run_id,
            idem=idempotency_key,
            json={"hold_id": hold_id, "payment_id": payment_id},
        )

    @mcp.tool(description="Declare interest: write a bid into a release's pool.")
    async def declare_interest(
        release_id: str,
        declaration_id: str,
        acceptable_slot_ids: list[str],
        group_size: int,
        min_group_size: int,
        max_price_paise: int,
        user_contact: str | None = None,
        mandate_id: str | None = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        return await _call(
            client,
            "POST",
            f"/venue/releases/{release_id}/declarations",
            run_id=run_id,
            idem=idempotency_key,
            json={
                "declaration_id": declaration_id,
                "acceptable_slot_ids": acceptable_slot_ids,
                "group_size": group_size,
                "min_group_size": min_group_size,
                "max_price_paise": max_price_paise,
                "user_contact": user_contact,
                "mandate_id": mandate_id,
            },
        )

    @mcp.tool(description="List the release's declared-interest pool (one entry per pending bid).")
    async def list_pool_entries(release_id: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", f"/venue/releases/{release_id}/declarations", run_id=run_id)

    @mcp.tool(description="Remove a declaration from the pool.")
    async def cancel_declaration(
        release_id: str, declaration_id: str, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None
    ) -> dict:
        return await _call(
            client,
            "DELETE",
            f"/venue/releases/{release_id}/declarations/{declaration_id}",
            run_id=run_id,
            idem=idempotency_key,
        )


def _pinelabs(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(
        description=(
            "Reserve (authorise) an amount on the customer's mandate. Give the amount in paise as the integer "
            "argument `amount_value` (the alias `amount` is also accepted), e.g. amount_value=120000 for Rs 1,200."
        )
    )
    async def create_mandate(
        amount_value: int | None = None,
        amount: int | None = None,
        currency: str = "INR",
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        value = amount_value if amount_value is not None else amount
        if value is None:
            return {
                "status_code": 400,
                "body": {"error": {"code": "BAD_REQUEST", "message": "amount_value is required, in paise"}},
            }
        return await _call(
            client,
            "POST",
            "/pinelabs/mandates",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": int(value), "currency": currency}},
        )

    @mcp.tool(description="Read the remaining authorised balance for a mandate.")
    async def get_mandate_balance(authorization_id: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", f"/pinelabs/mandates/{authorization_id}/balance", run_id=run_id)

    @mcp.tool(
        description=(
            "Capture (charge) an amount against an active mandate. Give the amount in paise as the integer "
            "argument `amount_value` (the alias `amount` is also accepted), e.g. amount_value=120000 for Rs 1,200."
        )
    )
    async def execute(
        authorization_id: str,
        amount_value: int | None = None,
        amount: int | None = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        value = amount_value if amount_value is not None else amount
        if value is None:
            return {
                "status_code": 400,
                "body": {"error": {"code": "BAD_REQUEST", "message": "amount_value is required, in paise"}},
            }
        return await _call(
            client,
            "POST",
            f"/pinelabs/mandates/{authorization_id}/execute",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": int(value)}},
        )

    @mcp.tool(description="Release the mandate's unused reserved amount.")
    async def release(authorization_id: str, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        return await _call(
            client,
            "POST",
            f"/pinelabs/mandates/{authorization_id}/release",
            run_id=run_id,
            idem=idempotency_key,
            json={},
        )

    @mcp.tool(description="Refund a captured payment.")
    async def refund(payment_id: str, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        return await _call(
            client,
            "POST",
            f"/pinelabs/payments/{payment_id}/refund",
            run_id=run_id,
            idem=idempotency_key,
            json={},
        )


def _allocator(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(
        description="Run the DIFD draw for a release's pool. Deterministic for a given (release, window_open_iso)."
    )
    async def draw(
        release_id: str,
        bids: list[dict],
        window_open_iso: str | None = None,
        run_id: str = DEFAULT_RUN,
        idempotency_key: str | None = None,
    ) -> dict:
        payload: dict = {"release_id": release_id, "bids": bids}
        if window_open_iso:
            payload["window_open_iso"] = window_open_iso
        return await _call(client, "POST", "/allocator/draw", run_id=run_id, idem=idempotency_key, json=payload)


def _delhivery(mcp: MCPServer, client: httpx.AsyncClient) -> None:

    @mcp.tool(description="Pincode serviceability lookup (empty list means non-serviceable).")
    async def pincode_serviceability(filter_codes: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(
            client, "GET", "/delhivery/c/api/pin-codes/json/", run_id=run_id, params={"filter_codes": filter_codes}
        )

    @mcp.tool(description="Create a shipment from a Delhivery-shaped create payload.")
    async def create_shipment(data: str, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None) -> dict:
        return await _call(
            client,
            "POST",
            "/delhivery/api/cmu/create.json",
            run_id=run_id,
            idem=idempotency_key,
            json={"format": "json", "data": data},
        )

    @mcp.tool(description="Track a shipment by waybill.")
    async def track(waybill: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(
            client, "GET", "/delhivery/api/v1/packages/json/", run_id=run_id, params={"waybill": waybill}
        )


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
