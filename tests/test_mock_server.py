import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from mock_server.app import create_app


def H(run="r", key=None):
    h = {"X-Run-Id": run, "X-Request-Id": "req-1"}
    if key:
        h["Idempotency-Key"] = key
    return h


def scenario(c, run="r", target="*", s="success", **kw):
    assert c.post("/__admin/scenario", json={"run_id": run, "target": target, "scenario": s, **kw}).status_code == 200


def hold_body(qty=2, slot="bd_0700"):
    return {"declaration_id": "d", "slot_id": slot, "quantity": qty, "ttl_s": 600}


def test_health_and_catalogue(mock_client):
    assert mock_client.get("/health").json()["status"] == "ok"
    assert len(mock_client.get("/venue/catalogue").json()["events"]) == 4


def test_admin_routes_are_open_when_no_admin_key_is_configured(mock_client):
    """The default today, until an operator provisions `MOCK_ADMIN_KEY` (#12 item 2): shipping the
    guard must not lock an existing deployment out of its own harness."""
    assert mock_client.post("/__admin/scenario", json={"run_id": "r", "scenario": "success"}).status_code == 200
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).status_code == 200
    assert mock_client.post("/__admin/reset", json={"run_id": "r"}).status_code == 200


def test_admin_routes_require_the_configured_admin_key(mock_client, monkeypatch):
    """`/__admin/*` answered unauthenticated on the public mock URL (#12 item 2). With the key set, a
    call must carry a matching `X-Admin-Key`; the agent is never told this header exists."""
    monkeypatch.setenv("MOCK_ADMIN_KEY", "harness-secret")
    no_key = mock_client.get("/__admin/state", params={"run_id": "r"})
    assert no_key.status_code == 403 and no_key.json()["error"]["code"] == "FORBIDDEN"
    wrong_key = mock_client.post(
        "/__admin/scenario", json={"run_id": "r", "scenario": "success"}, headers={"X-Admin-Key": "nope"}
    )
    assert wrong_key.status_code == 403
    assert mock_client.post("/__admin/reset", json={"run_id": "r"}).status_code == 403

    ok = mock_client.get("/__admin/state", params={"run_id": "r"}, headers={"X-Admin-Key": "harness-secret"})
    assert ok.status_code == 200


def test_unknown_scenario_rejected(mock_client):
    r = mock_client.post("/__admin/scenario", json={"run_id": "r", "scenario": "nope"})
    assert r.status_code == 422


def test_no_response_ever_names_a_scenario(mock_client):
    for s in ("success", "no_inventory", "insufficient_balance", "payment_failure", "partial_group", "booking_expired"):
        scenario(mock_client, s=s)
        for r in (
            mock_client.get("/venue/releases/rel_badminton_sat", headers=H()),
            mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key=s)),
            mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100, "currency": "INR"}}, headers=H()),
        ):
            assert "scenario" not in r.text.lower() and "mock" not in r.text.lower()
            assert "scenario" not in {k.lower() for k in r.headers}


def test_happy_hold_booking_flow_and_idempotency(mock_client):
    a = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k1")).json()
    b = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k1")).json()
    assert a == b and a["hold_id"] == "hold_0001"
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).json()["holds"] == 1
    m = mock_client.post(
        "/pinelabs/mandates", json={"amount": {"value": 100000, "currency": "INR"}}, headers=H(key="m")
    ).json()
    p = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="p")
    ).json()
    assert p["status"] == "SUCCESS"
    bk = mock_client.post(
        "/venue/bookings", json={"hold_id": a["hold_id"], "payment_id": p["payment_id"]}, headers=H(key="b")
    )
    assert bk.json()["booking_ref"] == "BK-0001"


def test_movie_release_is_bookable(mock_client):
    """ev_movie has a catalogue entry but previously had no release at all -- NOT_FOUND on every call."""
    releases = mock_client.get("/venue/releases", params={"event_id": "ev_movie"}).json()["releases"]
    assert len(releases) == 1
    r = releases[0]
    # Fixture dates are seeded relative to this test run's own clock (mock_server/state.py
    # `_seed_domain`, #12 item 3), not pinned to a calendar date, so a fresh seed is always open.
    assert r["release_id"] == "rel_movie_fri" and r["event_id"] == "ev_movie"
    assert r["allocation_mode"] == "fair_draw" and r["declarations_open"] is True and r["drawn"] is False
    assert r["weekday"] in (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    assert r["opens_at_ist"].endswith("+05:30")
    a = mock_client.post(
        "/venue/releases/rel_movie_fri/holds", json=hold_body(qty=2, slot="mv_1900"), headers=H(key="k1")
    ).json()
    assert a["hold_id"] == "hold_0001" and a["price_per_unit_paise"] == 25000
    m = mock_client.post(
        "/pinelabs/mandates", json={"amount": {"value": 50000, "currency": "INR"}}, headers=H(key="m")
    ).json()
    p = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="p")
    ).json()
    assert p["status"] == "SUCCESS"
    bk = mock_client.post(
        "/venue/bookings", json={"hold_id": a["hold_id"], "payment_id": p["payment_id"]}, headers=H(key="b")
    )
    assert bk.json()["booking_ref"] == "BK-0001"


