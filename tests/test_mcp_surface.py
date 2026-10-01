"""MCP surface tests (ADR-012).

The MCP transport is HTTP, so these exercise a real uvicorn thread and a real MCP client
rather than the in-process TestClient. The point of the surface is that its tools are the
*same* code path as the REST routes, so the tests assert parity, not just "it responds".
"""

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mock_server.app import create_app

H = {"X-Run-Id": "mcp"}


@pytest.fixture
def mcp_base(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    server = uvicorn.Server(uvicorn.Config(create_app(str(tmp_path)), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=5)


@asynccontextmanager
async def session(url):
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


def payload(result):
    """Tool results are dicts; MCP v2 may carry them as structured content or TextContent."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and structured:
        return structured
    return json.loads(result.content[0].text)


def test_each_surface_exposes_its_tools(mcp_base):
    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            names = {t.name for t in (await s.list_tools()).tools}
        async with session(f"{mcp_base}/pinelabs/mcp") as s:
            names |= {t.name for t in (await s.list_tools()).tools}
        async with session(f"{mcp_base}/allocator/mcp") as s:
            names |= {t.name for t in (await s.list_tools()).tools}
        async with session(f"{mcp_base}/delhivery/mcp") as s:
            names |= {t.name for t in (await s.list_tools()).tools}
        return names

    names = asyncio.run(go())
    assert {
        "get_release",
        "list_releases",
        "create_hold",
        "get_hold",
        "release_hold",
        "confirm_booking",
        "declare_interest",
        "list_pool_entries",
        "cancel_declaration",
        "create_mandate",
        "get_mandate_balance",
        "execute",
        "release",
        "refund",
        "draw",
        "pincode_serviceability",
        "create_shipment",
        "track",
    } <= names

    # Surfaces are separated, so one connector never exposes another's tools.
    async def venue_only():
        async with session(f"{mcp_base}/venue/mcp") as s:
            return {t.name for t in (await s.list_tools()).tools}

    assert "draw" not in asyncio.run(venue_only())


def test_declare_via_mcp_is_visible_to_rest(mcp_base):
    """The whole point: MCP tools and REST routes share one state store."""

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            return payload(
                await s.call_tool(
                    "declare_interest",
                    {
                        "release_id": "rel_tennis_sat",
                        "declaration_id": "d_mcp",
                        "acceptable_slot_ids": ["tn_0900"],
                        "group_size": 4,
                        "min_group_size": 4,
                        "max_price_paise": 60000,
                        "run_id": "mcp",
                    },
                )
            )

    body = asyncio.run(go())
    assert body["status_code"] == 200
    assert body["body"] == {"declaration_id": "d_mcp", "release_id": "rel_tennis_sat", "status": "DECLARED"}

    listed = httpx.get(f"{mcp_base}/venue/releases/rel_tennis_sat/declarations", headers=H, timeout=10).json()
    assert [d["declaration_id"] for d in listed["declarations"]] == ["d_mcp"]

    # ...and the pool feeds the draw endpoint the Workflow will call.
    drawn = httpx.post(
        f"{mcp_base}/allocator/draw",
        headers=H,
        timeout=10,
        json={
            "release_id": "rel_tennis_sat",
            "bids": [
                {
                    "declaration_id": "d_mcp",
                    "user_id": "u1",
                    "acceptable_slot_ids": ["tn_0900"],
                    "group_size": 4,
                    "min_group_size": 4,
                    "max_price_paise": 60000,
                }
            ],
        },
    ).json()
    assert drawn["results"][0]["status"] == "ALLOCATED"


def test_mcp_write_tools_replay_idempotency_keys(mcp_base):
    async def go():
        async with session(f"{mcp_base}/pinelabs/mcp") as s:
            args = {"amount_value": 100000, "run_id": "mcp", "idempotency_key": "mk1"}
            first = payload(await s.call_tool("create_mandate", args))
            second = payload(await s.call_tool("create_mandate", args))
            return first, second

    first, second = asyncio.run(go())
    assert first["status_code"] == 200
    assert first["body"]["authorizationId"] == second["body"]["authorizationId"]


def test_mcp_tool_surfaces_failures_not_exceptions(mcp_base):
    async def go():
        async with session(f"{mcp_base}/pinelabs/mcp") as s:
            return payload(await s.call_tool("execute", {"authorization_id": "auth_nope", "amount_value": 1}))

    out = asyncio.run(go())
    assert out["status_code"] == 404
    assert out["body"]["error"]["code"] == "NOT_FOUND"


def test_mcp_host_header_allow_list(mcp_base):
    """Regression for the first deploy: MCP validates the Host header (DNS-rebinding protection) and
    `streamable_http_app` defaults the allow-list to 127.0.0.1, so behind the ingress every call was
    rejected with `421 Invalid Host header`. The public host must be allowed; a foreign one must not.
    """
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    base = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    blocked = httpx.post(f"{mcp_base}/venue/mcp", json=body, headers={**base, "Host": "evil.example.com"}, timeout=10)
    assert blocked.status_code == 421

    allowed = httpx.post(
        f"{mcp_base}/venue/mcp", json=body, headers={**base, "Host": "api-kirro.upayan.dev"}, timeout=10
    )
    assert allowed.status_code != 421
