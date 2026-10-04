"""One pass of the agent-stats sync (ADR-020): read each known agent's record from AgenticOrg and
store the fields the portal displays in the mock.

Deliberately stateless, like `allocator_bridge`: nothing is remembered between passes. Idempotency is
"the latest read wins" — each pass overwrites the previous snapshot for an agent, and a pass that
fails for one agent leaves that agent's previous snapshot untouched rather than blanking it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

log = logging.getLogger("agent_stats_sync")

# The fields worth copying out of an AgenticOrg agent record. Everything else on the record is either
# huge (the prompt), tenant-internal, or changes for reasons a stat card should not show. A field the
# platform stops exposing is simply absent, which the portal renders as "—" rather than as a zero.
STAT_FIELDS = (
    "name",
    "status",
    "accuracy",
    "shadow_accuracy_current",
    "shadow_sample_count",
    "shadow_min_samples",
    "shadow_accuracy_floor",
)


@dataclass(frozen=True)
class SyncResult:
    agent_id: str
    stored: dict[str, Any]


def extract_stats(record: dict[str, Any], *, now: str) -> dict[str, Any]:
    """The storable subset of an AgenticOrg agent record, plus when it was read."""
    stats = {field: record[field] for field in STAT_FIELDS if field in record}
    stats["synced_at"] = now
    return stats


async def run_once(
    *,
    agent_ids: tuple[str, ...],
    fetch: Callable[[str], Awaitable[dict[str, Any]]],
    store: Callable[[str, dict[str, Any]], Awaitable[None]],
) -> list[SyncResult]:
    """Read and store stats for every agent, one at a time.

    A failure for one agent is logged and skipped, not raised: two agents' stats are independent, and
    one unreadable record should not cost the other its refresh. Raising here would fail the whole
    Job and, worse, hide a partial success.
    """
    results: list[SyncResult] = []
    for agent_id in agent_ids:
        try:
            record = await fetch(agent_id)
        except Exception as exc:  # noqa: BLE001 — one bad agent must not stop the others
            log.warning("could not read agent stats", extra={"agent_id": agent_id, "error": str(exc)})
            continue
        stats = extract_stats(record, now=datetime.now(timezone.utc).isoformat())
        await store(agent_id, stats)
        log.info("stored agent stats", extra={"agent_id": agent_id, "status": stats.get("status")})
        results.append(SyncResult(agent_id=agent_id, stored=stats))
    return results