def test_booking_requires_captured_payment(mock_client):
    a = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k")).json()
    r = mock_client.post(
        "/venue/bookings", json={"hold_id": a["hold_id"], "payment_id": "pay_9999"}, headers=H(key="b")
    )
    assert r.status_code == 402 and r.json()["error"]["code"] == "PAYMENT_REQUIRED"


@pytest.mark.parametrize(
    "s,target,method,path,body,status,code",
    [
        ("no_inventory", "venue.hold", "post", "/venue/releases/rel_badminton_sat/holds", hold_body(), 409, "SOLD_OUT"),
        (
            "partial_group",
            "venue.hold",
            "post",
            "/venue/releases/rel_badminton_sat/holds",
            hold_body(4),
            409,
            "INSUFFICIENT_CAPACITY",
        ),
        ("upstream_500", "venue.release", "get", "/venue/releases/rel_badminton_sat", None, 500, "INTERNAL"),
        (
            "insufficient_balance",
            "pinelabs.create_mandate",
            "post",
            "/pinelabs/mandates",
            {"amount": {"value": 5}},
            402,
            "INSUFFICIENT_BALANCE",
        ),
    ],
)
def test_failure_scenarios(mock_client, s, target, method, path, body, status, code):
    scenario(mock_client, target=target, s=s)
    r = getattr(mock_client, method)(path, headers=H(), **({"json": body} if body else {}))
    assert r.status_code == status and r.json()["error"]["code"] == code


def test_payment_failure_body(mock_client):
    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H()).json()
    scenario(mock_client, target="pinelabs.execute", s="payment_failure")
    r = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 1000}}, headers=H(key="x")
    ).json()
    assert r["status"] == "FAILED" and r["reason"] == "BANK_DECLINED"


def test_pinelabs_real_callout_is_a_noop_when_unconfigured(mock_client):
    """Default state, and every other test in this file: no PINELABS_CLIENT_ID/SECRET, so the
    capture/refund responses carry no `real_order`/`real_refund` key at all (ADR-019) — this is
    the regression test that guards `uv run pytest` staying network-free."""
    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H()).json()
    p = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="e")
    ).json()
    assert p["status"] == "SUCCESS" and "real_order" not in p
    r = mock_client.post(f"/pinelabs/payments/{p['payment_id']}/refund", headers=H(key="rf")).json()
    assert r["status"] == "REFUNDED" and "real_refund" not in r


def test_pinelabs_real_callout_fronts_capture_and_refund(mock_client, monkeypatch):
    """With real credentials configured (stubbed transport, no real network — ADR-019), a
    successful capture also places a real UAT order and a refund places a real UAT refund,
    surfaced as `real_order`/`real_refund` alongside the mock's own response."""
    import httpx

    import mock_server.app as app_module
    from mock_server.pinelabs_plural import RealPinelabsClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": "2099-01-01T00:00:00Z"})
        if "refunds" in request.url.path:
            return httpx.Response(200, json={"data": {"order_id": "rf_real_1", "status": "REFUND_INITIATED"}})
        return httpx.Response(200, json={"data": {"order_id": "ord_real_1", "status": "CREATED"}})

    stub = RealPinelabsClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://stub.local",
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(app_module, "get_real_pinelabs_client", lambda: stub)

    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H()).json()
    p = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="e")
    ).json()
    assert p["status"] == "SUCCESS" and p["real_order"] == {"order_id": "ord_real_1", "status": "CREATED"}
    r = mock_client.post(f"/pinelabs/payments/{p['payment_id']}/refund", headers=H(key="rf")).json()
    assert r["status"] == "REFUNDED"
    assert r["real_refund"] == {"order_id": "rf_real_1", "status": "REFUND_INITIATED"}


def test_pinelabs_real_callout_failure_does_not_break_the_mock_response(mock_client, monkeypatch):
    """A flaky/unreachable UAT sandbox must not fail the mock's own capture (ADR-019): the
    response stays 200 SUCCESS, with the real-call error surfaced, not raised."""
    import httpx

    import mock_server.app as app_module
    from mock_server.pinelabs_plural import RealPinelabsClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": "2099-01-01T00:00:00Z"})
        return httpx.Response(400, json={"error_code": "BAD_REQUEST", "message": "nope"})

    stub = RealPinelabsClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://stub.local",
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(app_module, "get_real_pinelabs_client", lambda: stub)

    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H()).json()
    p = mock_client.post(
        f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="e")
    ).json()
    assert p["status"] == "SUCCESS" and "error" in p["real_order"]


def test_malformed_returns_html_200_but_processes(mock_client):
    scenario(mock_client, target="venue.hold", s="malformed")
    r = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k"))
    assert r.status_code == 200 and "html" in r.headers["content-type"]
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).json()["holds"] == 1


