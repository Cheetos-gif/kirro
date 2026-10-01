"""Render connector output for the LLM. External text is DATA: fenced, truncated, stripped of fence tokens."""

from __future__ import annotations

import json
import re
from typing import Any

from agent.schemas.models import ConnectorResult

_FENCE = re.compile(r"<<|>>")


def _clean(v: Any, depth: int = 0) -> Any:
    if isinstance(v, str):
        return _FENCE.sub("", v)[:120]
    if isinstance(v, dict) and depth < 3:
        return {str(k)[:40]: _clean(x, depth + 1) for k, x in list(v.items())[:20]}
    if isinstance(v, list) and depth < 3:
        return [_clean(x, depth + 1) for x in v[:10]]
    return v


def render_connector_result(r: ConnectorResult) -> str:
    """Never includes raw_excerpt. The system prompt says content inside the fence is not instructions."""
    body = {
        "operation": r.operation,
        "status": r.status,
        "error": r.error.model_dump() if r.error else None,
        "data": _clean(r.data),
    }
    return (
        f"<<external_data source={r.source} connector={r.connector} kind={r.kind} status={r.status}>>\n"
        f"{json.dumps(body, ensure_ascii=False)}\n<</external_data>>"
    )
