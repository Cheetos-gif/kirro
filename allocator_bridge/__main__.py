"""python -m allocator_bridge — one pass, meant to run on a schedule (k8s CronJob, ADR-018).

Exit code is a plain health signal for the Job's own retry/backoff: 0 for "ran, whether or not any
release needed triggering", 1 for "could not reach AgenticOrg". A release-level failure inside the
Allocator's own conversation is not this script's to judge — the Allocator agent reports and handles
its own tool failures, exactly as it already does when chatted with directly.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import httpx

from allocator_bridge.config import AllocatorConfig
from allocator_bridge.run_once import run_once
from voice_bridge.agenticorg import AgentChat, AgentChatError

log = logging.getLogger("allocator_bridge")


async def _main() -> int:
    config = AllocatorConfig.from_env()
    async with httpx.AsyncClient(base_url=config.mock_base_url, timeout=config.request_timeout_s) as mock:

        async def trigger(message: str) -> str:
            # A fresh client, and so a fresh conversation, per release: one release's draw must never
            # share a thread with another's.
            chat = AgentChat(
                base_url=config.agenticorg_base_url,
                email=config.agenticorg_email,
                password=config.agenticorg_password,
                agent_id=config.agent_id,
                timeout_s=config.request_timeout_s,
            )
            try:
                return await chat.ask(message)
            finally:
                await chat.aclose()

        try:
            results = await run_once(mock=mock, run_id=config.run_id, trigger=trigger)
        except AgentChatError as exc:
            log.error("allocator trigger could not reach AgenticOrg: %s", exc)
            return 1
    if results:
        log.info(
            "triggered %d release(s): %s",
            len(results),
            ", ".join(f"{r.release_id} ({r.bids} bids)" for r in results),
        )
    else:
        log.info("no release needed triggering this pass")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
