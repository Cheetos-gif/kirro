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
        for r in (mock_client.get("/venue/releases/rel_badminton_sat", headers=H()),
                  mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key=s)),
                  mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100, "currency": "INR"}}, headers=H())):
            assert "scenario" not in r.text.lower() and "mock" not in r.text.lower()
            assert "scenario" not in {k.lower() for k in r.headers}


def test_happy_hold_booking_flow_and_idempotency(mock_client):
    a = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k1")).json()
    b = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k1")).json()
    assert a == b and a["hold_id"] == "hold_0001"
    assert mock_client.get("/__admin/state", params={"run_id": "r"}).json()["holds"] == 1
    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000, "currency": "INR"}}, headers=H(key="m")).json()
    p = mock_client.post(f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 50000}}, headers=H(key="p")).json()
    assert p["status"] == "SUCCESS"
    bk = mock_client.post("/venue/bookings", json={"hold_id": a["hold_id"], "payment_id": p["payment_id"]}, headers=H(key="b"))
    assert bk.json()["booking_ref"] == "BK-0001"


def test_booking_requires_captured_payment(mock_client):
    a = mock_client.post("/venue/releases/rel_badminton_sat/holds", json=hold_body(), headers=H(key="k")).json()
    r = mock_client.post("/venue/bookings", json={"hold_id": a["hold_id"], "payment_id": "pay_9999"}, headers=H(key="b"))
    assert r.status_code == 402 and r.json()["error"]["code"] == "PAYMENT_REQUIRED"


@pytest.mark.parametrize("s,target,method,path,body,status,code", [
    ("no_inventory", "venue.hold", "post", "/venue/releases/rel_badminton_sat/holds", hold_body(), 409, "SOLD_OUT"),
    ("partial_group", "venue.hold", "post", "/venue/releases/rel_badminton_sat/holds", hold_body(4), 409, "INSUFFICIENT_CAPACITY"),
    ("upstream_500", "venue.release", "get", "/venue/releases/rel_badminton_sat", None, 500, "INTERNAL"),
    ("insufficient_balance", "pinelabs.create_mandate", "post", "/pinelabs/mandates", {"amount": {"value": 5}}, 402, "INSUFFICIENT_BALANCE"),
])
def test_failure_scenarios(mock_client, s, target, method, path, body, status, code):
    scenario(mock_client, target=target, s=s)
    r = getattr(mock_client, method)(path, headers=H(), **({"json": body} if body else {}))
    assert r.status_code == status and r.json()["error"]["code"] == code


def test_payment_failure_body(mock_client):
    m = mock_client.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H()).json()
    scenario(mock_client, target="pinelabs.execute", s="payment_failure")
    r = mock_client.post(f"/pinelabs/mandates/{m['authorizationId']}/execute", json={"amount": {"value": 1000}}, headers=H(key="x")).json()
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
    assert second.json()["error"]["code"] == "DUPLICATE_REQUEST" and second.json()["original"]["hold_id"] == first.json()["hold_id"]


def test_scenario_sequence_then_sticks(mock_client):
    mock_client.post("/__admin/scenario", json={"run_id": "r", "target": "venue.release", "sequence": ["upstream_500", "success"]})
    codes = [mock_client.get("/venue/releases/rel_badminton_sat", headers=H()).status_code for _ in range(3)]
    assert codes == [500, 200, 200]


def test_runs_are_isolated(mock_client):
    scenario(mock_client, run="a", s="upstream_500")
    assert mock_client.get("/venue/releases/rel_badminton_sat", headers=H("a")).status_code == 500
    assert mock_client.get("/venue/releases/rel_badminton_sat", headers=H("b")).status_code == 200


def test_delhivery_shapes(mock_client):
    ok = mock_client.get("/delhivery/c/api/pin-codes/json/", params={"filter_codes": "560001"}, headers=H()).json()
    assert ok["delivery_codes"][0]["postal_code"]["pin"] == 560001
    assert mock_client.get("/delhivery/c/api/pin-codes/json/", params={"filter_codes": "999999"}, headers=H()).json() == {"delivery_codes": []}
    data = {"format": "json", "data": json.dumps({"shipments": [{"order": "BK-1", "pin": "560001"}]})}
    c1 = mock_client.post("/delhivery/api/cmu/create.json", data=data, headers=H(key="1")).json()
    assert c1["success"] and c1["packages"][0]["waybill"].startswith("MOCKWB")
    c2 = mock_client.post("/delhivery/api/cmu/create.json", data=data, headers=H(key="2")).json()
    assert not c2["success"] and "Duplicate" in c2["rmk"]
    t = mock_client.get("/delhivery/api/v1/packages/json/", params={"waybill": c1["packages"][0]["waybill"]}, headers=H()).json()
    assert t["ShipmentData"][0]["Shipment"]["Status"]["Status"] == "Manifested"


def test_request_response_scenario_logged(tmp_path):
    from fastapi.testclient import TestClient
    c = TestClient(create_app(str(tmp_path)))
    c.post("/__admin/scenario", json={"run_id": "lg", "target": "venue.release", "scenario": "upstream_500"})
    c.get("/venue/releases/rel_badminton_sat", headers=H("lg"))
    rec = json.loads((tmp_path / "lg.jsonl").read_text().splitlines()[0])
    assert {"ts", "request_id", "path", "scenario", "request", "response", "status", "latency_ms"} <= set(rec)
    assert rec["scenario"] == "upstream_500" and rec["request_id"] == "req-1" and rec["status"] == 500


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
    from connectors.inventory.venue import VenueInventoryConnector
    c = httpx.Client(base_url=live_url)
    conn = VenueInventoryConnector(c, "rt")
    c.post("/__admin/scenario", json={"run_id": "rt", "target": "venue.release", "scenario": "timeout", "delay_s": 0.6})
    res = conn.call("get_release", {"release_id": "rel_badminton_sat"}, idempotency_key="k", timeout_s=0.2)
    assert res.status == "timeout" and res.error.code == "TIMEOUT"
    c.post("/__admin/scenario", json={"run_id": "rt", "target": "venue.release", "scenario": "delayed", "delay_s": 0.3})
    res = conn.call("get_release", {"release_id": "rel_badminton_sat"}, idempotency_key="k2", timeout_s=2)
    assert res.status == "success" and res.latency_ms >= 250
