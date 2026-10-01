"""Per-run mock state backed by SQLite, plus the scenario table and request log.

State is **durable** (ADR-013): every mutation is written through to SQLite, so the declare-interest pool,
holds, mandates, payments, bookings and the idempotency ledger all survive a process restart. The Declare Agent
writes a pool entry in one conversation; the Window Allocation Workflow reads it later, possibly after a redeploy —
before this, everything lived in process memory and a restart silently emptied the pool.

One file (`MOCK_DB_PATH`, default `<log dir>/mock.db`) with two tables:

    objects(run_id, kind, key, payload)   -- one JSON document per entity
    counters(run_id, name, value)         -- next_id() sequences and per-slot capacity in use

Every row carries `run_id`, so the existing per-run isolation is unchanged: two `X-Run-Id` values never see each
other's state. SQLite (not Postgres) because this is a single-writer, single-replica service that must keep
`uv run pytest` runnable offline with no credentials — see ADR-013 for the reasoning and the condition that would
change it. Writes serialise behind one connection (`check_same_thread=False` + a lock); the Deployment is pinned to
`replicas: 1`.

The containers exposed here (`holds`, `mandates`, …) keep the dict-like API the routes already use, but every write
goes to SQL — `run.holds[hid] = {...}` persists, and so does a nested mutation on a row returned by `.get()`
(`hold["released"] = True`).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Iterator, MutableMapping

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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
    run_id  TEXT NOT NULL,
    kind    TEXT NOT NULL,
    key     TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, kind, key)
);
CREATE TABLE IF NOT EXISTS counters (
    run_id TEXT NOT NULL,
    name   TEXT NOT NULL,
    key    TEXT NOT NULL,
    value  INTEGER NOT NULL,
    PRIMARY KEY (run_id, name, key)
);
"""


def load_catalogue() -> dict:
    return json.loads((FIXTURES / "catalogue.json").read_text())


def resolve_db_path(log_dir: str | Path | None = None, db_path: str | Path | None = None) -> Path:
    """MOCK_DB_PATH wins; otherwise the DB sits beside the request log, which keeps tests isolated
    (they pass a per-test `log_dir`) and the container explicit (`MOCK_DB_PATH=/app/data/mock.db`)."""
    if db_path:
        return Path(db_path)
    env = os.environ.get("MOCK_DB_PATH")
    if env:
        return Path(env)
    base = Path(log_dir) if log_dir else Path(os.environ.get("MOCK_LOG_DIR", "logs/mock"))
    return base / "mock.db"