def test_duplicate_scenario_on_replayed_key(mock_client):
    scenario(mock_client, target="venue.hold", s="duplicate")
    first = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k"))
    second = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k"))
    assert first.status_code == 200 and second.status_code == 409
    assert (
        second.json()["error"]["code"] == "DUPLICATE_REQUEST"
        and second.json()["original"]["hold_id"] == first.json()["hold_id"]
    )


def test_scenario_sequence_then_sticks(mock_client):
    mock_client.post(
        "/__admin/scenario", json={"run_id": "r", "target": "venue.release", "sequence": ["upstream_500", "success"]}
    )
    codes = [mock_client.get("/venue/releases/rel_badminton_sat", headers=H()).status_code for _ in range(3)]
    assert codes == [500, 200, 200]


def test_runs_are_isolated(mock_client):
    scenario(mock_client, run="a", s="upstream_500")
    assert mock_client.get("/venue/releases/rel_badminton_sat", headers=H("a")).status_code == 500
    assert mock_client.get("/venue/releases/rel_badminton_sat", headers=H("b")).status_code == 200


def test_delhivery_shapes(mock_client):
    ok = mock_client.get("/delhivery/c/api/pin-codes/json/", params={"filter_codes": "560001"}, headers=H()).json()
    assert ok["delivery_codes"][0]["postal_code"]["pin"] == 560001
    assert mock_client.get(
        "/delhivery/c/api/pin-codes/json/", params={"filter_codes": "999999"}, headers=H()
    ).json() == {"delivery_codes": []}
    data = {"format": "json", "data": json.dumps({"shipments": [{"order": "BK-1", "pin": "560001"}]})}
    c1 = mock_client.post("/delhivery/api/cmu/create.json", data=data, headers=H(key="1")).json()
    assert c1["success"] and c1["packages"][0]["waybill"].startswith("MOCKWB")
    c2 = mock_client.post("/delhivery/api/cmu/create.json", data=data, headers=H(key="2")).json()
    assert not c2["success"] and "Duplicate" in c2["rmk"]
    t = mock_client.get(
        "/delhivery/api/v1/packages/json/", params={"waybill": c1["packages"][0]["waybill"]}, headers=H()
    ).json()
    assert t["ShipmentData"][0]["Shipment"]["Status"]["Status"] == "Manifested"


def test_request_response_scenario_logged(tmp_path, capsys):
    from fastapi.testclient import TestClient

    c = TestClient(create_app(str(tmp_path)))
    c.post("/__admin/scenario", json={"run_id": "lg", "target": "venue.release", "scenario": "upstream_500"})
    capsys.readouterr()
    c.get("/venue/releases/rel_badminton_sat", headers=H("lg"))
    rec = json.loads((tmp_path / "lg.jsonl").read_text().splitlines()[0])
    assert {"ts", "request_id", "path", "scenario", "request", "response", "status", "latency_ms"} <= set(rec)
    assert rec["scenario"] == "upstream_500" and rec["request_id"] == "req-1" and rec["status"] == 500
    # The same record is teed to stdout, the only channel the cluster's log agent ships.
    out = [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]
    assert out == [rec]


