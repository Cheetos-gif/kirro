from logging_.decision_log import DecisionLog, read_log
from logging_.reconstruct import to_markdown
from logging_.redact import redact
from tests.conftest import declare

REQUIRED = {"ts", "run_id", "state_before", "state_after", "input", "input_source", "connector", "decision", "rule",
            "action", "recipient", "tool_call", "tool_response", "result", "user_message"}


def test_record_has_all_q12_fields_and_is_jsonl(tmp_path):
    log = DecisionLog("r1", tmp_path)
    log.record(decision="x", state_before="A", state_after="B")
    log.record(decision="y")
    rows = read_log(log.path)
    assert len(rows) == 2 and REQUIRED <= set(rows[0]) and rows[1]["seq"] == 2


def test_secrets_and_phones_never_written(tmp_path):
    log = DecisionLog("r2", tmp_path)
    log.record(decision="call", tool_call={"headers": {"x-api-key": "sk-123", "Authorization": "Bearer abcdefghijklmnop"},
                                           "mobileNumber": "9876543210", "note": "call +91 98765 43210"})
    text = log.path.read_text()
    assert "sk-123" not in text and "abcdefghijklmnop" not in text and "9876543210" not in text and "98765 43210" not in text
    assert "******3210" in text


def test_redact_keeps_dates_and_amounts():
    assert redact({"d": "2026-10-03T07:00:00Z", "amt": 1200000}) == {"d": "2026-10-03T07:00:00Z", "amt": 1200000}


def test_engine_run_reconstructs_to_q12_table(make_engine):
    eng, log = make_engine()
    d = declare(eng)
    eng.confirm_readback(d, True)
    eng.request_authorisation(d)
    eng.on_event(d, {"type": "window_open", "event_id": "w"})
    md = to_markdown(log.records)
    assert "| timestamp |" in md and "call:create_hold" in md and "transition:CONFIRMED" in md
    assert all(REQUIRED <= set(r) for r in log.records)
    srcs = {r["input_source"] for r in log.records}
    assert {"user_voice", "connector", "human_event"} <= srcs
