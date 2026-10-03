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
        log_dir="/tmp/kirro-voice-test-logs",
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


def test_greet_caller_speaks_the_fixed_opening_line_with_no_agenticorg_call() -> None:
    """The greeting is spoken immediately and costs no scored turn on whichever agent is live
    (docs/agenticorg/declare-v6-notes.md section 1) — no HTTP call happens at all."""
    from voice_bridge.agent import GREETING_TEXT, greet_caller

    spoken: list[str] = []

    greet_caller(spoken.append)

    assert spoken == [GREETING_TEXT]


def test_greet_caller_logs_what_it_spoke(caplog: pytest.LogCaptureFixture) -> None:
    """The greeting is the one line spoken before any caller turn exists to log on its own."""
    import logging

    from voice_bridge.agent import GREETING_TEXT, greet_caller

    with caplog.at_level(logging.INFO, logger="voice_bridge.agent"):
        greet_caller(lambda _: None)

    assert any(GREETING_TEXT in r.message for r in caplog.records)


def test_pipeline_error_is_logged_as_one_structured_line(caplog: pytest.LogCaptureFixture) -> None:
    """A TTS/STT/LLM failure must be findable as one clear line, not only inside a vendored
    traceback — this is what would have made the Gnani TTS outage immediately visible."""
    import logging as logging_module

    from livekit.agents import ErrorEvent
    from livekit.agents.tts import TTSError

    from voice_bridge.agent import on_pipeline_error
    from voice_bridge.conversation_log import CallLogger

    error = TTSError(
        timestamp=0.0,
        label="gnani-tts",
        error=RuntimeError("We are facing technical difficulties. Please try again later."),
        recoverable=False,
    )
    event = ErrorEvent(error=error, source=error)

    with caplog.at_level(logging_module.ERROR, logger="voice_bridge.agent"):
        on_pipeline_error(CallLogger(logging_module.getLogger("voice_bridge.agent"), {"call_id": "call_x"}))(event)

    record = next(r for r in caplog.records if r.message == "pipeline error")
    assert record.stage == "tts_error"
    assert record.label == "gnani-tts"
    assert record.recoverable is False
    assert record.call_id == "call_x"


def test_session_close_is_logged_with_reason_and_duration(caplog: pytest.LogCaptureFixture) -> None:
    import logging as logging_module
    import time

    from livekit.agents import CloseEvent, CloseReason

    from voice_bridge.agent import on_session_close
    from voice_bridge.conversation_log import CallLogger

    started_at = time.monotonic() - 5
    handler = on_session_close(
        CallLogger(logging_module.getLogger("voice_bridge.agent"), {"call_id": "call_x"}),
        started_at,
        "kirro-upayanm3-gmail-com",
    )

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agent"):
        handler(CloseEvent(reason=CloseReason.PARTICIPANT_DISCONNECTED))

    record = next(r for r in caplog.records if r.message == "voice session ended")
    assert record.room == "kirro-upayanm3-gmail-com"
    assert record.reason == "participant_disconnected"
    assert record.duration_s >= 5
    assert record.error is None
    assert record.call_id == "call_x"


# --- swallowed turns and the portal's voice banner ------------------------------------------------


def _call_log() -> Any:
    import logging as logging_module

    from voice_bridge.conversation_log import CallLogger

    return CallLogger(logging_module.getLogger("voice_bridge.agent"), {"call_id": "call_x"})


def test_user_input_transcribed_is_logged_with_finality_and_call_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A final transcript is the proof the caller was heard, even when no turn follows it."""
    import logging as logging_module

    from livekit.agents import UserInputTranscribedEvent

    from voice_bridge.agent import on_user_input_transcribed

    event = UserInputTranscribedEvent(transcript="nahi", is_final=True, item_id="item_1")

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agent"):
        on_user_input_transcribed(_call_log())(event)

    record = next(r for r in caplog.records if r.message == "user input transcribed")
    assert record.is_final is True
    assert record.transcript == "nahi"
    assert record.item_id == "item_1"
    assert record.call_id == "call_x"


def test_agent_false_interruption_is_logged_with_call_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A discarded barge-in must be visible as a warning, not silently swallowed."""
    import logging as logging_module

    from livekit.agents import AgentFalseInterruptionEvent

    from voice_bridge.agent import on_agent_false_interruption

    event = AgentFalseInterruptionEvent(resumed=True)

    with caplog.at_level(logging_module.WARNING, logger="voice_bridge.agent"):
        on_agent_false_interruption(_call_log())(event)

    record = next(r for r in caplog.records if r.message == "agent false interruption")
    assert record.resumed is True
    assert record.call_id == "call_x"


