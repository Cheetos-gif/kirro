"""python -m agent_stats_sync — one pass, meant to run on a schedule (k8s CronJob, ADR-020).

Exit code is a plain health signal for the Job's own retry/backoff: 0 for "ran", 1 for "could not
reach AgenticOrg at all". A single unreadable agent record is logged and skipped inside `run_once`
rather than failing the pass — the other agent's stats are worth refreshing either way.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import httpx

from agent_stats_sync.config import StatsSyncConfig
from agent_stats_sync.run_once import run_once
from voice_bridge.agenticorg import AgentChat, AgentChatError

log = logging.getLogger("agent_stats_sync")


async def _main() -> int:
    config = StatsSyncConfig.from_env()
    async with httpx.AsyncClient(base_url=config.mock_base_url, timeout=config.request_timeout_s) as mock:
        admin_headers = {"X-Admin-Key": config.mock_admin_key} if config.mock_admin_key else {}

        async def store(agent_id: str, stats: dict) -> None:
            response = await mock.put(f"/__admin/agent-stats/{agent_id}", json=stats, headers=admin_headers)
            response.raise_for_status()

        # One client, one login for the whole pass: unlike the allocator bridge (a fresh conversation
        # per release), reading several agents' records is the same session and the same thread, and
        # logging in once per agent would just be four logins.
        chat = AgentChat(
            base_url=config.agenticorg_base_url,
            email=config.agenticorg_email,
            password=config.agenticorg_password,
            agent_id=config.agent_ids[0],
            timeout_s=config.request_timeout_s,
        )

        async def fetch(agent_id: str) -> dict:
            return await chat.get_json(f"/api/v1/agents/{agent_id}")

        try:
            results = await run_once(agent_ids=config.agent_ids, fetch=fetch, store=store)
        except AgentChatError as exc:
            log.error("stats sync could not reach AgenticOrg: %s", exc)
            return 1
        except httpx.HTTPError as exc:
            # The read side failed for every agent, or the mock refused a write. Either way the pass
            # achieved nothing and the Job's backoff should know: a plain traceback would be a worse
            # signal than a logged, non-zero exit.
            log.error("stats sync could not store stats in the mock: %s", exc)
            return 1
        finally:
            await chat.aclose()

    log.info(
        "synced %d/%d agent(s): %s",
        len(results),
        len(config.agent_ids),
        ", ".join(r.agent_id for r in results) or "none",
    )
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
