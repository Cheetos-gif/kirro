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

from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

DEFAULT_RUN = "default"

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


def _venue(client: httpx.AsyncClient) -> MCPServer:
    mcp = MCPServer("venue_inventory", instructions=SURFACE_INSTRUCTIONS["venue"])

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

    return mcp


def _pinelabs(client: httpx.AsyncClient) -> MCPServer:
    mcp = MCPServer("pine_labs_mandate", instructions=SURFACE_INSTRUCTIONS["pinelabs"])

    @mcp.tool(description="Reserve (authorise) an amount on the customer's mandate.")
    async def create_mandate(
        amount_value: int, currency: str = "INR", run_id: str = DEFAULT_RUN, idempotency_key: str | None = None
    ) -> dict:
        return await _call(
            client,
            "POST",
            "/pinelabs/mandates",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": amount_value, "currency": currency}},
        )

    @mcp.tool(description="Read the remaining authorised balance for a mandate.")
    async def get_mandate_balance(authorization_id: str, run_id: str = DEFAULT_RUN) -> dict:
        return await _call(client, "GET", f"/pinelabs/mandates/{authorization_id}/balance", run_id=run_id)

    @mcp.tool(description="Capture (charge) against an active mandate.")
    async def execute(
        authorization_id: str, amount_value: int, run_id: str = DEFAULT_RUN, idempotency_key: str | None = None
    ) -> dict:
        return await _call(
            client,
            "POST",
            f"/pinelabs/mandates/{authorization_id}/execute",
            run_id=run_id,
            idem=idempotency_key,
            json={"amount": {"value": amount_value}},
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

    return mcp


def _allocator(client: httpx.AsyncClient) -> MCPServer:
    mcp = MCPServer("difd_allocator", instructions=SURFACE_INSTRUCTIONS["allocator"])

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

    return mcp


def _delhivery(client: httpx.AsyncClient) -> MCPServer:
    mcp = MCPServer("delhivery_mock", instructions=SURFACE_INSTRUCTIONS["delhivery"])

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

    return mcp


BUILDERS = {"venue": _venue, "pinelabs": _pinelabs, "allocator": _allocator, "delhivery": _delhivery}


def build_surfaces(app: Any) -> dict[str, MCPServer]:
    """Build one MCP server per surface. Mount each at `/<surface>/mcp`."""
    client = _client(app)
    return {name: builder(client) for name, builder in BUILDERS.items()}