def test_user_state_changed_is_logged_with_call_id(caplog: pytest.LogCaptureFixture) -> None:
    """The caller's speaking state is what shows a `speaking` that never became a turn."""
    import logging as logging_module

    from livekit.agents import UserStateChangedEvent

    from voice_bridge.agent import on_user_state_changed

    event = UserStateChangedEvent(old_state="listening", new_state="speaking")

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agent"):
        on_user_state_changed(_call_log())(event)

    record = next(r for r in caplog.records if r.message == "user state changed")
    assert record.old_state == "listening"
    assert record.new_state == "speaking"
    assert record.call_id == "call_x"


def test_overlapping_speech_is_logged_with_call_id(caplog: pytest.LogCaptureFixture) -> None:
    """Overlap is where a short barge-in gets classified; the verdict must land on the record."""
    import logging as logging_module

    from livekit.agents.voice.events import OverlappingSpeechEvent

    from voice_bridge.agent import on_overlapping_speech

    event = OverlappingSpeechEvent(is_interruption=True, agent_ended=False, detection_delay=0.42)

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agent"):
        on_overlapping_speech(_call_log())(event)

    record = next(r for r in caplog.records if r.message == "overlapping speech")
    assert record.is_interruption is True
    assert record.agent_ended is False
    assert record.detection_delay == 0.42
    assert record.call_id == "call_x"


def test_unrecoverable_tts_error_publishes_the_voice_error_banner() -> None:
    """An unrecoverable TTS failure is when the caller hears silence, so the portal is told."""
    import logging as logging_module

    from livekit.agents import ErrorEvent
    from livekit.agents.tts import TTSError

    from voice_bridge.agent import VOICE_ERROR_TOPIC, on_pipeline_error

    sent: list[tuple[str, str]] = []
    error = TTSError(
        timestamp=0.0,
        label="gnani-tts",
        error=RuntimeError("We are facing technical difficulties. Please try again later."),
        recoverable=False,
    )
    handler = on_pipeline_error(_call_log(), lambda topic, payload: sent.append((topic, payload)))
    # silence the error line the handler also writes
    logging_module.getLogger("voice_bridge.agent").setLevel(logging_module.CRITICAL)
    try:
        handler(ErrorEvent(error=error, source=error))
    finally:
        logging_module.getLogger("voice_bridge.agent").setLevel(logging_module.NOTSET)

    assert [topic for topic, _ in sent] == [VOICE_ERROR_TOPIC]
    assert json.loads(sent[0][1]) == {
        "call_id": "call_x",
        "stage": "tts_error",
        "label": "gnani-tts",
        "message": "We are facing technical difficulties. Please try again later.",
    }


def test_recoverable_tts_error_and_other_stages_publish_nothing() -> None:
    """Retries usually succeed and an STT error is not a voice outage — no banner either way."""
    import logging as logging_module

    from livekit.agents import ErrorEvent
    from livekit.agents.stt import STTError
    from livekit.agents.tts import TTSError

    from voice_bridge.agent import on_pipeline_error

    sent: list[tuple[str, str]] = []
    handler = on_pipeline_error(_call_log(), lambda topic, payload: sent.append((topic, payload)))

    logging_module.getLogger("voice_bridge.agent").setLevel(logging_module.CRITICAL)
    try:
        retry = TTSError(timestamp=0.0, label="gnani-tts", error=RuntimeError("retrying"), recoverable=True)
        handler(ErrorEvent(error=retry, source=retry))
        stt = STTError(timestamp=0.0, label="gnani-stt", error=RuntimeError("boom"), recoverable=False)
        handler(ErrorEvent(error=stt, source=stt))
    finally:
        logging_module.getLogger("voice_bridge.agent").setLevel(logging_module.NOTSET)

    assert sent == []


def test_completed_tts_synthesis_publishes_voice_ok() -> None:
    """A synthesis that produced characters means TTS works again, even if it was interrupted."""

    from livekit.agents import MetricsCollectedEvent
    from livekit.agents.metrics import TTSMetrics

    from voice_bridge.agent import VOICE_OK_TOPIC, on_metrics_collected

    sent: list[tuple[str, str]] = []
    handler = on_metrics_collected(
        _call_log(),
        lambda topic, payload: sent.append((topic, payload)),
    )
    metrics = TTSMetrics(
        label="gnani-tts",
        request_id="r1",
        timestamp=0.0,
        ttfb=0.1,
        duration=0.2,
        audio_duration=0.5,
        cancelled=True,
        characters_count=12,
        streamed=True,
    )

    handler(MetricsCollectedEvent(metrics=metrics))

    assert len(sent) == 1 and sent[0][0] == VOICE_OK_TOPIC
    assert json.loads(sent[0][1]) == {"call_id": "call_x"}


