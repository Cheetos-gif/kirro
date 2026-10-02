"""Durable per-call conversation log (ADR-017 §logging).

One JSONL file per call under `log_dir`, in the same convention as the mock's own
`logs/mock/<run_id>.jsonl` (`MOCK_LOG_DIR`, `mock_server/state.py`): every structured log record
already carries a `call_id` (via the `LoggerAdapter`s in `agent.py`/`agenticorg.py`), so this is a
plain `logging.Handler` that demuxes by that field into `<log_dir>/<call_id>.jsonl` — no change to
how anything is logged, just where a call's own copy ends up. That copy outlives the pod's own log
retention and survives a restart (the directory is a PVC in `k8s/pvc.yaml`), so a call can be pulled
up by id long after `kubectl logs` has rolled the line away.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Attributes every `logging.LogRecord` carries regardless of what was passed as `extra`; anything
# else on the record is an application field worth keeping.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class CallLogger(logging.LoggerAdapter):
    """A `LoggerAdapter` that tags every record with `call_id`, in addition to whatever `extra`
    the call site passes — the stdlib `LoggerAdapter` default `process()` replaces the call's own
    `extra` with the adapter's, which would silently drop every field (`turn`, `thread_id_after`,
    `latency_ms`, ...) already being logged at each call site.
    """

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        kwargs["extra"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


class ConversationLogHandler(logging.Handler):
    """Appends every record carrying a `call_id` to `<log_dir>/<call_id>.jsonl`.

    Records without a `call_id` (startup, worker lifecycle, anything outside a call) are ignored —
    this is a per-conversation log, not a replacement for the pod's own stdout log.
    """

    def __init__(self, log_dir: str | Path) -> None:
        super().__init__()
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        # One process logs many calls over its lifetime but never the same call concurrently with
        # itself, so a single lock protecting the open-append-close below is enough.
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        call_id = getattr(record, "call_id", None)
        if not call_id:
            return
        try:
            entry = self._entry(record)
            line = json.dumps(entry, default=str)
        except Exception:
            self.handleError(record)
            return
        path = self._log_dir / f"{call_id}.jsonl"
        try:
            with self._lock, path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            self.handleError(record)

    @staticmethod
    def _entry(record: logging.LogRecord) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = logging.Formatter().formatException(record.exc_info)
        for key, value in vars(record).items():
            if key in _STANDARD_ATTRS or key in entry:
                continue
            entry[key] = value
        return entry
