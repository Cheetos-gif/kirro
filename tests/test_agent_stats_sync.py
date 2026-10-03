"""Agent-stats sync (ADR-020) — offline tests.

No network: the AgenticOrg read is a plain async callable and the mock write is another, exactly the
two things `run_once` depends on.
"""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine

import pytest

from agent_stats_sync.config import DEFAULT_AGENT_IDS, ConfigError, StatsSyncConfig
from agent_stats_sync.run_once import extract_stats, run_once


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


def _env(**over: str) -> dict[str, str]:
    base = {
        "MOCK_API_URL": "http://mock.example",
        "AGENTICORG_BASE_URL": "https://agenticorg.example",
        "AGENTICORG_EMAIL": "agent@example.com",
        "AGENTICORG_PASSWORD": "hunter2",
    }
    return base | over


# --------------------------------------------------------------------------- config


def test_config_requires_the_agenticorg_credentials():
    for missing in ("MOCK_API_URL", "AGENTICORG_BASE_URL", "AGENTICORG_EMAIL", "AGENTICORG_PASSWORD"):
        env = _env()
        del env[missing]
        with pytest.raises(ConfigError):
            StatsSyncConfig.from_env(env)


def test_config_defaults_to_the_known_agents_and_no_admin_key():
    config = StatsSyncConfig.from_env(_env())
    assert config.agent_ids == DEFAULT_AGENT_IDS
    # Unset is meaningful, not an error: the mock's /__admin guard is a no-op without a key.
    assert config.mock_admin_key == ""
    assert config.run_id == "default"


def test_config_agent_ids_and_admin_key_can_be_overridden():
    config = StatsSyncConfig.from_env(_env(AGENT_STATS_AGENT_IDS="a1, a2 ,", MOCK_ADMIN_KEY="k", MOCK_RUN_ID="demo"))
    assert config.agent_ids == ("a1", "a2")
    assert config.mock_admin_key == "k"
    assert config.run_id == "demo"


# --------------------------------------------------------------------------- extract_stats


def test_extract_stats_keeps_only_the_displayed_fields_and_stamps_the_time():
    record = {
        "id": "agent-abc",
        "status": "active",
        "shadow_accuracy_current": 0.804,
        "shadow_sample_count": 26,
        "system_prompt_text": "x" * 5000,  # must never be copied into the mock
        "config": {"whatever": True},
    }
    stats = extract_stats(record, now="2026-10-04T00:00:00Z")
    assert stats == {
        "status": "active",
        "shadow_accuracy_current": 0.804,
        "shadow_sample_count": 26,
        "synced_at": "2026-10-04T00:00:00Z",
    }


def test_extract_stats_omits_fields_the_platform_does_not_expose():
    """A field the record lacks is absent from the stored stats, not zero — the portal shows "—"."""
    stats = extract_stats({"status": "shadow"}, now="2026-10-04T00:00:00Z")
    assert stats == {"status": "shadow", "synced_at": "2026-10-04T00:00:00Z"}
    assert "accuracy" not in stats


# --------------------------------------------------------------------------- run_once


def test_run_once_fetches_and_stores_every_agent():
    fetched: list[str] = []
    stored: dict[str, dict] = {}

    async def fetch(agent_id: str) -> dict:
        fetched.append(agent_id)
        return {"status": "active", "shadow_sample_count": 7}

    async def store(agent_id: str, stats: dict) -> None:
        stored[agent_id] = stats

    results = _run(run_once(agent_ids=("a1", "a2"), fetch=fetch, store=store))

    assert fetched == ["a1", "a2"]
    assert set(stored) == {"a1", "a2"}
    assert stored["a1"]["shadow_sample_count"] == 7
    assert "synced_at" in stored["a1"]
    assert [r.agent_id for r in results] == ["a1", "a2"]


def test_one_unreadable_agent_does_not_stop_the_others():
    stored: dict[str, dict] = {}

    async def fetch(agent_id: str) -> dict:
        if agent_id == "bad":
            raise RuntimeError("platform said no")
        return {"status": "active"}

    async def store(agent_id: str, stats: dict) -> None:
        stored[agent_id] = stats

    results = _run(run_once(agent_ids=("bad", "good"), fetch=fetch, store=store))

    assert list(stored) == ["good"]
    assert [r.agent_id for r in results] == ["good"]
