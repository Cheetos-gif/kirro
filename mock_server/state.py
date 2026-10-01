"""Per-run mock state, scenario table and request log. Everything is keyed by run_id (X-Run-Id header)."""

from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
SCENARIOS = {
    "success",
    "no_inventory",
    "insufficient_balance",
    "timeout",
    "malformed",
    "duplicate",
    "booking_expired",
    "payment_failure",
    "partial_group",
    "upstream_500",
    "delayed",
}
DEFAULT_DELAY = {"timeout": 12.0, "delayed": 4.0}


def load_catalogue() -> dict:
    return json.loads((FIXTURES / "catalogue.json").read_text())


class RunState:
    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.used_capacity: dict[str, int] = defaultdict(int)
        self.holds: dict[str, dict] = {}
        self.bookings: dict[str, dict] = {}
        self.mandates: dict[str, dict] = {}
        self.payments: dict[str, dict] = {}
        self.shipments: dict[str, dict] = {}
        self.declarations: dict[str, dict[str, dict]] = {}
        self.idem: dict[tuple[str, str], tuple[int, Any]] = {}
        self.scenarios: dict[str, deque] = {}
        self.delay: dict[str, float] = {}
        self.options: dict[str, Any] = {}

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] += 1
        return f"{prefix}_{self.counters[prefix]:04d}"


class MockState:
    def __init__(self, log_dir: str | Path | None = None) -> None:
        self.runs: dict[str, RunState] = defaultdict(RunState)
        self.catalogue = load_catalogue()
        self.log_dir = Path(log_dir or os.environ.get("MOCK_LOG_DIR", "logs/mock"))

    def run(self, run_id: str) -> RunState:
        return self.runs[run_id]

    def reset(self, run_id: str | None = None) -> None:
        if run_id:
            self.runs.pop(run_id, None)
        else:
            self.runs.clear()

    def set_scenario(
        self, run_id: str, target: str, sequence: list[str], delay_s: float | None, options: dict | None
    ) -> None:
        for s in sequence:
            if s not in SCENARIOS:
                raise ValueError(f"unknown scenario {s!r}")
        r = self.run(run_id)
        r.scenarios[target] = deque(sequence)
        if delay_s is not None:
            r.delay[target] = delay_s
        if options:
            r.options.update(options)

    def next_scenario(self, run_id: str, target: str) -> str:
        """Pop the next scenario for a target; the last entry sticks. Falls back to '*' then success."""
        r = self.run(run_id)
        for key in (target, "*"):
            q = r.scenarios.get(key)
            if q:
                return q.popleft() if len(q) > 1 else q[0]
        return "success"

    def delay_for(self, run_id: str, target: str, scenario: str) -> float:
        r = self.run(run_id)
        return r.delay.get(target, r.delay.get("*", DEFAULT_DELAY.get(scenario, 0.0)))

    def log(self, run_id: str, entry: dict) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / f"{run_id}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
