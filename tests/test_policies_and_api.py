import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from agent.api import create_core
from agent.runner.anthropic_policy import AnthropicPolicy
from agent.runner.session import HumanTurn, Session
from agent.tools.toolset import TOOL_DEFS


def test_core_api_flow(mock_client, tmp_path):
    core = TestClient(create_core(client=mock_client, log_dir=str(tmp_path)))
    assert core.get("/health").json()["status"] == "ok"
    did = core.post("/declarations").json()["declaration_id"]
    r = core.post(f"/declarations/{did}/fields", json={"user_text": "budget 8 to 10k", "field": "max_price", "evidence": "budget 8 to 10k"})
    assert r.json()["status"] == "ambiguous"
    assert core.post(f"/declarations/{did}/authorise").json()["ok"] is False
    assert core.get("/declarations/nope").status_code == 404
    ex = core.post("/intake/gnani", json={"transcript": "Shanivaar ko court chahiye, char log"}).json()
    assert ex["language"] == "hinglish"


def test_tool_defs_expose_no_money_fields():
    names = {t["name"] for t in TOOL_DEFS}
    assert names == {"set_field", "ask_user", "confirm_readback", "request_authorisation", "cancel_declaration", "report_to_user", "get_state"}
    schema_text = json.dumps([t["input_schema"] for t in TOOL_DEFS])
    assert "paise" not in schema_text and "amount" not in schema_text and "price" not in schema_text.replace("max_price", "")


class FakeClient:
    """Stands in for anthropic.Anthropic: scripted tool_use then nothing. Proves the live loop wiring offline."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        blocks = self.script.pop(0)
        return SimpleNamespace(content=blocks, stop_reason="tool_use" if blocks else "end_turn")


def tu(i, name, **inp):
    return SimpleNamespace(type="tool_use", id=f"t{i}", name=name, input=inp)


def test_anthropic_policy_loop_uses_same_tools_and_guards(make_engine, monkeypatch):
    eng, _ = make_engine()
    d = eng.new_declaration()
    fake = FakeClient([[tu(1, "set_field", field="max_price", evidence="8 to 10k, ideally 8")],
                       [tu(2, "ask_user", question="What is the single maximum you will pay per person?")]])
    pol = AnthropicPolicy(client=fake, model=None)
    assert pol.model == "claude-sonnet-5-5"
    s = Session(eng, d, pol)
    s.step(HumanTurn(text="8 to 10k, ideally 8"))
    assert d.max_price_paise is None
    assert eng.messages[-1]["text"].startswith("What is the single maximum")
    assert fake.calls[0]["tools"] == TOOL_DEFS and "KIRRO" in fake.calls[0]["system"]
    assert "temperature" not in fake.calls[0] and "tool_choice" not in fake.calls[0]


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("KIRRO_MODEL", "claude-test")
    assert AnthropicPolicy(client=FakeClient([])).model == "claude-test"