class Store:
    """Thin SQLite wrapper: JSON documents keyed by (run_id, kind, key), and integer counters."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)
        self._db.commit()

    # ------------------------------------------------------------------ documents
    def get(self, run_id: str, kind: str, key: str) -> Any | None:
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM objects WHERE run_id=? AND kind=? AND key=?", (run_id, kind, key)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, run_id: str, kind: str, key: str, payload: Any) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO objects(run_id, kind, key, payload) VALUES(?,?,?,?) "
                "ON CONFLICT(run_id, kind, key) DO UPDATE SET payload=excluded.payload",
                (run_id, kind, key, json.dumps(payload, ensure_ascii=False)),
            )
            self._db.commit()

    def delete(self, run_id: str, kind: str, key: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM objects WHERE run_id=? AND kind=? AND key=?", (run_id, kind, key))
            self._db.commit()
        return cur.rowcount > 0

    def keys(self, run_id: str, kind: str) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT key FROM objects WHERE run_id=? AND kind=? ORDER BY key", (run_id, kind)
            ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ counters
    def int_get(self, run_id: str, name: str, key: str) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM counters WHERE run_id=? AND name=? AND key=?", (run_id, name, key)
            ).fetchone()
        return int(row[0]) if row else 0

    def int_set(self, run_id: str, name: str, key: str, value: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO counters(run_id, name, key, value) VALUES(?,?,?,?) "
                "ON CONFLICT(run_id, name, key) DO UPDATE SET value=excluded.value",
                (run_id, name, key, int(value)),
            )
            self._db.commit()

    def int_incr(self, run_id: str, name: str, key: str, delta: int = 1) -> int:
        """Atomic read-modify-write: the reason this moved off in-memory dicts and onto SQL."""
        with self._lock:
            self._db.execute(
                "INSERT INTO counters(run_id, name, key, value) VALUES(?,?,?,?) "
                "ON CONFLICT(run_id, name, key) DO UPDATE SET value=value+excluded.value",
                (run_id, name, key, int(delta)),
            )
            self._db.commit()
            row = self._db.execute(
                "SELECT value FROM counters WHERE run_id=? AND name=? AND key=?", (run_id, name, key)
            ).fetchone()
        return int(row[0])

    def int_keys(self, run_id: str, name: str) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT key FROM counters WHERE run_id=? AND name=? ORDER BY key", (run_id, name)
            ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ lifecycle
    def clear(self, run_id: str | None = None) -> None:
        with self._lock:
            if run_id:
                self._db.execute("DELETE FROM objects WHERE run_id=?", (run_id,))
                self._db.execute("DELETE FROM counters WHERE run_id=?", (run_id,))
            else:
                self._db.execute("DELETE FROM objects")
                self._db.execute("DELETE FROM counters")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()


class Row(dict):
    """A stored document. Mutating it (even nested, e.g. `hold["released"] = True`) writes it back."""

    def __init__(self, store: Store, run_id: str, kind: str, key: str, data: dict) -> None:
        super().__init__(data)
        self._store, self._run_id, self._kind, self._key = store, run_id, kind, key

    def save(self) -> None:
        self._store.put(self._run_id, self._kind, self._key, dict(self))

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self.save()

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self.save()

    def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().update(*args, **kwargs)
        self.save()

    def pop(self, *args: Any) -> Any:  # type: ignore[override]
        value = super().pop(*args)
        self.save()
        return value

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        self.save()

    def setdefault(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        if key not in self:
            self[key] = default
        return self[key]


class PTable(MutableMapping):
    """A table of stored documents, keyed by string."""

    def __init__(self, store: Store, run_id: str, kind: str) -> None:
        self._store, self._run_id, self._kind = store, run_id, kind

    def __getitem__(self, key: str) -> Row:
        payload = self._store.get(self._run_id, self._kind, key)
        if payload is None:
            raise KeyError(key)
        return Row(self._store, self._run_id, self._kind, key, payload)

    def __setitem__(self, key: str, value: dict) -> None:
        self._store.put(self._run_id, self._kind, key, dict(value))

    def __delitem__(self, key: str) -> None:
        if not self._store.delete(self._run_id, self._kind, key):
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store.keys(self._run_id, self._kind))

    def __len__(self) -> int:
        return len(self._store.keys(self._run_id, self._kind))

    def setdefault(self, key: str, default: Any = None) -> Row:  # type: ignore[override]
        # Re-read so callers get a Row (which persists nested writes), not the plain default.
        if not self._store.get(self._run_id, self._kind, key):
            self._store.put(self._run_id, self._kind, key, default if default is not None else {})
        return self[key]


class IntTable(MutableMapping):
    """A table of integer counters. Missing keys read as 0, like the defaultdict it replaces."""

    def __init__(self, store: Store, run_id: str, name: str) -> None:
        self._store, self._run_id, self._name = store, run_id, name

    def __getitem__(self, key: str) -> int:
        return self._store.int_get(self._run_id, self._name, key)

    def __setitem__(self, key: str, value: int) -> None:
        self._store.int_set(self._run_id, self._name, key, int(value))

    def __delitem__(self, key: str) -> None:
        self._store.int_set(self._run_id, self._name, key, 0)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store.int_keys(self._run_id, self._name))

    def __len__(self) -> int:
        return len(self._store.int_keys(self._run_id, self._name))

    def incr(self, key: str, delta: int = 1) -> int:
        return self._store.int_incr(self._run_id, self._name, key, delta)


class Idem(MutableMapping):
    """The idempotency ledger: (target, idempotency key) -> (status, payload)."""

    def __init__(self, store: Store, run_id: str) -> None:
        self._store, self._run_id = store, run_id

    @staticmethod
    def _key(key: tuple[str, str]) -> str:
        return f"{key[0]}\x00{key[1]}"

    def __getitem__(self, key: tuple[str, str]) -> tuple[int, Any]:
        payload = self._store.get(self._run_id, "idem", self._key(key))
        if payload is None:
            raise KeyError(key)
        return int(payload[0]), payload[1]

    def __setitem__(self, key: tuple[str, str], value: tuple[int, Any]) -> None:
        self._store.put(self._run_id, "idem", self._key(key), [value[0], value[1]])

    def __delitem__(self, key: tuple[str, str]) -> None:
        if not self._store.delete(self._run_id, "idem", self._key(key)):
            raise KeyError(key)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for key in self._store.keys(self._run_id, "idem"):
            target, _, idem = key.partition("\x00")
            yield (target, idem)

    def __len__(self) -> int:
        return len(self._store.keys(self._run_id, "idem"))


class RunState:
    """Per-run handle over the store. Attribute names match the previous in-memory version."""

    def __init__(self, store: Store, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.holds = PTable(store, run_id, "holds")
        self.bookings = PTable(store, run_id, "bookings")
        self.mandates = PTable(store, run_id, "mandates")
        self.payments = PTable(store, run_id, "payments")
        self.shipments = PTable(store, run_id, "shipments")
        self.declarations = PTable(store, run_id, "declarations")
        self.used_capacity = IntTable(store, run_id, "capacity")
        self.counters = IntTable(store, run_id, "counters")
        self.idem = Idem(store, run_id)
        # Scenario control is harness-only, not business state: deliberately in memory.
        self.scenarios: dict[str, deque] = {}
        self.delay: dict[str, float] = {}
        self.options: dict[str, Any] = {}

    def next_id(self, prefix: str) -> str:
        return f"{prefix}_{self.counters.incr(prefix):04d}"


class MockState:
    def __init__(self, log_dir: str | Path | None = None, db_path: str | Path | None = None) -> None:
        self.runs: dict[str, RunState] = {}
        self.catalogue = load_catalogue()
        self.log_dir = Path(log_dir or os.environ.get("MOCK_LOG_DIR", "logs/mock"))
        self.db_path = resolve_db_path(log_dir, db_path)
        self.store = Store(self.db_path)
        self._log_warned = False

    def run(self, run_id: str) -> RunState:
        state = self.runs.get(run_id)
        if state is None:
            state = self.runs[run_id] = RunState(self.store, run_id)
        return state

    def reset(self, run_id: str | None = None) -> None:
        if run_id:
            self.runs.pop(run_id, None)
        else:
            self.runs.clear()
        self.store.clear(run_id)

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
        """Append to the request log. A logging failure must never fail the mocked call itself:
        the mock's job is to answer like a vendor API, so this degrades to a one-time warning."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_dir / f"{run_id}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            if not self._log_warned:
                self._log_warned = True
                print(f"[mock] request logging disabled ({self.log_dir}): {exc}", file=sys.stderr)
