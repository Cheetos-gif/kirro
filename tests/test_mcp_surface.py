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
def mcp_server(tmp_path):
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
    yield f"http://127.0.0.1:{port}", tmp_path
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture
def mcp_base(mcp_server):
    return mcp_server[0]


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
                        "acceptable_slot_ids": "tn_0900",
                        "group_size": 4,
                        "min_group_size": 4,
                        "max_price_paise": 60000,
                        "run_id": "mcp",
                    },
                )
            )

    body = asyncio.run(go())
    assert body["status_code"] == 200
    assert body["body"] == {
        "declaration_id": "decl_mcp_rel_tennis_sat",
        "release_id": "rel_tennis_sat",
        "status": "DECLARED",
    }

    listed = httpx.get(f"{mcp_base}/venue/releases/rel_tennis_sat/declarations", headers=H, timeout=10).json()
    assert [d["declaration_id"] for d in listed["declarations"]] == ["decl_mcp_rel_tennis_sat"]

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


def test_aggregate_surface_serves_every_tool(mcp_base):
    """`/all/mcp` exists because AgenticOrg scopes only one untrusted custom connector per agent, so
    the Declare Agent must be able to reach every tool through a single connector."""

    async def go():
        async with session(f"{mcp_base}/all/mcp") as s:
            return sorted(t.name for t in (await s.list_tools()).tools)

    names = asyncio.run(go())
    assert len(names) == 18
    assert {
        "get_release",
        "declare_interest",
        "create_mandate",
        "get_mandate_balance",
        "draw",
        "track",
    } <= set(names)


def test_mandate_tools_accept_the_amount_alias(mcp_base):
    """Live, the platform validated our schema and the model had not supplied `amount_value`, which surfaced as
    "The amount value is missing". Every shape a model plausibly emits must work - the `amount` alias, a nested
    `{"value": ...}` object, and a numeric string - and omitting everything must be a clean 400 that echoes what
    actually arrived instead of a platform-side validation error."""

    async def go():
        async with session(f"{mcp_base}/pinelabs/mcp") as s:
            by_alias = payload(await s.call_tool("create_mandate", {"amount": 123400}))
            nested = payload(await s.call_tool("create_mandate", {"amount_value": {"value": 5500}}))
            as_string = payload(await s.call_tool("create_mandate", {"amount_value": "7000"}))
            missing = payload(await s.call_tool("create_mandate", {}))
            charged = payload(
                await s.call_tool(
                    "execute",
                    {"authorization_id": by_alias["body"]["authorizationId"], "amount": 1000},
                )
            )
            return by_alias, nested, as_string, missing, charged

    by_alias, nested, as_string, missing, charged = asyncio.run(go())
    assert by_alias["status_code"] == 200 and by_alias["body"]["amount"]["value"] == 123400
    assert nested["status_code"] == 200 and nested["body"]["amount"]["value"] == 5500
    assert as_string["status_code"] == 200 and as_string["body"]["amount"]["value"] == 7000
    assert missing["status_code"] == 400 and missing["body"]["error"]["code"] == "BAD_REQUEST"
    assert "amount_value=None" in missing["body"]["error"]["message"]
    assert charged["status_code"] == 200 and charged["body"]["status"] == "SUCCESS"


def test_lookup_and_bid_tools_accept_model_shaped_arguments(mcp_base):
    """Live, the agent's release lookup and pool declare were both rejected before reaching the mock, so it told the
    user the lookup had failed. A free-text event, a date, a single slot id as a string, numbers as strings, and an
    omitted declaration id must all work."""

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            listed = payload(await s.call_tool("list_releases", {"event": "badminton"}))
            fetched = payload(await s.call_tool("get_release", {"release_id": "badminton"}))
            bid = payload(
                await s.call_tool(
                    "declare_interest",
                    {
                        "release_id": "rel_badminton_sat",
                        "acceptable_slot_ids": "bd_0700",
                        "group_size": 4,
                        "min_group_size": 2,
                        "max_price_paise": 30000,
                    },
                )
            )
            return listed, fetched, bid

    listed, fetched, bid = asyncio.run(go())
    assert [item["release_id"] for item in listed["body"]["releases"]] == ["rel_badminton_sat"]
    assert fetched["body"]["release_id"] == "rel_badminton_sat" and fetched["body"]["slots"]
    assert bid["status_code"] == 200 and bid["body"]["status"] == "DECLARED"
    assert bid["body"]["declaration_id"]


