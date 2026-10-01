"""Eval harness. `python -m evals.harness E01` (or `all`). Modes: offline (stub policy, no network) | live.

The mock scenario is set out of band via /__admin/scenario; the agent never sees it.
Outputs evals/runs/<ts>_p<version>_<id>_<slug>/{log.jsonl, transcript.md, verdict.json, mock/}.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import httpx
import yaml
from fastapi.testclient import TestClient

from agent.core import Engine
from agent.runner.prompt import current_version
from agent.runner.session import HumanTurn, Session
from agent.state.store import Store
from allocator.engine import Bid
from connectors.registry import build_connectors
from evals.checks import RunResult, builtin_checks, check
from logging_.decision_log import DecisionLog, read_log
from mock_server.app import create_app

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
RUNS = ROOT / "evals" / "runs"


def load_case(ident: str) -> dict:
    matches = sorted(CASES.glob(f"{ident}_*.yaml")) or sorted(CASES.glob(f"{ident}.yaml"))
    if not matches:
        raise SystemExit(f"no eval case {ident!r} in {CASES}")
    return yaml.safe_load(matches[0].read_text())


def all_case_ids() -> list[str]:
    return [p.name.split("_")[0] for p in sorted(CASES.glob("E*.yaml"))]


def _policy(mode: str, version: str):
    if mode == "offline":
        from agent.runner.stub import StubPolicy
        return StubPolicy()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("live mode needs ANTHROPIC_API_KEY (offline mode needs none)")
    from agent.runner.anthropic_policy import AnthropicPolicy
    return AnthropicPolicy(prompt_version=version)


def run_case(case: dict, mode: str = "offline", mock_url: str | None = None, runs_dir: Path = RUNS,
             prompt_version: str | None = None) -> dict:
    setup = case.get("setup", {})
    version = prompt_version or setup.get("prompt_version") or current_version()
    if version == "current":
        version = current_version()
    slug = re.sub(r"[^a-z0-9]+", "-", case["name"].lower()).strip("-")
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_p{version}_{case['id']}_{slug}"
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    client = (httpx.Client(base_url=mock_url) if mock_url
              else TestClient(create_app(str(run_dir / "mock")), base_url="http://mock"))
    ext = case.get("external_state", {})
    for sc in ext.get("scenarios", []):
        body = {"run_id": run_id, "target": sc.get("target", "*"), "sequence": sc.get("sequence") or [sc["scenario"]]}
        if "delay_s" in sc:
            body["delay_s"] = sc["delay_s"]
        if ext.get("options"):
            body["options"] = ext["options"]
        client.post("/__admin/scenario", json=body).raise_for_status()
    if ext.get("options") and not ext.get("scenarios"):
        client.post("/__admin/scenario", json={"run_id": run_id, "target": "*", "scenario": "success",
                                               "options": ext["options"]}).raise_for_status()
    catalogue = client.get("/venue/catalogue").json()["events"]
    competitors = [Bid(c["declaration_id"], c["user_id"], tuple(c["slots"]), c["group_size"], c.get("min_group_size", c["group_size"]),
                       c["max_price_paise"], c.get("allocations_last_30d", 0)) for c in setup.get("competitors", [])]
    log = DecisionLog(run_id, run_dir, "log.jsonl")
    engine = Engine(build_connectors(client, run_id, env={}), Store(), log, catalogue,
                    today=date.fromisoformat(setup.get("today", "2026-10-01")), competitors=competitors)
    decl = engine.new_declaration(declaration_id=f"decl-{case['id']}")
    session = Session(engine, decl, _policy(mode, version), version)
    for raw in case["human_input"]:
        turn = HumanTurn(text=raw.get("say"), interrupted=bool(raw.get("interrupted")),
                         event=raw.get("event") and {**raw["event"], "event_id": raw["event"].get("event_id") or f"{raw['event']['type']}-{len(session.snapshots)}"})
        session.step(turn)
        if raw.get("pause_s"):
            time.sleep(raw["pause_s"])
    mock_state = client.get("/__admin/state", params={"run_id": run_id}).json()
    result = RunResult(decl.model_dump(mode="json"), read_log(log.path), session.transcript, session.snapshots, mock_state)
    checks = [{"name": n, "passed": p, "detail": d, "builtin": True} for n, p, d in builtin_checks(result)]
    for c in case["pass_criteria"]:
        p, d = check(c, result)
        checks.append({"name": json.dumps(c), "passed": p, "detail": d, "builtin": False})
    for c in case.get("forbidden_checks", []):
        p, d = check(c, result)
        checks.append({"name": "forbidden: " + json.dumps(c), "passed": p, "detail": d, "builtin": False})
    verdict = {"run_id": run_id, "case": case["id"], "name": case["name"], "mode": mode, "policy": session.policy.name,
               "prompt_version": version, "passed": all(c["passed"] for c in checks), "final_state": decl.state.value,
               "checks": checks}
    (run_dir / "verdict.json").write_text(json.dumps(verdict, indent=2))
    lines = [f"# {case['id']} {case['name']} ({mode}, prompt {version})", ""]
    for t in session.transcript:
        who = {"user": "USER", "assistant": "KIRRO", "event": "EVENT"}[t["role"]]
        lines.append(f"- [{t['step']}] **{who}**: {t['text'] or '(silence)'}" + (" _(interrupted)_" if t.get("interrupted") else ""))
    lines += ["", f"Final state: {decl.state.value}. Verdict: {'PASS' if verdict['passed'] else 'FAIL'}"]
    (run_dir / "transcript.md").write_text("\n".join(lines) + "\n")
    verdict["run_dir"] = str(run_dir)
    return verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run KIRRO eval cases")
    ap.add_argument("case", help="E01..E10 or 'all'")
    ap.add_argument("--mode", choices=["offline", "live"], default="offline")
    ap.add_argument("--mock-url", default=None, help="use a running mock server instead of the in-process one")
    ap.add_argument("--prompt-version", default=None)
    a = ap.parse_args(argv)
    ids = all_case_ids() if a.case == "all" else [a.case]
    failed = 0
    for i in ids:
        v = run_case(load_case(i), a.mode, a.mock_url, prompt_version=a.prompt_version)
        print(f"{'PASS' if v['passed'] else 'FAIL'}  {v['case']}  {v['name']}  -> {v['final_state']}  ({v['run_dir']})")
        for c in v["checks"]:
            if not c["passed"]:
                print(f"      failed: {c['name']}  [{c['detail']}]")
        failed += not v["passed"]
    print(f"{len(ids) - failed}/{len(ids)} passed ({a.mode})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