def test_other_metrics_and_empty_synthesis_publish_nothing() -> None:
    """A VAD metric, or a TTS synthesis with no characters, is not evidence the voice works."""

    from livekit.agents import MetricsCollectedEvent
    from livekit.agents.metrics import TTSMetrics, VADMetrics

    from voice_bridge.agent import on_metrics_collected

    sent: list[tuple[str, str]] = []
    handler = on_metrics_collected(
        _call_log(),
        lambda topic, payload: sent.append((topic, payload)),
    )
    vad = VADMetrics(
        label="silero",
        timestamp=0.0,
        idle_time=1.0,
        inference_duration_total=0.01,
        inference_count=3,
    )
    empty_tts = TTSMetrics(
        label="gnani-tts",
        request_id="r2",
        timestamp=0.0,
        ttfb=0.1,
        duration=0.2,
        audio_duration=0.0,
        cancelled=False,
        characters_count=0,
        streamed=True,
    )

    handler(MetricsCollectedEvent(metrics=vad))
    handler(MetricsCollectedEvent(metrics=empty_tts))

    assert sent == []


def test_room_publisher_sends_over_the_text_stream_and_swallows_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The handler is sync and `send_text` is a coroutine, so the send must be scheduled, and a
    broken data channel must cost a warning — never the call."""
    import logging as logging_module

    from voice_bridge.agent import room_publisher

    sent: list[tuple[str, str]] = []

    class _Participant:
        async def send_text(self, payload: str, topic: str | None = None) -> None:
            sent.append((topic or "", payload))

    class _Room:
        local_participant = _Participant()

    class _BrokenParticipant:
        async def send_text(self, payload: str, topic: str | None = None) -> None:
            raise RuntimeError("data channel closed")

    class _BrokenRoom:
        local_participant = _BrokenParticipant()

    async def run() -> None:
        room_publisher(_Room(), _call_log())("kirro.voice_ok", '{"call_id": "call_x"}')
        room_publisher(_BrokenRoom(), _call_log())("kirro.voice_ok", "{}")
        await asyncio.sleep(0.05)

    with caplog.at_level(logging_module.WARNING, logger="voice_bridge.agent"):
        _run(run())

    assert sent == [("kirro.voice_ok", '{"call_id": "call_x"}')]
    assert any("could not publish" in r.message for r in caplog.records)


# --- per-call conversation log -------------------------------------------------------------------


def test_conversation_log_writes_one_file_per_call(tmp_path: Any) -> None:
    """Each call's lines land in its own file, keyed by the call_id on the record."""
    import json
    import logging as logging_module

    from voice_bridge.conversation_log import ConversationLogHandler

    handler = ConversationLogHandler(tmp_path)
    logger = logging_module.getLogger("voice_bridge.test.conversation")
    logger.addHandler(handler)
    logger.setLevel(logging_module.INFO)
    try:
        logger.info("agenticorg turn", extra={"call_id": "call_a", "turn": 1, "query": "hi"})
        logger.info("agenticorg turn", extra={"call_id": "call_b", "turn": 1, "query": "hello"})
        logger.info("no call id, must be dropped")
    finally:
        logger.removeHandler(handler)

    entries_a = [json.loads(line) for line in (tmp_path / "call_a.jsonl").read_text().splitlines()]
    entries_b = [json.loads(line) for line in (tmp_path / "call_b.jsonl").read_text().splitlines()]
    assert len(entries_a) == 1 and entries_a[0]["query"] == "hi"
    assert len(entries_b) == 1 and entries_b[0]["query"] == "hello"
    # the record without a call_id does not invent a file for itself
    assert sorted(p.name for p in tmp_path.iterdir()) == ["call_a.jsonl", "call_b.jsonl"]


def test_call_logger_merges_its_fields_with_the_call_sites(tmp_path: Any) -> None:
    """The stdlib adapter would drop `turn`; ours must keep both it and `call_id`."""
    import json
    import logging as logging_module

    from voice_bridge.conversation_log import CallLogger, ConversationLogHandler

    handler = ConversationLogHandler(tmp_path)
    logger = logging_module.getLogger("voice_bridge.test.merge")
    logger.addHandler(handler)
    logger.setLevel(logging_module.INFO)
    try:
        CallLogger(logger, {"call_id": "call_m"}).info("agenticorg turn", extra={"turn": 7, "latency_ms": 12})
    finally:
        logger.removeHandler(handler)

    entry = json.loads((tmp_path / "call_m.jsonl").read_text().splitlines()[0])
    assert entry["call_id"] == "call_m"
    assert entry["turn"] == 7
    assert entry["latency_ms"] == 12


def test_agent_chat_tags_every_turn_with_the_call_id(caplog: pytest.LogCaptureFixture) -> None:
    """A call's own turns are filed under its id, which is what makes a call findable later."""
    import logging as logging_module

    platform = _Platform(answer="Hello!")
    chat = AgentChat(
        base_url="https://agenticorg.example",
        email="bridge@example.com",
        password="secret",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://agenticorg.example", transport=httpx.MockTransport(platform.handler)
        ),
        call_id="call_z",
    )

    with caplog.at_level(logging_module.INFO, logger="voice_bridge.agenticorg"):
        reply = _run(chat.ask("hello"))

    assert reply == "Hello!"
    record = next(r for r in caplog.records if r.message == "agenticorg turn")
    assert record.call_id == "call_z"
    _run(chat.aclose())
