"""Voice bridge (ADR-016, ADR-017) — offline tests.

The speech side is Gnani's own LiveKit plugin and the transport is LiveKit's, so what this repo owns
— and what these tests cover — is the AgenticOrg client, the LLM adapter that exposes that agent to
the LiveKit pipeline, and the wiring between them. No network, no LiveKit server, no Gnani.

Async cases run through `asyncio.run` rather than a pytest plugin, to keep the test dependencies as
they are.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Coroutine

import httpx
import pytest
from livekit.agents.llm import LLM, ChatContext

from voice_bridge.agenticorg import AgentChat, AgentChatError
from voice_bridge.agenticorg_llm import AgenticOrgChat, build_llm, latest_user_text
from voice_bridge.config import ConfigError, VoiceConfig

CSRF = "csrf-token-value"


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


def _config(**overrides: Any) -> VoiceConfig:
    base = dict(
        gnani_api_key="gnani-key",
        agenticorg_base_url="https://agenticorg.example",
        agenticorg_email="bridge@example.com",
        agenticorg_password="secret",
        agent_id="agent-1",
        language="en-IN",
        voice="Kaveri",
        tts_model="timbre-v2.5",
        livekit_url="ws://livekit.example",
        livekit_api_key="devkey",
        livekit_api_secret="devsecret",
        health_port=8082,
        request_timeout_s=30.0,
    )
    base.update(overrides)
    return VoiceConfig(**base)


class _Platform:
    """A stand-in for AgenticOrg: login, CSRF, one canned agent reply, and a request log."""

    def __init__(self, *, answer: str = "Which date would you like?", fail_query: bool = False) -> None:
        self.answer = answer
        self.fail_query = fail_query
        self.logins = 0
        self.queries: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/auth/login":
            self.logins += 1
            return httpx.Response(
                200,
                json={"user": {"email": "bridge@example.com"}},
                headers={"set-cookie": f"agenticorg_csrf={CSRF}; Path=/"},
            )
        if path == "/api/v1/chat/query":
            self.queries.append(
                {
                    "body": json.loads(request.content),
                    "csrf_header": request.headers.get("x-csrf-token"),
                }
            )
            if self.fail_query:
                return httpx.Response(500, text="upstream boom")
            return httpx.Response(200, json={"answer": self.answer, "confidence": 0.8})
        return httpx.Response(404)

    def chat(self) -> AgentChat:
        return AgentChat(
            base_url="https://agenticorg.example",
            email="bridge@example.com",
            password="secret",
            agent_id="agent-1",
            client=httpx.AsyncClient(
                base_url="https://agenticorg.example",
                transport=httpx.MockTransport(self.handler),
            ),
        )


# --- configuration ----------------------------------------------------------------------------


def test_config_requires_the_credentials_and_the_livekit_room() -> None:
    with pytest.raises(ConfigError):
        VoiceConfig.from_env({})


def test_config_accepts_the_gnani_key_under_any_of_its_names() -> None:
    base = {
        "AGENTICORG_BASE_URL": "https://agenticorg.example/",
        "AGENTICORG_EMAIL": "a@b.c",
        "AGENTICORG_PASSWORD": "p",
        "LIVEKIT_URL": "ws://livekit.example",
        "LIVEKIT_API_KEY": "k",
        "LIVEKIT_API_SECRET": "s",
    }
    for name in ("GNANI_API_KEY", "GNANI_API_KEY_ID", "VACHANA_API_KEY_ID"):
        assert VoiceConfig.from_env({**base, name: "the-key"}).gnani_api_key == "the-key"

    config = VoiceConfig.from_env({**base, "GNANI_API_KEY": "k"})
    assert config.agenticorg_base_url == "https://agenticorg.example"
    assert config.tts_model == "timbre-v2.5"
    assert config.voice == "Kaveri"
    assert config.health_port == 8082


# --- the transcript the pipeline hands the adapter --------------------------------------------


def test_latest_user_text_returns_the_newest_user_turn() -> None:
    ctx = ChatContext()
    ctx.add_message(role="user", content="first thing")
    ctx.add_message(role="assistant", content="an answer")
    ctx.add_message(role="user", content=["second thing", "continued"])
    assert latest_user_text(ctx) == "second thing continued"


def test_latest_user_text_is_empty_without_a_user_turn() -> None:
    ctx = ChatContext()
    ctx.add_message(role="assistant", content="only the agent has spoken")
    assert latest_user_text(ctx) == ""


# --- the AgenticOrg client --------------------------------------------------------------------


def test_the_agent_client_logs_in_then_sends_the_message_with_csrf() -> None:
    platform = _Platform(answer="Badminton it is.")
    chat = platform.chat()

    reply = _run(chat.ask("badminton please"))

    assert reply == "Badminton it is."
    assert platform.logins == 1
    assert platform.queries[0]["body"] == {
        "query": "badminton please",
        "agent_id": "agent-1",
        # The platform rejects the header form alone; the body field is what it accepts.
        "csrf_token": CSRF,
    }
    assert platform.queries[0]["csrf_header"] == CSRF
    _run(chat.aclose())


def test_the_agent_client_reports_a_failed_turn() -> None:
    chat = _Platform(fail_query=True).chat()
    with pytest.raises(AgentChatError):
        _run(chat.ask("anything"))
    _run(chat.aclose())


# --- the LLM adapter ----------------------------------------------------------------------------


def _collect(llm: AgenticOrgChat, ctx: ChatContext) -> str:
    async def drain() -> str:
        return "".join([chunk.delta.content or "" async for chunk in llm.chat(chat_ctx=ctx) if chunk.delta])

    return _run(drain())


def test_the_llm_adapter_streams_the_agents_answer_to_the_pipeline() -> None:
    platform = _Platform(answer="Four people, 300 each. Shall I go ahead?")
    llm = AgenticOrgChat(client=platform.chat())

    ctx = ChatContext()
    ctx.add_message(role="user", content="tennis saturday for four, 300 each")

    assert _collect(llm, ctx) == "Four people, 300 each. Shall I go ahead?"
    # Only the newest utterance is sent: AgenticOrg owns the dialogue state, not this adapter.
    assert platform.queries[0]["body"]["query"] == "tennis saturday for four, 300 each"
    _run(llm.aclose())


def test_the_llm_adapter_says_so_when_the_agent_is_unreachable() -> None:
    llm = AgenticOrgChat(client=_Platform(fail_query=True).chat())
    ctx = ChatContext()
    ctx.add_message(role="user", content="hello")

    assert "could not reach the booking agent" in _collect(llm, ctx)
    _run(llm.aclose())


def test_the_llm_adapter_sends_nothing_for_an_empty_user_turn() -> None:
    platform = _Platform()
    llm = AgenticOrgChat(client=platform.chat())

    assert _collect(llm, ChatContext()) == ""
    assert platform.queries == []
    _run(llm.aclose())


def test_build_llm_returns_an_llm_the_pipeline_can_use() -> None:
    llm = build_llm(
        base_url="https://agenticorg.example",
        email="a@b.c",
        password="p",
        agent_id="agent-1",
        timeout_s=5.0,
    )
    assert isinstance(llm, AgenticOrgChat)
    assert isinstance(llm, LLM)
    assert llm.provider == "agenticorg"
    assert llm.model == "agenticorg"
    _run(llm.aclose())


# --- the pipeline -------------------------------------------------------------------------------


def test_the_session_wires_gnani_speech_around_the_agent() -> None:
    """Gnani in, the AgenticOrg agent in the middle, Gnani out."""
    gnani = pytest.importorskip("livekit.plugins.gnani")

    from voice_bridge.agent import build_session

    async def build() -> tuple[bool, bool, bool, int]:
        session = build_session(_config())
        result = (
            isinstance(session.stt, gnani.STT),
            isinstance(session.tts, gnani.TTS),
            isinstance(session.llm, AgenticOrgChat),
            session.tts.sample_rate,
        )
        closer = getattr(session, "aclose", None)
        if closer is not None:
            await closer()
        return result

    # AgentSession binds to the running loop, so it has to be constructed inside one.
    stt_ok, tts_ok, llm_ok, sample_rate = _run(build())
    assert stt_ok and tts_ok and llm_ok
    assert sample_rate == 16000
