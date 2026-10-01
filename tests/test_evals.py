import json
import re

import pytest

from agent.runner.prompt import build_system_prompt, current_version, load_layer1
from agent.schemas.models import Declaration
from evals.harness import CASES, all_case_ids, load_case, run_case

REQUIRED = {
    "id",
    "name",
    "objective",
    "setup",
    "human_input",
    "external_state",
    "expected_behaviour",
    "forbidden_behaviour",
    "pass_criteria",
}


def test_exactly_ten_canonical_cases():
    ids = all_case_ids()
    assert ids == [f"E{i:02d}" for i in range(1, 11)]


@pytest.mark.parametrize("cid", [f"E{i:02d}" for i in range(1, 11)])
def test_case_schema(cid):
    c = load_case(cid)
    assert REQUIRED <= set(c) and c["id"] == cid
    assert c["human_input"] and c["pass_criteria"] and c["expected_behaviour"] and c["forbidden_behaviour"]
    for crit in c["pass_criteria"]:
        assert crit["type"] in open(CASES.parent / "checks.py").read()


@pytest.mark.parametrize("cid", [f"E{i:02d}" for i in range(1, 11)])
def test_offline_run_passes_and_writes_artifacts(cid, tmp_path):
    v = run_case(load_case(cid), "offline", runs_dir=tmp_path)
    failed = [c for c in v["checks"] if not c["passed"]]
    assert v["passed"], failed
    d = tmp_path / v["run_id"]
    assert (d / "log.jsonl").exists() and (d / "transcript.md").exists()
    assert json.loads((d / "verdict.json").read_text())["case"] == cid


def test_live_mode_refuses_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        run_case(load_case("E01"), "live", runs_dir=tmp_path)


def test_a_broken_policy_would_fail_the_suite(tmp_path):
    """The checks must bite: a policy that claims success before CONFIRMED has to fail the built-ins."""
    from evals.checks import RunResult, builtin_checks

    r = RunResult(
        {"state": "INTAKE"}, [], [{"step": 1, "role": "assistant", "text": "All booked!", "state": "INTAKE"}], []
    )
    assert not all(ok for _, ok, _ in builtin_checks(r))


def test_prompt_versioning():
    v = current_version()
    assert re.fullmatch(r"v\d+", v)
    ver, text = load_layer1(v)
    assert "external_data" in text and "one question" in text.lower()
    _, full = build_system_prompt(Declaration(declaration_id="d"))
    assert "Current declaration state" in full
    changelog = (load_layer1.__globals__["DIR"] / "CHANGELOG.md").read_text()
    for f in load_layer1.__globals__["DIR"].glob("v*.md"):
        assert f.stem in changelog, f"{f.name} lacks a CHANGELOG row"