def test_lookup_survives_a_misresolved_date_and_a_bid_without_slots(mcp_base):
    """Live, the agent resolved "this Saturday" to 2026-10-07 while the badminton release is dated 2026-10-03. A
    strict date filter then left it with no release id and no slot ids, so the pool entry was dropped entirely —
    the user was told the declaration failed. The lookup must stay reachable, and the bid must not need slot ids."""

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            listed = payload(await s.call_tool("list_releases", {"event": "badminton", "date": "2026-10-07"}))
            fetched = payload(await s.call_tool("get_release", {"release_id": "badminton"}))
            bid = payload(
                await s.call_tool(
                    "declare_interest",
                    {
                        "release_id": "badminton",
                        "group_size": 4,
                        "min_group_size": 2,
                        "max_price_paise": 30000,
                    },
                )
            )
            return listed, fetched, bid

    listed, fetched, bid = asyncio.run(go())
    assert [item["release_id"] for item in listed["body"]["releases"]] == ["rel_badminton_sat"]
    assert fetched["body"]["release_id"] == "rel_badminton_sat"
    assert bid["status_code"] == 200 and bid["body"]["status"] == "DECLARED"


def test_no_model_facing_parameter_carries_a_type_or_concrete_default(mcp_base):
    """AgenticOrg appears to prefill a tool call's arguments from the JSON-schema defaults: a parameter declared with
    a concrete type and default arrives empty or zero however the model chose it, while `Any = None` lets the model's
    value through — the cause behind `docs/agenticorg/platform-map.md` §11, which cost hours and produced a bid with
    a zero group size. Every parameter the model is expected to fill must therefore stay untyped with a null default.

    `run_id`, `idempotency_key` and `currency` are exempt: they are plumbing we supply, not values the model chooses.
    """
    exempt = {"run_id", "idempotency_key", "currency"}

    async def go():
        async with session(f"{mcp_base}/all/mcp") as s:
            schemas = {}
            for tool in (await s.list_tools()).tools:
                schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
                schemas[tool.name] = schema if isinstance(schema, dict) else schema.model_dump()
            return schemas

    offenders = {}
    for name, schema in asyncio.run(go()).items():
        bad = [
            param
            for param, spec in (schema.get("properties") or {}).items()
            if param not in exempt and ("type" in spec or spec.get("default") is not None)
        ]
        if bad:
            offenders[name] = bad
    assert offenders == {}, f"typed parameters discard the model's values: {offenders}"


def test_draw_accepts_bids_as_a_json_string(mcp_base):
    """The model sends an array parameter as a JSON string as often as a list; both must reach the allocator."""

    async def go():
        async with session(f"{mcp_base}/allocator/mcp") as s:
            bids = [
                {
                    "declaration_id": "d1",
                    "user_id": "u1",
                    "acceptable_slot_ids": ["bd_0700"],
                    "group_size": 4,
                    "min_group_size": 4,
                    "max_price_paise": 30000,
                }
            ]
            as_string = payload(
                await s.call_tool("draw", {"release_id": "rel_badminton_sat", "bids": json.dumps(bids)})
            )
            as_list = payload(await s.call_tool("draw", {"release_id": "rel_badminton_sat", "bids": bids}))
            return as_string, as_list

    as_string, as_list = asyncio.run(go())
    assert as_string["status_code"] == 200
    assert as_string["body"] == as_list["body"]
    assert as_string["body"]["results"][0]["status"] == "ALLOCATED"


def test_pool_and_draw_resolve_their_release_from_the_bids(mcp_base):
    """Live, the model calls list_pool_entries — and then draw — with a null release_id, however often the refusal
    names the candidates and whatever the conversation says, so the pool never reached the allocator. The mock
    resolves the release from data it already holds: the pool that actually has bids, and for the draw the release
    whose pool holds the named declarations."""

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            await s.call_tool(
                "declare_interest",
                {"release_id": "rel_badminton_sat", "group_size": 4, "min_group_size": 2, "max_price_paise": 30000},
            )
            pool = payload(await s.call_tool("list_pool_entries", {}))
        async with session(f"{mcp_base}/allocator/mcp") as s:
            # Copied off the pool exactly as the model copies it — no user_id, since the pool entry has none. An
            # earlier version of this test added one by hand and so missed the KeyError the live run hit.
            bids = [
                {
                    "declaration_id": entry["declaration_id"],
                    "acceptable_slot_ids": entry["acceptable_slot_ids"],
                    "group_size": entry["group_size"],
                    "min_group_size": entry["min_group_size"],
                    "max_price_paise": entry["max_price_paise"],
                }
                for entry in pool["body"]["declarations"]
            ]
            drawn = payload(await s.call_tool("draw", {"bids": bids}))
            return pool, drawn

    pool, drawn = asyncio.run(go())
    assert pool["status_code"] == 200 and pool["body"]["release_id"] == "rel_badminton_sat"
    assert drawn["status_code"] == 200 and drawn["body"]["release_id"] == "rel_badminton_sat"
    assert drawn["body"]["results"][0]["status"] == "ALLOCATED"


