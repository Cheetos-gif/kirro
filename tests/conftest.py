from datetime import date

import pytest
from fastapi.testclient import TestClient

from agent.core import Engine
from agent.state.store import Store
from connectors.registry import build_connectors
from logging_.decision_log import DecisionLog
from mock_server.app import create_app

TODAY = date(2026, 10, 1)  # a Thursday


@pytest.fixture
def mock_client(tmp_path):
    return TestClient(create_app(str(tmp_path / "mocklogs")), base_url="http://mock")


@pytest.fixture
def make_engine(tmp_path, mock_client):
    def _make(run_id="t1", scenarios=()):
        for sc in scenarios:
            mock_client.post("/__admin/scenario", json={"run_id": run_id, **sc}).raise_for_status()
        cat = mock_client.get("/venue/catalogue").json()["events"]
        log = DecisionLog(run_id, tmp_path / "logs")
        eng = Engine(build_connectors(mock_client, run_id, env={}), Store(), log, cat, today=TODAY)
        return eng, log

    return _make


def declare(eng, text="Badminton court Saturday 7-9 am, 4 people, max 300 each"):
    """Drive a declaration to VALIDATED through the public engine API (no stub policy)."""
    d = eng.new_declaration()
    eng.receive_user_turn(d, text)
    for name, ev in (
        ("time_window", "7-9 am"),
        ("event", "Badminton court"),
        ("date", "Saturday"),
        ("group_size", "4 people"),
        ("max_price", "max 300 each"),
    ):
        eng.set_field(d, name, ev)
    eng.present_readback(d)
    return d
