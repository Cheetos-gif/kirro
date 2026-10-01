"""Durable state tests (ADR-013).

The failure these exist to prevent: the Declare Agent writes a pool entry in one conversation, the Window
Allocation Workflow reads the pool later — and a pod restart in between silently empties it. Every test here opens
a *second* `create_app` over the same data directory, which is exactly what a container restart does.
"""

from fastapi.testclient import TestClient

from mock_server.app import create_app

H = {"X-Run-Id": "r"}

DECLARE = {
    "declaration_id": "dec_1",
    "user_contact": "+91-9000000000",
    "mandate_id": "auth_0001",
    "acceptable_slot_ids": ["tn_0900"],
    "group_size": 4,
    "min_group_size": 4,
    "max_price_paise": 60000,
}

HOLD = {"slot_id": "bd_0700", "quantity": 2, "ttl_s": 600}


def client(log_dir):
    """A fresh app + fresh store over the same data directory (i.e. a restarted process)."""
    return TestClient(create_app(str(log_dir)), base_url="http://mock")


def test_declare_pool_survives_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    assert first.post("/venue/releases/rel_tennis_sat/declarations", json=DECLARE, headers=H).status_code == 200

    restarted = client(log_dir)
    listed = restarted.get("/venue/releases/rel_tennis_sat/declarations", headers=H).json()
    assert [d["declaration_id"] for d in listed["declarations"]] == ["dec_1"]
    assert listed["declarations"][0]["status"] == "DECLARED"

    # the pool is what the draw reads, so the allocation must still be computable after the restart
    drawn = restarted.post(
        "/allocator/draw",
        headers=H,
        json={
            "release_id": "rel_tennis_sat",
            "bids": [
                {
                    "declaration_id": "dec_1",
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


def test_holds_and_capacity_survive_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    assert first.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=H).json()["hold_id"] == "hold_0001"

    restarted = client(log_dir)
    assert restarted.get("/venue/holds/hold_0001", headers=H).json()["status"] == "active"
    # capacity consumed by the surviving hold is still consumed (slot capacity is 8, 2 are held)
    r = restarted.post("/venue/releases/rel_badminton_sat/holds", json={**HOLD, "quantity": 8}, headers=H)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INSUFFICIENT_CAPACITY"

    # releasing after the restart returns the capacity
    assert restarted.delete("/venue/holds/hold_0001", headers=H).status_code == 200
    assert (
        restarted.post("/venue/releases/rel_badminton_sat/holds", json={**HOLD, "quantity": 8}, headers=H).status_code
        == 200
    )


def test_idempotency_ledger_survives_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    head = {**H, "Idempotency-Key": "k1"}
    original = first.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=head).json()
    assert original["hold_id"] == "hold_0001"

    restarted = client(log_dir)
    replay = restarted.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=head)
    assert replay.json()["hold_id"] == "hold_0001"
    # a redelivered request after a restart must not create a second hold
    assert restarted.get("/__admin/state", params={"run_id": "r"}).json()["holds"] == 1


def test_ids_do_not_repeat_after_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    first.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=H)
    first.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=H)

    restarted = client(log_dir)
    third = restarted.post("/venue/releases/rel_badminton_sat/holds", json=HOLD, headers=H).json()
    assert third["hold_id"] == "hold_0003"


def test_mandate_and_capture_survive_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    auth = first.post("/pinelabs/mandates", json={"amount": {"value": 100000}}, headers=H).json()["authorizationId"]

    restarted = client(log_dir)
    assert restarted.get(f"/pinelabs/mandates/{auth}/balance", headers=H).json()["balance"]["value"] == 100000
    assert (
        restarted.post(f"/pinelabs/mandates/{auth}/execute", json={"amount": {"value": 50000}}, headers=H).json()[
            "status"
        ]
        == "SUCCESS"
    )

    again = client(log_dir)
    assert again.get(f"/pinelabs/mandates/{auth}/balance", headers=H).json()["balance"]["value"] == 50000
    assert again.get(f"/pinelabs/mandates/{auth}/balance", headers=H).json()["status"] == "ACTIVE"


def test_runs_stay_isolated_across_reopen(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    first.post("/venue/releases/rel_tennis_sat/declarations", json=DECLARE, headers={"X-Run-Id": "a"})

    restarted = client(log_dir)
    assert (
        restarted.get("/venue/releases/rel_tennis_sat/declarations", headers={"X-Run-Id": "b"}).json()["declarations"]
        == []
    )
    assert (
        len(
            restarted.get("/venue/releases/rel_tennis_sat/declarations", headers={"X-Run-Id": "a"}).json()[
                "declarations"
            ]
        )
        == 1
    )


def test_reset_clears_durable_state(tmp_path):
    log_dir = tmp_path / "mocklogs"
    first = client(log_dir)
    first.post("/venue/releases/rel_tennis_sat/declarations", json=DECLARE, headers=H)
    assert first.post("/__admin/reset", json={"run_id": "r"}).json() == {"ok": True}

    restarted = client(log_dir)
    assert restarted.get("/venue/releases/rel_tennis_sat/declarations", headers=H).json()["declarations"] == []


def test_unwritable_log_dir_does_not_fail_the_call(tmp_path, monkeypatch):
    """A logging failure must never turn a business call into a 500 — request logging is diagnostics."""
    blocker = tmp_path / "logs_is_a_file"
    blocker.write_text("not a directory")
    monkeypatch.setenv("MOCK_DB_PATH", str(tmp_path / "state.db"))
    c = TestClient(create_app(str(blocker)), base_url="http://mock")
    r = c.get("/venue/releases/rel_badminton_sat", headers=H)
    assert r.status_code == 200 and len(r.json()["slots"]) == 3
