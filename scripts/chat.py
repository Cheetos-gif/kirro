"""Interactive text chat with the agent (stub policy by default, --live for the Anthropic policy).
Type /open to fire the window_open event, /end for window_end, /quit to stop.
Run: uv run python scripts/chat.py [--live] [--scenario venue.hold=payment_failure]"""
import argparse
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from agent.core import Engine  # noqa: E402
from agent.runner.session import HumanTurn, Session  # noqa: E402
from agent.state.store import Store  # noqa: E402
from connectors.registry import build_connectors  # noqa: E402
from logging_.decision_log import DecisionLog  # noqa: E402
from mock_server.app import create_app  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--scenario", action="append", default=[], help="target=scenario, e.g. pinelabs.execute=payment_failure")
    a = ap.parse_args()
    run_id = f"chat-{uuid.uuid4().hex[:6]}"
    client = TestClient(create_app("logs/mock"), base_url="http://mock")
    for s in a.scenario:
        t, sc = s.split("=")
        client.post("/__admin/scenario", json={"run_id": run_id, "target": t, "scenario": sc})
    cat = client.get("/venue/catalogue").json()["events"]
    eng = Engine(build_connectors(client, run_id, env={}), Store(), DecisionLog(run_id, "logs"), cat, today=date.today())
    if a.live:
        from agent.runner.anthropic_policy import AnthropicPolicy
        policy = AnthropicPolicy()
    else:
        from agent.runner.stub import StubPolicy
        policy = StubPolicy()
    sess = Session(eng, eng.new_declaration(), policy)
    print(f"run {run_id}; log at logs/{run_id}.jsonl")
    while True:
        try:
            line = input("you> ")
        except EOFError:
            break
        if line == "/quit":
            break
        turn = (HumanTurn(event={"type": "window_open"}) if line == "/open"
                else HumanTurn(event={"type": "window_end"}) if line == "/end" else HumanTurn(text=line))
        n = len(eng.messages)
        sess.step(turn)
        for m in eng.messages[n:]:
            print("kirro>", m["text"])
        print(f"[state {sess.decl.state.value}]")


if __name__ == "__main__":
    main()