@pytest.fixture
def live_url(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    server = uvicorn.Server(uvicorn.Config(create_app(str(tmp_path)), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=3)


def test_timeout_and_delayed_scenarios_over_real_http(live_url):
    c = httpx.Client(base_url=live_url, headers={"X-Run-Id": "rt"})
    c.post("/__admin/scenario", json={"run_id": "rt", "target": "venue.release", "scenario": "timeout", "delay_s": 0.6})
    with pytest.raises(httpx.TimeoutException):
        c.get("/venue/releases/rel_badminton_sat", timeout=0.2)
    c.post("/__admin/scenario", json={"run_id": "rt", "target": "venue.release", "scenario": "delayed", "delay_s": 0.3})
    t0 = time.monotonic()
    r = c.get("/venue/releases/rel_badminton_sat", timeout=2)
    assert r.status_code == 200 and (time.monotonic() - t0) >= 0.25


def draw_body(bids=None, release="rel_tennis_sat"):
    return {"release_id": release, "window_open_iso": "2026-10-02T06:00:00Z", "bids": bids or []}


def bid(declaration_id, user_id, group=4, min_group=None, price=60000, slots=None):
    return {
        "declaration_id": declaration_id,
        "user_id": user_id,
        "acceptable_slot_ids": slots or ["tn_0900"],
        "group_size": group,
        "min_group_size": min_group if min_group is not None else group,
        "max_price_paise": price,
    }


def test_allocator_draw_allocates_then_waitlists_a_full_slot(mock_client):
    bids = [bid("d1", "u1"), bid("d2", "u2")]  # one 4-seat slot, two 4-person bids
    r = mock_client.post("/allocator/draw", json=draw_body(bids), headers=H(key="k1"))
    assert r.status_code == 200
    body = r.json()
    assert body["release_id"] == "rel_tennis_sat"
    results = {x["declaration_id"]: x for x in body["results"]}
    statuses = sorted(x["status"] for x in results.values())
    assert statuses == ["ALLOCATED", "WAITLISTED"]
    winner = next(x for x in results.values() if x["status"] == "ALLOCATED")
    loser = next(x for x in results.values() if x["status"] == "WAITLISTED")
    assert winner["slot_id"] == "tn_0900" and winner["group_size_allocated"] == 4
    assert loser["slot_id"] is None and loser["group_size_allocated"] == 0
    assert all(x["seed"] for x in results.values())
    # deterministic: same inputs -> same draw order and statuses
    again = mock_client.post("/allocator/draw", json=draw_body(bids), headers=H(key="k2")).json()
    assert [x["declaration_id"] for x in again["results"]] == [x["declaration_id"] for x in body["results"]]
    assert [x["status"] for x in again["results"]] == [x["status"] for x in body["results"]]


def test_allocator_draw_unknown_release(mock_client):
    r = mock_client.post("/allocator/draw", json=draw_body(release="rel_nope"), headers=H())
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_allocator_draw_marks_the_release_drawn(mock_client):
    """The allocator-trigger bridge (ADR-018) reads `drawn` back to know a release never needs asking about
    again; it must flip on a real draw and stay off when the draw never actually ran."""
    assert mock_client.get("/venue/releases/rel_tennis_sat", headers=H()).json()["drawn"] is False
    mock_client.post("/allocator/draw", json=draw_body([bid("d1", "u1")]), headers=H(key="k1"))
    assert mock_client.get("/venue/releases/rel_tennis_sat", headers=H()).json()["drawn"] is True
    assert any(
        r["drawn"]
        for r in mock_client.get("/venue/releases", headers=H()).json()["releases"]
        if r["release_id"] == "rel_tennis_sat"
    )

    scenario(mock_client, target="allocator.draw", s="upstream_500")
    r = mock_client.post(
        "/allocator/draw", json=draw_body([bid("d2", "u2")], release="rel_badminton_sat"), headers=H(key="k2")
    )
    assert r.status_code == 500
    assert mock_client.get("/venue/releases/rel_badminton_sat", headers=H()).json()["drawn"] is False


def declare_body(**over):
    return {
        "declaration_id": "dec_1",
        "user_contact": "+91-9000000000",
        "notify_phone": "+919000000000",
        "mandate_id": "auth_0001",
        "acceptable_slot_ids": ["bd_0700", "bd_0800"],
        "group_size": 4,
        "min_group_size": 2,
        "max_price_paise": 30000,
    } | over


def test_declare_pool_round_trip(mock_client):
    body = declare_body()
    r = mock_client.post("/venue/releases/rel_badminton_sat/declarations", json=body, headers=H(key="d1"))
    assert r.status_code == 200
    assert r.json() == {"declaration_id": "dec_1", "release_id": "rel_badminton_sat", "status": "DECLARED"}

    listed = mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H())
    assert listed.status_code == 200 and listed.json()["release_id"] == "rel_badminton_sat"
    assert listed.json()["declarations"] == [body | {"status": "DECLARED"}]

    d = mock_client.delete("/venue/releases/rel_badminton_sat/declarations/dec_1", headers=H())
    assert d.status_code == 200 and d.json()["status"] == "CANCELLED"
    assert mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H()).json()["declarations"] == []
    assert mock_client.delete("/venue/releases/rel_badminton_sat/declarations/dec_1", headers=H()).status_code == 404


def test_declare_pool_second_call_with_same_declaration_id_is_a_no_op(mock_client):
    """L09: declaring twice with the same declaration_id must not be indistinguishable from the first
    call, and must not let a second body silently overwrite the stored bid (#12 item 6)."""
    body = declare_body()
    first = mock_client.post("/venue/releases/rel_badminton_sat/declarations", json=body, headers=H(key="d1"))
    assert first.json() == {"declaration_id": "dec_1", "release_id": "rel_badminton_sat", "status": "DECLARED"}

    second = mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations", json=declare_body(group_size=99), headers=H(key="d2")
    )
    assert second.status_code == 200
    assert second.json() == {
        "declaration_id": "dec_1",
        "release_id": "rel_badminton_sat",
        "status": "DECLARED",
        "duplicate": True,
    }
    # The second body's group_size must not have overwritten the first declaration.
    stored = mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H()).json()["declarations"]
    assert stored == [body | {"status": "DECLARED"}]


def test_declare_pool_refuses_a_closed_release(mock_client):
    """`declarations_open` tells the agent a window is shut; the REST route must refuse a bid too,
    not just advertise the field (#12 item 3)."""
    closed = instant_release_body(
        event_id="ev_tennis", date="2000-01-02", opens_at="2000-01-01T06:00:00Z", allocation_mode="fair_draw"
    )
    closed_id = mock_client.post("/venue/releases", json=closed, headers=H(key="r1")).json()["release_id"]
    r = mock_client.post(f"/venue/releases/{closed_id}/declarations", json=declare_body(), headers=H())
    assert r.status_code == 409 and r.json()["error"]["code"] == "POOL_CLOSED"
    assert mock_client.get(f"/venue/releases/{closed_id}/declarations", headers=H()).json()["declarations"] == []


