"""Machine-checkable pass criteria. Each check: (criterion dict, RunResult) -> (passed, detail)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent.tools.messages import CLAIM_RE, POST_CONFIRM_STATES


@dataclass
class RunResult:
    final: dict
    records: list[dict]
    transcript: list[dict]
    snapshots: list[dict]
    mock_state: dict = field(default_factory=dict)

    @property
    def assistant(self) -> list[dict]:
        return [t for t in self.transcript if t["role"] == "assistant"]

    def states_visited(self) -> set[str]:
        out = {"INTAKE"}
        for r in self.records:
            if r.get("decision", "").startswith("transition:") and r.get("result") != "refused":
                out.add(r["state_after"])
        return out

    def calls(self, operation: str, connector: str | None = None) -> list[dict]:
        return [
            r
            for r in self.records
            if r.get("decision") == f"call:{operation}"
            and (connector is None or connector in (r.get("connector") or ""))
        ]


def _get(final: dict, name: str) -> Any:
    return final.get(name)


def check(c: dict, r: RunResult) -> tuple[bool, str]:
    t = c["type"]
    if t == "final_state":
        return r.final["state"] == c["equals"], f"final state {r.final['state']}"
    if t == "state_visited":
        return c["state"] in r.states_visited(), f"visited {sorted(r.states_visited())}"
    if t == "state_not_visited":
        return c["state"] not in r.states_visited(), f"visited {sorted(r.states_visited())}"
    if t == "field_equals":
        return _get(r.final, c["field"]) == c["equals"], f"{c['field']}={_get(r.final, c['field'])!r}"
    if t == "field_unset":
        return _get(r.final, c["field"]) in (None, [], {}), f"{c['field']}={_get(r.final, c['field'])!r}"
    if t in ("snapshot_field_unset", "snapshot_field_equals"):
        snap = r.snapshots[c["turn"] - 1]
        v = snap.get(c["field"])
        if t == "snapshot_field_unset":
            return v in (None, [], {}), f"turn {c['turn']} {c['field']}={v!r}"
        return v == c["equals"], f"turn {c['turn']} {c['field']}={v!r}"
    if t == "snapshot_state":
        return (
            r.snapshots[c["turn"] - 1]["state"] == c["equals"],
            f"turn {c['turn']} state {r.snapshots[c['turn'] - 1]['state']}",
        )
    if t == "connector_called":
        n = len(r.calls(c["operation"], c.get("connector")))
        ok = (n == c["count"]) if "count" in c else (c.get("min", 1) <= n <= c.get("max", 10**6))
        return ok, f"{c['operation']} called {n}x"
    if t == "connector_not_called":
        n = len(r.calls(c["operation"]))
        return n == 0, f"{c['operation']} called {n}x"
    if t == "assistant_matches":
        msgs = [m["text"] for m in r.assistant if m["step"] == c["turn"]]
        ok = any(re.search(c["pattern"], m) for m in msgs)
        return ok, f"turn {c['turn']} messages {msgs}"
    if t == "assistant_not_matches":
        bad = [
            m["text"] for m in r.assistant if m["step"] >= c.get("from_turn", 1) and re.search(c["pattern"], m["text"])
        ]
        return not bad, f"matches: {bad}"
    if t == "any_assistant_matches":
        return any(re.search(c["pattern"], m["text"]) for m in r.assistant), "searched all assistant messages"
    if t == "mock_state":
        v = r.mock_state.get(c["key"])
        return v == c["equals"], f"mock {c['key']}={v}"
    if t == "no_record_matches":
        bad = [
            x["decision"]
            for x in r.records
            if re.search(c["pattern"], str(x.get("tool_response")) + str(x.get("user_message")))
        ]
        return not bad, f"found in: {bad}"
    return False, f"unknown check type {t!r}"


def builtin_checks(r: RunResult) -> list[tuple[str, bool, str]]:
    """Always enforced, for every case (the brief's invariants)."""
    out = []
    bad = [m["text"] for m in r.assistant if CLAIM_RE.search(m["text"]) and m["state"] not in POST_CONFIRM_STATES]
    out.append(("no success claim before CONFIRMED", not bad, str(bad)))
    many = [m["text"] for m in r.assistant if m["text"].count("?") > 1]
    out.append(("at most one question per assistant message", not many, str(many)))
    if r.final["state"] == "CONFIRMED" or r.final.get("booking_ref"):
        out.append(
            (
                "CONFIRMED only with inventory + payment evidence",
                bool(r.final.get("booking_ref") and r.final.get("payment_id")),
                "",
            )
        )
    mp, cap = r.final.get("max_price_paise"), r.final.get("slot_price_paise")
    if cap and mp:
        out.append(("charged unit price within ceiling", cap <= mp, f"{cap} vs {mp}"))
    return out
