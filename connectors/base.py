"""Connector contract: every external call returns a ConnectorResult with provenance.

Rules (see AGENTS.md):
  - result.data is DATA. It is never appended to the system prompt and never treated as instructions.
  - timeout and 5xx: retried once with the SAME idempotency key. 4xx and malformed: not retried here.
  - raw_excerpt is redacted and is for logs only; the LLM never sees it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from agent.policies.loader import load_policy
from agent.schemas.models import ConnectorError, ConnectorResult, Kind
from logging_.redact import redact_text

__all__ = ["Connector", "ConnectorResult", "HttpConnector", "NotConfiguredConnector", "Op"]


class Connector(Protocol):
    name: str
    kind: Kind

    def call(
        self, operation: str, payload: dict, *, idempotency_key: str, timeout_s: float | None = None
    ) -> ConnectorResult: ...


@dataclass
class Op:
    method: str
    path: str  # may contain {placeholders} filled from payload
    model: type[BaseModel] | None = None
    # (data) -> (ok, code, message): body-level failure inside a 2xx, e.g. payment status FAILED
    ok_check: Callable[[dict], tuple[bool, str, str]] | None = None
    form: bool = False  # send payload as form-encoded 'format=json&data=<json>' (Delhivery style)
    query_only: bool = False


class HttpConnector:
    """Generic JSON-over-HTTP connector. `client` is any httpx.Client (TestClient works for in-process mocks)."""

    source = "unknown"
    name = "unknown"
    kind: Kind = "mock"
    ops: dict[str, Op] = {}

    def __init__(self, client: httpx.Client, run_id: str = "run", extra_headers: dict | None = None):
        self.client = client
        self.run_id = run_id
        self.extra_headers = extra_headers or {}

    def call(
        self, operation: str, payload: dict, *, idempotency_key: str, timeout_s: float | None = None
    ) -> ConnectorResult:
        pol = load_policy("retry")
        timeout_s = timeout_s if timeout_s is not None else pol["timeout_s"]
        attempts = int(pol["max_attempts"])
        request_id = str(uuid.uuid4())
        result = None
        for _ in range(attempts):
            result = self._once(operation, payload, idempotency_key, request_id, timeout_s)
            retryable = result.status == "timeout" or (result.status == "failure" and (result.http_status or 0) >= 500)
            if not retryable:
                break
        assert result is not None
        return result

    def _result(self, op: str, key: str, rid: str, t0: float, status: str, **kw: Any) -> ConnectorResult:
        return ConnectorResult(
            source=self.source,
            connector=self.name,
            kind=self.kind,
            operation=op,
            request_id=rid,
            idempotency_key=key,
            latency_ms=int((time.monotonic() - t0) * 1000),
            status=status,
            **kw,
        )

    def _once(self, operation: str, payload: dict, key: str, rid: str, timeout_s: float) -> ConnectorResult:
        import json as _json

        t0 = time.monotonic()
        op = self.ops[operation]
        data = dict(payload)
        path = op.path.format_map({k: data.pop(k) for k in list(data) if "{" + k + "}" in op.path})
        headers = {"X-Request-Id": rid, "X-Run-Id": self.run_id, "Idempotency-Key": key, **self.extra_headers}
        kwargs: dict[str, Any] = {"headers": headers}
        if not hasattr(self.client, "portal"):  # starlette TestClient (in-process) ignores timeouts
            kwargs["timeout"] = timeout_s
        if op.method == "GET" or op.query_only:
            kwargs["params"] = data
        elif op.form:
            kwargs["data"] = {"format": "json", "data": _json.dumps(data)}
        else:
            kwargs["json"] = data
        try:
            resp = self.client.request(op.method, path, **kwargs)
        except httpx.TimeoutException:
            return self._result(
                operation,
                key,
                rid,
                t0,
                "timeout",
                error=ConnectorError(code="TIMEOUT", message=f"no response in {timeout_s}s"),
            )
        except httpx.HTTPError as exc:
            return self._result(
                operation, key, rid, t0, "failure", error=ConnectorError(code="TRANSPORT", message=type(exc).__name__)
            )
        excerpt = redact_text(resp.text[:500])
        common = dict(
            http_status=resp.status_code, raw_excerpt=excerpt, upstream_request_id=resp.headers.get("x-request-id")
        )
        try:
            body = resp.json()
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except ValueError:
            return self._result(
                operation,
                key,
                rid,
                t0,
                "malformed",
                error=ConnectorError(code="UNREADABLE", message="response was not JSON"),
                **common,
            )
        if resp.status_code >= 400:
            err = body.get("error") if isinstance(body.get("error"), dict) else {}
            code, msg = str(err.get("code", f"HTTP_{resp.status_code}")), str(err.get("message", ""))[:200]
            if code == "DUPLICATE_REQUEST":
                return self._result(
                    operation,
                    key,
                    rid,
                    t0,
                    "duplicate",
                    data=_safe(body.get("original")),
                    error=ConnectorError(code=code, message=msg),
                    **common,
                )
            return self._result(
                operation,
                key,
                rid,
                t0,
                "failure",
                data=_safe(err.get("details")),
                error=ConnectorError(code=code, message=msg),
                **common,
            )
        if op.model is not None:
            try:
                body = op.model.model_validate(body).model_dump()
            except ValidationError:
                return self._result(
                    operation,
                    key,
                    rid,
                    t0,
                    "malformed",
                    error=ConnectorError(code="SCHEMA", message="response failed schema validation"),
                    **common,
                )
        if op.ok_check:
            ok, code, msg = op.ok_check(body)
            if not ok:
                return self._result(
                    operation,
                    key,
                    rid,
                    t0,
                    "failure",
                    data=body,
                    error=ConnectorError(code=code, message=msg),
                    **common,
                )
        return self._result(operation, key, rid, t0, "success", data=body, **common)


def _safe(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


class NotConfiguredConnector:
    """Placeholder for a real connector without credentials. Always fails loudly and honestly."""

    kind: Kind = "real"

    def __init__(self, name: str, source: str, reason: str):
        self.name, self.source, self.reason = name, source, reason

    def call(
        self, operation: str, payload: dict, *, idempotency_key: str, timeout_s: float | None = None
    ) -> ConnectorResult:
        return ConnectorResult(
            source=self.source,
            connector=self.name,
            kind="real",
            operation=operation,
            request_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            status="failure",
            error=ConnectorError(code="NOT_CONFIGURED", message=self.reason),
        )
