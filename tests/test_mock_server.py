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
    assert mock_client.get("/venue/releases", params={"event_id": "ev_movie"}).json()["releases"] == [
        {
            "release_id": "rel_movie_fri",
            "event_id": "ev_movie",
            "date": "2026-10-03",
            "opens_at": "2026-10-02T06:00:00Z",
            "allocation_mode": "fair_draw",
        }
    ]
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


def declare_body(**over):
    return {
        "declaration_id": "dec_1",
        "user_contact": "+91-9000000000",
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


@pytest.mark.parametrize(
    "over",
    [
        {"group_size": "four"},
        {"max_price_paise": None},
        {"acceptable_slot_ids": []},
        {"acceptable_slot_ids": "bd_0700"},
        {"min_group_size": 5},
    ],
)
def test_declare_pool_rejects_bad_bid(mock_client, over):
    r = mock_client.post("/venue/releases/rel_badminton_sat/declarations", json=declare_body(**over), headers=H())
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