@pytest.mark.parametrize(
    "over",
    [
        {"group_size": "four"},
        {"max_price_paise": None},
        {"acceptable_slot_ids": []},
        {"acceptable_slot_ids": "bd_0700"},
        {"min_group_size": 5},
        {"notify_phone": ""},
        {"notify_phone": "9876543210"},  # no country code, and no saved profile to fall back on
        {"notify_phone": "not a number"},
        {"notify_phone": "+91-abc"},
    ],
)
def test_declare_pool_rejects_bad_bid(mock_client, over):
    r = mock_client.post("/venue/releases/rel_badminton_sat/declarations", json=declare_body(**over), headers=H())
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_REQUEST"


def test_declare_pool_falls_back_to_the_number_saved_in_settings(mock_client):
    """The delivery address belongs to the account, not the bid: a signed-in caller who saved a number
    is never asked for it again, and the bid stores the resolved one."""
    mock_client.put("/venue/users/me@example.com/profile", json={"notify_phone": "+91 85097 01939"}, headers=H())
    r = mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations",
        json=declare_body(notify_phone=None, user_contact="me@example.com"),
        headers=H(key="d1"),
    )
    assert r.status_code == 200
    stored = mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H()).json()["declarations"]
    assert stored[0]["notify_phone"] == "+918509701939"

    # A number given on the bid itself still wins over the saved one.
    r = mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations",
        json=declare_body(declaration_id="dec_2", user_contact="me@example.com", notify_phone="+919111111111"),
        headers=H(key="d2"),
    )
    assert r.status_code == 200
    stored = mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H()).json()["declarations"]
    assert {d["declaration_id"]: d["notify_phone"] for d in stored}["dec_2"] == "+919111111111"

    # A contact with nothing saved is still refused.
    refused = mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations",
        json=declare_body(declaration_id="dec_3", user_contact="nobody@example.com", notify_phone=None),
        headers=H(key="d3"),
    )
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "BAD_REQUEST"


def test_declare_pool_normalises_a_phone_number_people_actually_type(mock_client):
    """The number is the one address the draw's result can be delivered to, so a number written the
    usual way (spaces, dashes, brackets, a leading 00) is stored as E.164 rather than refused."""
    r = mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations",
        json=declare_body(notify_phone="00 91 (98765) 43210"),
        headers=H(key="d1"),
    )
    assert r.status_code == 200
    stored = mock_client.get("/venue/releases/rel_badminton_sat/declarations", headers=H()).json()["declarations"]
    assert stored[0]["notify_phone"] == "+919876543210"


def test_user_profile_stores_the_whatsapp_number_once(mock_client):
    """The portal puts the number in settings rather than on every declaration, so a user sets it
    once and it is read back for each later bid."""
    assert mock_client.get("/venue/users/me@example.com/profile", headers=H()).json() == {
        "user_contact": "me@example.com"
    }

    saved = mock_client.put(
        "/venue/users/me@example.com/profile", json={"notify_phone": "00 91 (98765) 43210"}, headers=H()
    )
    assert saved.status_code == 200 and saved.json()["notify_phone"] == "+919876543210"
    assert saved.json()["user_contact"] == "me@example.com"

    assert mock_client.get("/venue/users/me@example.com/profile", headers=H()).json()["notify_phone"] == "+919876543210"
    # Another user's profile is untouched.
    assert "notify_phone" not in mock_client.get("/venue/users/other@example.com/profile", headers=H()).json()


@pytest.mark.parametrize("bad", [None, "", "9876543210", "nope", "+91-abc"])
def test_user_profile_rejects_a_number_that_cannot_be_messaged(mock_client, bad):
    r = mock_client.put("/venue/users/me@example.com/profile", json={"notify_phone": bad}, headers=H())
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_REQUEST"
    assert "notify_phone" not in mock_client.get("/venue/users/me@example.com/profile", headers=H()).json()


def test_user_profile_push_subscription_merges_without_clobbering_phone(mock_client):
    """PWA push notifications (web/settings) and the WhatsApp number (ADR-015) are independent
    fields on the same per-user profile document; saving one must not erase the other."""
    mock_client.put("/venue/users/me@example.com/profile", json={"notify_phone": "+919876543210"}, headers=H())

    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k1", "auth": "k2"}}
    saved = mock_client.put("/venue/users/me@example.com/profile", json={"push_subscription": sub}, headers=H())
    assert saved.status_code == 200
    assert saved.json()["push_subscription"] == sub
    assert saved.json()["notify_phone"] == "+919876543210"  # untouched by the push-only save

    updated_phone = mock_client.put(
        "/venue/users/me@example.com/profile", json={"notify_phone": "+911111111111"}, headers=H()
    )
    assert updated_phone.status_code == 200
    assert updated_phone.json()["notify_phone"] == "+911111111111"
    assert updated_phone.json()["push_subscription"] == sub  # untouched by the phone-only save

    cleared = mock_client.put("/venue/users/me@example.com/profile", json={"push_subscription": None}, headers=H())
    assert cleared.status_code == 200
    assert "push_subscription" not in cleared.json()


