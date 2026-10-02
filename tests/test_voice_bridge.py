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
        # Each chat/query without a thread_id starts a new one, which is the platform's actual
        # behaviour and the reason a client that forgets to echo it loses all context.
        self.threads_created = 0

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
            body = json.loads(request.content)
            thread = body.get("thread_id")
            if not thread:
                self.threads_created += 1
                thread = f"chat:{self.threads_created:04d}"
            self.queries.append(
                {
                    "body": body,
                    "thread": thread,
                    "csrf_header": request.headers.get("x-csrf-token"),
                }
            )
            if self.fail_query:
                return httpx.Response(500, text="upstream boom")
            return httpx.Response(200, json={"answer": self.answer, "confidence": 0.8, "thread_id": thread})
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


def test_a_turn_continues_the_same_conversation() -> None:
    """Without this the agent forgets the previous sentence — every turn is a new thread."""
    platform = _Platform(answer="Which event or venue are you interested in?")
    chat = platform.chat()

    _run(chat.ask("I want a tennis court on Saturday"))
    _run(chat.ask("for four people"))

    first, second = platform.queries
    # The first turn opens the thread; the second must carry the thread the reply handed back.
    assert "thread_id" not in first["body"]
    assert second["body"]["thread_id"] == first["thread"]
    assert platform.threads_created == 1, "the second turn must not start a new conversation"
    assert chat.thread_id == first["thread"]
    _run(chat.aclose())


def test_a_new_call_starts_a_fresh_conversation() -> None:
    """One call is one thread: a new caller must not inherit the previous caller's declaration."""
    platform = _Platform()
    chat = platform.chat()

    _run(chat.ask("first caller"))
    chat.start_new_thread()
    assert chat.thread_id is None
    _run(chat.ask("second caller"))

    assert platform.threads_created == 2
    assert "thread_id" not in platform.queries[1]["body"]
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


def test_greet_caller_speaks_the_agents_own_opening_line() -> None:
    """The agent speaks first, and what it says is AgenticOrg's real reply, not invented text."""
    from voice_bridge.agent import GREETING_OPENER, greet_caller

    platform = _Platform(answer="Hello! What would you like to book today?")
    llm = AgenticOrgChat(client=platform.chat())
    spoken: list[str] = []

    _run(greet_caller(llm, spoken.append))

    assert spoken == ["Hello! What would you like to book today?"]
    assert platform.queries[0]["body"]["query"] == GREETING_OPENER
    # the greeting is turn one, so it must not carry a thread_id yet
    assert "thread_id" not in platform.queries[0]["body"]
    _run(llm.aclose())


def test_greet_caller_stays_silent_if_agenticorg_is_unreachable() -> None:
    """A failed greeting must not crash the call; the caller can still speak first instead."""
    from voice_bridge.agent import greet_caller

    platform = _Platform(fail_query=True)
    llm = AgenticOrgChat(client=platform.chat())
    spoken: list[str] = []

    _run(greet_caller(llm, spoken.append))

    assert spoken == []
    _run(llm.aclose())


def test_greet_caller_logs_what_it_spoke(caplog: pytest.LogCaptureFixture) -> None:
    """The greeting is the one line spoken before any caller turn exists to log on its own."""
    import logging

    from voice_bridge.agent import greet_caller

    platform = _Platform(answer="Hello! What would you like to book today?")
    llm = AgenticOrgChat(client=platform.chat())

    with caplog.at_level(logging.INFO, logger="voice_bridge.agent"):
        _run(greet_caller(llm, lambda _: None))

    assert any("Hello! What would you like to book today?" in r.message for r in caplog.records)
    _run(llm.aclose())


def test_pipeline_error_is_logged_as_one_structured_line(caplog: pytest.LogCaptureFixture) -> None:
    """A TTS/STT/LLM failure must be findable as one clear line, not only inside a vendored
    traceback — this is what would have made the Gnani TTS outage immediately visible."""
    import logging as logging_module

    from livekit.agents import ErrorEvent
    from livekit.agents.tts import TTSError

    from voice_bridge.agent import _on_pipeline_error

    error = TTSError(
        timestamp=0.0,
        label="gnani-tts",
        error=RuntimeError("We are facing technical difficulties. Please try again later."),
        recoverable=False,
    )
    event = ErrorEvent(error=error, source=error)

    with caplog.at_level(logging_module.ERROR, logger="voice_bridge.agent"):
        _on_pipeline_error(event)

    record = next(r for r in caplog.records if r.message == "pipeline error")
    assert record.stage == "tts_error"
    assert record.label == "gnani-tts"
    assert record.recoverable is False


def test_session_close_is_logged_with_reason_and_duration(caplog: pytest.LogCaptureFixture) -> None:
    import logging as logging_module
    import time

    from livekit.agents import CloseEvent, CloseReason

    from voice_bridge.agent import _on_session_close

    started_at = time.monotonic() - 5
    handler = _on_session_close(started_at, "kirro-upayanm3-gmail-com")

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agent"):
        handler(CloseEvent(reason=CloseReason.PARTICIPANT_DISCONNECTED))

    record = next(r for r in caplog.records if r.message == "voice session ended")
    assert record.room == "kirro-upayanm3-gmail-com"
    assert record.reason == "participant_disconnected"
    assert record.duration_s >= 5
    assert record.error is None
