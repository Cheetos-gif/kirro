"""Allocator-trigger bridge (ADR-018) — offline tests.

No network, no AgenticOrg, no real mock server: the mock's `/venue/releases` and
`/venue/releases/{id}/declarations` responses are stubbed with `httpx.MockTransport`, and the
AgenticOrg side is a plain async callable, exactly the shape `run_once` depends on.
"""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine

import httpx
import pytest

from allocator_bridge.config import AllocatorConfig, ConfigError
from allocator_bridge.run_once import TRIGGER_MESSAGE, candidate_releases, run_once


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


class _Mock:
    """A stand-in for `mock_server`: just enough of the two routes `run_once` reads."""

    def __init__(self, releases: list[dict], pools: dict[str, list[dict]] | None = None) -> None:
        self.releases = releases
        self.pools = pools or {}
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        if request.url.path == "/venue/releases":
            return httpx.Response(200, json={"releases": self.releases})
        if request.url.path.startswith("/venue/releases/") and request.url.path.endswith("/declarations"):
            release_id = request.url.path.split("/")[3]
            return httpx.Response(200, json={"release_id": release_id, "declarations": self.pools.get(release_id, [])})
        return httpx.Response(404)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="http://mock.example", transport=httpx.MockTransport(self.handler))


def _release(release_id: str, *, declarations_open: bool = False, drawn: bool = False) -> dict:
    return {
        "release_id": release_id,
        "event_id": "ev_tennis",
        "date": "2026-10-10",
        "opens_at": "2026-10-09T06:00:00Z",
        "allocation_mode": "fair_draw",
        "declarations_open": declarations_open,
        "drawn": drawn,
    }


def _bid(declaration_id: str) -> dict:
    return {"declaration_id": declaration_id, "group_size": 2, "min_group_size": 2, "max_price_paise": 60000}


# --- configuration ----------------------------------------------------------------------------


def test_config_requires_the_credentials_and_the_mock_url() -> None:
    with pytest.raises(ConfigError):
        AllocatorConfig.from_env({})


def test_config_defaults_the_agent_id_run_id_and_timeout() -> None:
    config = AllocatorConfig.from_env(
        {
            "MOCK_API_URL": "http://kirro-mock:8081/",
            "AGENTICORG_BASE_URL": "https://agenticorg.example/",
            "AGENTICORG_EMAIL": "a@b.c",
            "AGENTICORG_PASSWORD": "secret",
        }
    )
    assert config.mock_base_url == "http://kirro-mock:8081"
    assert config.agenticorg_base_url == "https://agenticorg.example"
    assert config.agent_id == "5591e57a-79f9-4b30-a95e-0b910a467ce3"
    assert config.run_id == "default"
    assert config.request_timeout_s == 180.0


def test_config_accepts_explicit_overrides() -> None:
    config = AllocatorConfig.from_env(
        {
            "MOCK_API_URL": "http://kirro-mock:8081",
            "AGENTICORG_BASE_URL": "https://agenticorg.example",
            "AGENTICORG_EMAIL": "a@b.c",
            "AGENTICORG_PASSWORD": "secret",
            "ALLOCATOR_AGENT_ID": "agent-9",
            "MOCK_RUN_ID": "eval",
            "ALLOCATOR_TIMEOUT_S": "30",
        }
    )
    assert config.agent_id == "agent-9" and config.run_id == "eval" and config.request_timeout_s == 30.0


# --- candidate_releases -------------------------------------------------------------------------


def test_candidate_releases_skips_open_drawn_and_empty_pools() -> None:
    """Only a release whose window has closed, that has never been drawn, and that still has a bid
    waiting is worth asking the Allocator about."""
    mock = _Mock(
        releases=[
            _release("rel_open"),  # still accepting declarations -- not closed yet
            _release("rel_drawn_already"),  # closed, already drawn
            _release("rel_empty"),  # closed, never drawn, but nobody declared
            _release("rel_ready"),  # closed, never drawn, one bid waiting
        ],
        pools={
            "rel_open": [_bid("d1")],
            "rel_drawn_already": [_bid("d2")],
            "rel_ready": [_bid("d3"), _bid("d4")],
        },
    )
    mock.releases[0]["declarations_open"] = True
    mock.releases[1]["drawn"] = True

    async def go():
        async with mock.client() as client:
            return await candidate_releases(client, "default")

    candidates = _run(go())
    assert [c["release_id"] for c in candidates] == ["rel_ready"]
    assert candidates[0]["bid_count"] == 2
    # the open and already-drawn releases were never even checked for bids
    assert "/venue/releases/rel_open/declarations" not in mock.requests
    assert "/venue/releases/rel_drawn_already/declarations" not in mock.requests


def test_candidate_releases_is_empty_when_nothing_qualifies() -> None:
    mock = _Mock(releases=[{**_release("rel_a"), "declarations_open": True}, _release("rel_b", drawn=True)])

    async def go():
        async with mock.client() as client:
            return await candidate_releases(client, "default")

    assert _run(go()) == []


# --- run_once -------------------------------------------------------------------------------


def test_run_once_triggers_each_candidate_with_the_verified_message() -> None:
    mock = _Mock(
        releases=[_release("rel_a"), _release("rel_b")],
        pools={"rel_a": [_bid("d1")], "rel_b": [_bid("d2"), _bid("d3")]},
    )
    sent: list[str] = []

    async def trigger(message: str) -> str:
        sent.append(message)
        return "The allocation process has been completed."

    async def go():
        async with mock.client() as client:
            return await run_once(mock=client, run_id="default", trigger=trigger)

    results = _run(go())
    assert sent == [
        TRIGGER_MESSAGE.format(release_id="rel_a"),
        TRIGGER_MESSAGE.format(release_id="rel_b"),
    ]
    assert [(r.release_id, r.bids) for r in results] == [("rel_a", 1), ("rel_b", 2)]
    assert all(r.reply == "The allocation process has been completed." for r in results)


def test_run_once_triggers_nothing_when_no_release_qualifies() -> None:
    mock = _Mock(releases=[{**_release("rel_a"), "declarations_open": True}])
    calls = []

    async def trigger(message: str) -> str:
        calls.append(message)
        return "unused"

    async def go():
        async with mock.client() as client:
            return await run_once(mock=client, run_id="default", trigger=trigger)

    assert _run(go()) == []
    assert calls == []