def test_user_profile_rejects_an_empty_body(mock_client):
    r = mock_client.put("/venue/users/me@example.com/profile", json={}, headers=H())
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_REQUEST"


def test_gnani_route_is_gone(mock_client):
    assert mock_client.post("/gnani/extract", json={"transcript": "x"}, headers=H()).status_code == 404


# ---------------------------------------------------------------------- organisers / events / releases
# The portal-facing surface added by ADR-015 (docs/web-portal/plan.md). Same serve() wrapper as every other
# route, so scenarios/idempotency/logging apply with no new pattern.


def organiser_body(**over):
    return {"name": "Court Co", "contact": "+91-9000000001", "requested_by": "org@example.com"} | over


def event_body(organiser_id="org_seed", **over):
    return {"name": "New League", "organiser_id": organiser_id, "status": "published"} | over


def instant_release_body(event_id="ev_badminton", **over):
    return {
        "event_id": event_id,
        "date": "2026-11-01",
        "opens_at": "2026-10-25T06:00:00Z",
        "allocation_mode": "instant_buy",
        "slots": [
            {
                "slot_id": "ib_a",
                "label": "Court A, 10:00",
                "starts_at": "2026-11-01T10:00:00Z",
                "capacity": 4,
                "price_per_person_paise": 20000,
            }
        ],
    } | over


def new_mandate(mock_client, value):
    return mock_client.post(
        "/pinelabs/mandates", json={"amount": {"value": value, "currency": "INR"}}, headers=H(key="m")
    ).json()["authorizationId"]


def test_organiser_request_lists_pending_then_approval_clears_it(mock_client):
    created = mock_client.post("/venue/organisers", json=organiser_body(), headers=H(key="o1"))
    assert created.status_code == 200
    org = created.json()
    assert org["organiser_id"] == "org_0001" and org["status"] == "pending" and org["requested_by"] == "org@example.com"

    pending = mock_client.get("/venue/organisers", params={"status": "pending"}, headers=H()).json()["organisers"]
    assert [o["organiser_id"] for o in pending] == ["org_0001"]

    approved = mock_client.post("/venue/organisers/org_0001/approve", headers=H(key="a1"))
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert mock_client.get("/venue/organisers", params={"status": "pending"}, headers=H()).json()["organisers"] == []
    assert mock_client.post("/venue/organisers/org_nope/approve", headers=H()).status_code == 404


@pytest.mark.parametrize("over", [{"name": ""}, {"contact": None}, {"requested_by": "  "}])
def test_organiser_request_rejects_missing_fields(mock_client, over):
    r = mock_client.post("/venue/organisers", json=organiser_body(**over), headers=H())
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_REQUEST"


def test_event_creation_requires_an_approved_organiser(mock_client):
    pending = mock_client.post("/venue/organisers", json=organiser_body(), headers=H()).json()
    blocked = mock_client.post("/venue/events", json=event_body(pending["organiser_id"]), headers=H())
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "ORGANISER_NOT_APPROVED"

    mock_client.post(f"/venue/organisers/{pending['organiser_id']}/approve", headers=H())
    created = mock_client.post("/venue/events", json=event_body(pending["organiser_id"]), headers=H(key="e1"))
    assert created.status_code == 200
    event = created.json()
    assert event["event_id"] == "ev_0001" and event["organiser_id"] == pending["organiser_id"]
    assert event["status"] == "published" and event["fulfilment"] == "digital"


def test_event_creation_rejects_unknown_organiser_and_bad_body(mock_client):
    assert mock_client.post("/venue/events", json=event_body("org_nope"), headers=H()).status_code == 404
    missing_name = mock_client.post("/venue/events", json={"organiser_id": "org_seed"}, headers=H())
    assert missing_name.status_code == 400 and missing_name.json()["error"]["code"] == "BAD_REQUEST"
    bad_status = mock_client.post("/venue/events", json=event_body(status="live"), headers=H())
    assert bad_status.status_code == 400


def test_event_patch_updates_only_allowed_fields(mock_client):
    ok = mock_client.patch("/venue/events/ev_badminton", json={"status": "draft", "name": "Renamed"}, headers=H())
    assert ok.status_code == 200 and ok.json()["status"] == "draft" and ok.json()["name"] == "Renamed"
    assert (
        mock_client.get("/venue/catalogue", params={"status": "draft"}, headers=H()).json()["events"][0]["event_id"]
        == "ev_badminton"
    )

    assert mock_client.patch("/venue/events/ev_nope", json={"name": "x"}, headers=H()).status_code == 404
    bad_status = mock_client.patch("/venue/events/ev_badminton", json={"status": "live"}, headers=H())
    assert bad_status.status_code == 400
    immutable = mock_client.patch("/venue/events/ev_badminton", json={"event_id": "ev_x"}, headers=H())
    assert immutable.status_code == 400 and "event_id" in immutable.json()["error"]["message"]