def test_a_bid_without_a_mandate_id_carries_the_run_s_most_recent_one(mcp_base):
    """Live, the model reserves the mandate and then bids without ever passing its authorization id, so the pool
    entry the allocation captures against had no mandate — the allocator drew, held the slot, and then stopped. A
    bid without a mandate id takes the run's most recently created mandate."""

    async def go():
        async with session(f"{mcp_base}/pinelabs/mcp") as s:
            mandate = payload(await s.call_tool("create_mandate", {"amount_value": 100000}))
        async with session(f"{mcp_base}/venue/mcp") as v:
            await v.call_tool(
                "declare_interest",
                {"release_id": "rel_badminton_sat", "group_size": 4, "min_group_size": 2, "max_price_paise": 30000},
            )
            pool = payload(await v.call_tool("list_pool_entries", {"release_id": "rel_badminton_sat"}))
        return mandate, pool

    mandate, pool = asyncio.run(go())
    entry = pool["body"]["declarations"][0]
    assert entry["mandate_id"] == mandate["body"]["authorizationId"]


def test_every_tool_invocation_is_logged_with_the_arguments_received(mcp_server):
    """A guard that answers inside the tool used to leave no trace at all, so a call the platform made and we
    rejected was indistinguishable from one it never sent. The arguments as received must land in the run log."""
    base, log_dir = mcp_server

    async def go():
        async with session(f"{base}/all/mcp") as s:
            await s.call_tool("list_releases", {"event": "badminton"})
            await s.call_tool(
                "declare_interest",
                {"release_id": "no-such-release", "group_size": 4, "min_group_size": 2, "max_price_paise": 30000},
            )
            # Every one of these is refused by its own guard; each must still leave a trace, or a refusal is
            # indistinguishable from a call the platform never made.
            for tool in ("create_hold", "list_pool_entries", "draw", "execute", "confirm_booking", "track"):
                await s.call_tool(tool, {})

    asyncio.run(go())
    lines = [json.loads(line) for line in (log_dir / "default.jsonl").read_text().splitlines()]
    tools = {line["target"]: line["request"] for line in lines if line["target"].startswith("mcp.")}
    assert tools["mcp.list_releases"] == {"event": "badminton", "date": None}
    # The guard rejected the bid, but what it did receive is recorded rather than silently dropped.
    assert tools["mcp.declare_interest"]["release_id"] == "no-such-release"
    assert tools["mcp.declare_interest"]["max_price_paise"] == 30000
    for tool in ("create_hold", "list_pool_entries", "draw", "execute", "confirm_booking", "track"):
        assert f"mcp.{tool}" in tools, f"{tool} refused without logging"


def test_an_empty_release_lookup_returns_the_candidates(mcp_base):
    """Live, the model calls get_release with no argument at all, and the platform rejects a missing *required*
    parameter before the call reaches us — leaving the agent with an error and no ids. The empty lookup must
    answer with the releases instead."""

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            return payload(await s.call_tool("get_release", {}))

    body = asyncio.run(go())
    assert body["status_code"] == 200
    assert {item["release_id"] for item in body["body"]["releases"]} >= {"rel_badminton_sat", "rel_tennis_sat"}


def _future_tennis_release(base, date, key):
    body = {
        "event_id": "ev_tennis",
        "date": date,
        "opens_at": f"{date[:-2]}01T06:00:00Z",
        "slots": [
            {"label": "Court 3", "starts_at": f"{date}T09:00:00Z", "capacity": 4, "price_per_person_paise": 50000}
        ],
    }
    created = httpx.post(f"{base}/venue/releases", json=body, headers={**H, "Idempotency-Key": key}, timeout=10)
    return created.json()["release_id"]


def test_an_event_word_resolves_to_the_one_release_still_open(mcp_base):
    """ "tennis" matches the past fixture release and any future one. The agent must land on the one that can still
    take declarations, through both the lookup and the bid; with two open, it gets the list with dates instead."""
    open_id = _future_tennis_release(mcp_base, "2099-01-10", "t1")

    async def go():
        async with session(f"{mcp_base}/venue/mcp") as s:
            looked = payload(await s.call_tool("get_release", {"release_id": "tennis", "run_id": "mcp"}))
            bid = payload(
                await s.call_tool(
                    "declare_interest",
                    {
                        "release_id": "tennis",
                        "group_size": 2,
                        "min_group_size": 2,
                        "max_price_paise": 50000,
                        "run_id": "mcp",
                    },
                )
            )
            return looked, bid

    looked, bid = asyncio.run(go())
    assert looked["status_code"] == 200 and looked["body"]["release_id"] == open_id
    assert looked["body"]["declarations_open"] is True
    assert bid["body"]["release_id"] == open_id and bid["body"]["status"] == "DECLARED"

    _future_tennis_release(mcp_base, "2099-02-10", "t2")

    async def ambiguous():
        async with session(f"{mcp_base}/venue/mcp") as s:
            return payload(await s.call_tool("get_release", {"release_id": "tennis", "run_id": "mcp"}))

    listed = asyncio.run(ambiguous())
    assert listed["status_code"] == 404
    assert {item["date"] for item in listed["body"]["releases"]} == {"2026-10-03", "2099-01-10", "2099-02-10"}
