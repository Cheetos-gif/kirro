"""In-memory store with optional JSON persistence, plus the idempotency ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent.schemas.models import ConnectorResult, Declaration


def idempotency_key(declaration_id: str, state: str, scope: str) -> str:
    """sha256(declaration_id + state + attempt_scope). Scope names the logical action."""
    return hashlib.sha256(f"{declaration_id}|{state}|{scope}".encode()).hexdigest()[:40]


def is_final(result: ConnectorResult) -> bool:
    """Only final outcomes are stored; timeouts, malformed bodies and 5xx stay retryable."""
    if result.status in ("timeout", "malformed"):
        return False
    if result.status == "failure" and (result.http_status or 0) >= 500:
        return False
    return True


class Store:
    def __init__(self, directory: str | Path | None = None):
        self.dir = Path(directory) if directory else None
        self.declarations: dict[str, Declaration] = {}
        self.ledger: dict[str, ConnectorResult] = {}
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def put(self, d: Declaration) -> None:
        self.declarations[d.declaration_id] = d
        if self.dir:
            (self.dir / f"{d.declaration_id}.json").write_text(d.model_dump_json(indent=2))

    def get(self, declaration_id: str) -> Declaration:
        return self.declarations[declaration_id]

    def ledger_get(self, key: str) -> ConnectorResult | None:
        return self.ledger.get(key)

    def ledger_put(self, key: str, result: ConnectorResult) -> None:
        if is_final(result):
            self.ledger[key] = result
            if self.dir:
                (self.dir / "ledger.json").write_text(
                    json.dumps({k: v.model_dump() for k, v in self.ledger.items()}, indent=1)
                )