def test_release_creation_defaults_to_fair_draw_and_generates_slot_ids(mock_client):
    body = instant_release_body()
    del body["allocation_mode"]
    del body["slots"][0]["slot_id"]
    created = mock_client.post("/venue/releases", json=body, headers=H(key="r1"))
    assert created.status_code == 200
    release = created.json()
    assert release["release_id"] == "rel_0001" and release["allocation_mode"] == "fair_draw"
    assert release["slots"][0]["slot_id"] == "slot_0001"
    assert mock_client.get("/venue/releases/rel_0001", headers=H()).json()["allocation_mode"] == "fair_draw"


def test_a_release_takes_declarations_only_until_its_window_opens(mock_client):
    """The draw runs when the window opens, so a release past its opens_at can no longer be declared on. The agent
    reads that as a field rather than doing date arithmetic; it must be right for past, future and instant_buy."""
    future = instant_release_body(
        event_id="ev_tennis", date="2099-01-02", opens_at="2099-01-01T06:00:00Z", allocation_mode="fair_draw"
    )
    open_id = mock_client.post("/venue/releases", json=future, headers=H(key="r1")).json()["release_id"]
    # A dedicated past-dated release rather than the catalogue fixture: with #12 item 3, the fixture's
    # own `opens_at` is seeded relative to "now" and so is always open right after a reset.
    closed = instant_release_body(
        event_id="ev_tennis", date="2000-01-02", opens_at="2000-01-01T06:00:00Z", allocation_mode="fair_draw"
    )
    closed_id = mock_client.post("/venue/releases", json=closed, headers=H(key="r3")).json()["release_id"]
    instant_id = mock_client.post("/venue/releases", json=instant_release_body(), headers=H(key="r2")).json()[
        "release_id"
    ]

    detail = mock_client.get(f"/venue/releases/{open_id}", headers=H()).json()
    assert detail["declarations_open"] is True and detail["date"] == "2099-01-02"
    past = mock_client.get(f"/venue/releases/{closed_id}", headers=H()).json()
    assert past["declarations_open"] is False and past["date"] == "2000-01-02"
    assert mock_client.get(f"/venue/releases/{instant_id}", headers=H()).json()["declarations_open"] is False

    listed = {
        r["release_id"]: r["declarations_open"]
        for r in mock_client.get("/venue/releases", headers=H()).json()["releases"]
    }
    assert listed[open_id] is True and listed[closed_id] is False and listed[instant_id] is False


@pytest.mark.parametrize(
    "over,status,code",
    [
        ({"event_id": "ev_nope"}, 404, "NOT_FOUND"),
        ({"allocation_mode": "auction"}, 400, "BAD_REQUEST"),
        ({"slots": []}, 400, "BAD_REQUEST"),
        (
            {
                "slots": [
                    {"label": "x", "starts_at": "2026-11-01T10:00:00Z", "capacity": 0, "price_per_person_paise": 1}
                ]
            },
            400,
            "BAD_REQUEST",
        ),
    ],
)
def test_release_creation_rejects_bad_body(mock_client, over, status, code):
    r = mock_client.post("/venue/releases", json=instant_release_body(**over), headers=H())
    assert r.status_code == status and r.json()["error"]["code"] == code


def test_instant_buy_holds_captures_and_confirms_in_one_call(mock_client):
    release = mock_client.post("/venue/releases", json=instant_release_body(), headers=H(key="r1")).json()
    auth = new_mandate(mock_client, 100000)
    bought = mock_client.post(
        f"/venue/releases/{release['release_id']}/buy",
        json={"slot_id": "ib_a", "quantity": 2, "mandate_id": auth},
        headers=H(key="b1"),
    )
    assert bought.status_code == 200
    body = bought.json()
    assert body["status"] == "CONFIRMED" and body["booking_ref"] == "BK-0001" and body["amount_paise"] == 40000
    # The hold is active, two of four seats are gone, and the mandate kept the rest.
    assert mock_client.get(f"/venue/holds/{body['hold_id']}", headers=H()).json()["status"] == "active"
    slots = mock_client.get(f"/venue/releases/{release['release_id']}", headers=H()).json()["slots"]
    assert slots[0]["capacity"] == 2
    assert mock_client.get(f"/pinelabs/mandates/{auth}/balance", headers=H()).json()["balance"]["value"] == 60000
    state = mock_client.get("/__admin/state", params={"run_id": "r"}).json()
    assert state["bookings"] == 1 and state["captured_paise"] == 40000


def test_instant_buy_replays_an_idempotency_key(mock_client):
    release = mock_client.post("/venue/releases", json=instant_release_body(), headers=H(key="r1")).json()
    auth = new_mandate(mock_client, 100000)
    payload = {"slot_id": "ib_a", "quantity": 1, "mandate_id": auth}
    first = mock_client.post(f"/venue/releases/{release['release_id']}/buy", json=payload, headers=H(key="same"))
    second = mock_client.post(f"/venue/releases/{release['release_id']}/buy", json=payload, headers=H(key="same"))
    assert first.json() == second.json()
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).json()["bookings"] == 1


