"""Structured JSONL decision log. One line per decision. Redacts on write."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.schemas.models import DecisionRecord
from logging_.redact import redact


class DecisionLog:
    def __init__(self, run_id: str, directory: str | Path = "logs", filename: str | None = None):
        self.run_id = run_id
        self.path = Path(directory) / (filename or f"{run_id}.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self._seq = 0

    def record(self, **fields: Any) -> dict[str, Any]:
        self._seq += 1
        rec = DecisionRecord(run_id=self.run_id, seq=self._seq, **fields)
        data = redact(json.loads(rec.model_dump_json()))
        self.records.append(data)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")
        return data


def read_log(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
