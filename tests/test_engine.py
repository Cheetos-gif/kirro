from agent.schemas.models import State
from agent.tools.toolset import ToolSet
from tests.conftest import declare


def test_invalid_price_constraint_rejected(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    eng.receive_user_turn(d, "budget 8 to 10k, ideally 8")
    r = eng.set_field(d, "max_price", "budget 8 to 10k, ideally 8")
    assert not r["ok"] and r["status"] == "ambiguous"
    assert d.max_price_paise is None and d.field_notes["max_price"] == "ambiguous"
    # the model cannot smuggle an amount: evidence must be the user's own words
    r = eng.set_field(d, "max_price", "8000 rupees")
    assert not r["ok"] and d.max_price_paise is None


def test_missing_field_blocks_claim_and_authorisation(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    eng.receive_user_turn(d, "Badminton Saturday")
    eng.set_field(d, "event", "Badminton")
    eng.set_field(d, "date", "Saturday")
    assert d.state == State.AWAITING_USER and d.open_field == "group_size"
    r = eng.request_authorisation(d)
    assert not r["ok"] and d.mandate_id is None and d.state == State.AWAITING_USER
    assert eng.confirm_readback(d, True)["ok"] is False
    assert eng.c.pine_labs.client.get("/__admin/state", params={"run_id": "t1"}).json()["mandates"] == 0


def test_success_words_blocked_before_confirmed(make_engine):
    eng, log = make_engine()
    d = eng.new_declaration()
    r = eng.report_to_user(d, "Great news, your tickets are booked!")
    assert not r["ok"] and eng.messages == []
    assert any(x["decision"] == "message_blocked" for x in log.records)


def test_two_questions_in_one_turn_refused(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    assert not eng.ask_user(d, "Which date? And how many people?")["ok"]


def test_user_cancellation_releases_in_order(make_engine):
    eng, log = make_engine()
    d = declare(eng)
    assert d.state == State.INTAKE and d.readback_presented
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    assert d.state == State.WAITING_FOR_WINDOW and d.mandate_paise == 120000
    eng.on_event(d, {"type": "user_cancel", "event_id": "c1"})
    assert d.state == State.CANCELLED and d.mandate_released
    assert "reserved amount" in eng.messages[-1]["text"]
    assert [x["decision"] for x in log.records if x["decision"].startswith("call:")][-1] == "call:release_mandate"


def test_cancel_before_anything_reserved(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    assert eng.cancel(d, "changed mind")["ok"] and d.state == State.CANCELLED
    assert "Nothing had been reserved" in eng.messages[-1]["text"]


def test_booking_needs_external_confirmation_end_to_end(make_engine):
    eng, _ = make_engine()
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w1"})
    assert d.state == State.CLOSED and d.booking_ref == "BK-0001"
    assert d.inventory_result.status == "success" and d.payment_result.status == "success"
    assert d.slot_price_paise * d.allocated_group_size <= d.max_price_paise * d.group_size


def test_duplicate_window_event_creates_no_second_action(make_engine):
    eng, _ = make_engine()
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w1"})
    n_msgs = len(eng.messages)
    r = eng.on_event(d, {"type": "window_open", "event_id": "w1"})
    assert r["ignored"] and len(eng.messages) == n_msgs
    st = eng.c.pine_labs.client.get("/__admin/state", params={"run_id": "t1"}).json()
    assert st["holds"] == 1 and st["bookings"] == 1 and st["payments"] == 1


def test_ledger_returns_stored_result_without_second_call(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    calls = []
    real = eng.c.pine_labs.call

    def counting(*a, **k):
        calls.append(a[0])
        return real(*a, **k)

    eng.c.pine_labs.call = counting
    p = {"customerReference": "u", "amount": {"value": 100, "currency": "INR"}, "paymentMethod": "RESERVE_PAY"}
    r1 = eng._call(d, eng.c.pine_labs, "create_mandate", p, "s", "test")
    r2 = eng._call(d, eng.c.pine_labs, "create_mandate", p, "s", "test")
    assert calls == ["create_mandate"] and r1 is r2


def test_malformed_response_does_not_advance_state_or_invent_ids(make_engine):
    eng, _ = make_engine(scenarios=[{"target": "pinelabs.create_mandate", "scenario": "malformed"}])
    d = declare(eng)
    eng.confirm_readback(d, True)
    r = eng.request_authorisation(d)
    assert not r["ok"] and d.mandate_id is None
    assert d.state == State.AWAITING_USER and d.open_field == "payment"
    assert "reserved up to" not in eng.messages[-1]["text"]


def test_payment_failure_unwinds_and_does_not_claim(make_engine):
    eng, _ = make_engine(scenarios=[{"target": "pinelabs.execute", "scenario": "payment_failure"}])
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w"})
    assert d.state == State.RELEASED and d.hold_released and d.mandate_released and d.booking_ref is None


def test_booking_expired_releases_before_charging(make_engine):
    eng, log = make_engine(scenarios=[{"target": "venue.hold", "scenario": "booking_expired"}])
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w"})
    assert d.state == State.RELEASED
    assert not any(x["decision"] == "call:execute_charge" for x in log.records)


def test_upstream_500_fails_safe(make_engine):
    eng, _ = make_engine(scenarios=[{"target": "venue.release", "scenario": "upstream_500"}])
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w"})
    assert d.state == State.FAILED and d.mandate_released


def test_toolset_refuses_illegal_action_for_state(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    ts = ToolSet(eng, d)
    r = ts.execute("request_authorisation", {})
    assert not r["ok"] and "not legal" in r["reason"]
    assert ts.execute("get_state", {})["state"] == "AWAITING_USER"


def test_evidence_must_come_from_the_users_turn(make_engine):
    eng, _ = make_engine()
    d = eng.new_declaration()
    eng.receive_user_turn(d, "hello")
    assert not eng.set_field(d, "group_size", "4 people")["ok"]


def test_set_field_change_needs_explicit_correction(make_engine):
    eng, _ = make_engine()
    d = declare(eng)
    eng.receive_user_turn(d, "Sunday")
    assert not eng.set_field(d, "date", "Sunday")["ok"] and d.date == "2026-10-03"
    eng.receive_user_turn(d, "actually Sunday")
    assert eng.set_field(d, "date", "actually Sunday")["ok"] and d.date == "2026-10-04"
    assert d.group_size == 4 and d.max_price_paise == 30000
