"""One pass of the allocator trigger (ADR-018): find closed, undrawn, non-empty releases and ask the
"Kirro Allocator" agent to draw each one.

Deliberately stateless. Idempotency across runs comes from the mock itself: `/allocator/draw` marks a
release `drawn` as a side effect of a real draw (`mock_server/app.py`), so a release this script has
already handed off is simply absent from the next pass's candidate list — no local checkpoint, no
database, nothing this script has to remember between invocations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger("allocator_bridge")

# Exact phrasing already verified against the live agent (docs/agenticorg/conversations/,
# docs/testing.md "workflow §2 happy path" and the L12-L16 re-checks): the Allocator reliably draws,
# holds, captures and releases from this one sentence.
TRIGGER_MESSAGE = "Run the allocation for release_id {release_id}: draw its bids and settle every one."


@dataclass(frozen=True)
class TriggerResult:
    release_id: str
    bids: int
    reply: str


async def candidate_releases(mock: httpx.AsyncClient, run_id: str) -> list[dict[str, Any]]:
    """Releases whose declare window has closed, that have not been drawn, and that have a bid.

    A release still accepting declarations (`declarations_open`) is skipped — drawing it early would
    cut off bids that are still allowed to arrive. A release with an empty pool is skipped too: there
    is nothing to settle, and the Allocator's prompt expects at least one bid.
    """
    listing = await mock.get("/venue/releases", headers={"X-Run-Id": run_id})
    listing.raise_for_status()
    candidates = []
    for release in listing.json()["releases"]:
        if release.get("declarations_open") or release.get("drawn"):
            continue
        pool = await mock.get(f"/venue/releases/{release['release_id']}/declarations", headers={"X-Run-Id": run_id})
        pool.raise_for_status()
        bids = pool.json().get("declarations", [])
        if bids:
            candidates.append({**release, "bid_count": len(bids)})
    return candidates


async def run_once(
    *,
    mock: httpx.AsyncClient,
    run_id: str,
    trigger: Callable[[str], Awaitable[str]],
) -> list[TriggerResult]:
    """Trigger the Allocator once per candidate release found this pass.

    `trigger` sends one message and returns the agent's reply; the caller is responsible for giving
    each call its own fresh conversation — one release's draw must never share a thread with
    another's, the same invariant `voice_bridge` keeps per call.
    """
    results = []
    for release in await candidate_releases(mock, run_id):
        release_id = release["release_id"]
        message = TRIGGER_MESSAGE.format(release_id=release_id)
        reply = await trigger(message)
        log.info(
            "triggered allocation",
            extra={"release_id": release_id, "bids": release["bid_count"]},
        )
        results.append(TriggerResult(release_id=release_id, bids=release["bid_count"], reply=reply))
    return results
