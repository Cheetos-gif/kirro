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
            self._load()

    def _load(self) -> None:
        """Restore what a previous process wrote. One unreadable file is skipped, never fatal —
        a corrupt declaration must not stop the process (and every other declaration) from booting."""
        for path in sorted(self.dir.glob("*.json")):
            if path.name == "ledger.json":
                continue
            try:
                d = Declaration.model_validate_json(path.read_text())
            except Exception:
                continue
            self.declarations[d.declaration_id] = d
        ledger_path = self.dir / "ledger.json"
        if not ledger_path.is_file():
            return
        try:
            raw = json.loads(ledger_path.read_text())
        except Exception:
            return
        for key, value in raw.items():
            try:
                self.ledger[key] = ConnectorResult.model_validate(value)
            except Exception:
                continue

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