def test_buy_refuses_a_fair_draw_release_server_side(mock_client):
    """The fairness chain cannot be bypassed by calling the wrong endpoint: /buy itself returns 409."""
    r = mock_client.post(
        "/venue/releases/rel_badminton_sat/buy",
        json={"slot_id": "bd_0700", "quantity": 1, "mandate_id": new_mandate(mock_client, 100000)},
        headers=H(),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "FAIR_DRAW_REQUIRED"
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).json()["bookings"] == 0


def test_buy_validates_capacity_and_payment(mock_client):
    release = mock_client.post(
        "/venue/releases",
        json=instant_release_body(
            slots=[
                {
                    "slot_id": "ib_a",
                    "label": "Court A",
                    "starts_at": "2026-11-01T10:00:00Z",
                    "capacity": 1,
                    "price_per_person_paise": 20000,
                }
            ]
        ),
        headers=H(key="r1"),
    ).json()
    path = f"/venue/releases/{release['release_id']}/buy"
    small = new_mandate(mock_client, 10000)

    unknown_release = mock_client.post(
        "/venue/releases/rel_nope/buy", json={"slot_id": "ib_a", "quantity": 1, "mandate_id": small}, headers=H()
    )
    assert unknown_release.status_code == 404
    bad_slot = mock_client.post(path, json={"slot_id": "ghost", "quantity": 1, "mandate_id": small}, headers=H())
    assert bad_slot.status_code == 400
    no_mandate = mock_client.post(path, json={"slot_id": "ib_a", "quantity": 1}, headers=H())
    assert no_mandate.status_code == 404
    too_many = mock_client.post(path, json={"slot_id": "ib_a", "quantity": 2, "mandate_id": small}, headers=H())
    assert too_many.status_code == 409 and too_many.json()["error"]["code"] == "INSUFFICIENT_CAPACITY"
    underfunded = mock_client.post(path, json={"slot_id": "ib_a", "quantity": 1, "mandate_id": small}, headers=H())
    assert underfunded.status_code == 402 and underfunded.json()["error"]["code"] == "INSUFFICIENT_BALANCE"


@pytest.mark.parametrize(
    "s,status,code",
    [
        ("no_inventory", 409, "SOLD_OUT"),
        ("payment_failure", 402, "PAYMENT_FAILED"),
    ],
)
def test_buy_failure_scenarios_release_the_hold(mock_client, s, status, code):
    release = mock_client.post("/venue/releases", json=instant_release_body(), headers=H(key="r1")).json()
    auth = new_mandate(mock_client, 100000)
    scenario(mock_client, target="venue.buy", s=s)
    r = mock_client.post(
        f"/venue/releases/{release['release_id']}/buy",
        json={"slot_id": "ib_a", "quantity": 2, "mandate_id": auth},
        headers=H(),
    )
    assert r.status_code == status and r.json()["error"]["code"] == code
    # A refused buy must leave no held capacity behind, and must not have charged anyone.
    state = mock_client.get("/__admin/state", params={"run_id": "r"}).json()
    assert state["active_holds"] == 0 and state["bookings"] == 0 and state["captured_paise"] == 0
    slots = mock_client.get(f"/venue/releases/{release['release_id']}", headers=H()).json()["slots"]
    assert slots[0]["capacity"] == 4


def test_admin_state_has_a_per_user_view(mock_client):
    """The dashboard reads its own data from /__admin/state?user_contact= (no per-user business route)."""
    mock_client.post(
        "/venue/releases/rel_badminton_sat/declarations",
        json=declare_body(user_contact="a@b.com"),
        headers=H(key="d1"),
    )
    release = mock_client.post("/venue/releases", json=instant_release_body(), headers=H(key="r1")).json()
    auth = new_mandate(mock_client, 100000)
    mock_client.post(
        f"/venue/releases/{release['release_id']}/buy",
        json={"slot_id": "ib_a", "quantity": 1, "mandate_id": auth, "user_contact": "a@b.com"},
        headers=H(key="b1"),
    )

    view = mock_client.get("/__admin/state", params={"run_id": "r", "user_contact": "a@b.com"}).json()["user"]
    assert [d["release_id"] for d in view["declarations"]] == ["rel_badminton_sat"]
    assert view["bookings"][0]["booking_ref"] == "BK-0001"
    assert view["payments"][0]["amount"] == 20000
    assert mock_client.get("/__admin/state", params={"run_id": "r", "user_contact": "nobody@x.com"}).json()["user"] == {
        "user_contact": "nobody@x.com",
        "declarations": [],
        "bookings": [],
        "payments": [],
    }
    assert "user" not in mock_client.get("/__admin/state", params={"run_id": "r"}).json()


def test_catalogue_filters_by_organiser_and_status(mock_client):
    seeded = mock_client.get("/venue/catalogue", params={"organiser_id": "org_seed"}, headers=H()).json()["events"]
    assert {e["event_id"] for e in seeded} == {"ev_badminton", "ev_tennis", "ev_movie", "ev_f1"}
    assert all(e["status"] == "published" for e in seeded)
    assert mock_client.get("/venue/catalogue", params={"status": "draft"}, headers=H()).json()["events"] == []
