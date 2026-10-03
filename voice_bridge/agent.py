"""The voice bridge: a LiveKit agent worker (ADR-016, ADR-017).

Run it as a worker:

    python -m voice_bridge.agent dev      # against a local livekit-server
    python -m voice_bridge.agent start    # production

The browser publishes its microphone into a LiveKit room; this worker joins that room and runs the
standard LiveKit voice pipeline with Gnani as the speech side and the AgenticOrg agent as the model.
It owns no state and makes no decisions: the transcript LiveKit keeps is for captions, and every
booking decision stays with the agent on AgenticOrg (ADR-011).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    CloseEvent,
    ErrorEvent,
    JobContext,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
    WorkerOptions,
    cli,
)
from livekit.agents.utils import shortuuid
from livekit.agents.voice.events import OverlappingSpeechEvent
from livekit.plugins import silero
from livekit.plugins.gnani import STT as GnaniSTT
from livekit.plugins.gnani import TTS as GnaniTTS

from logging_.redact import redact_text
from voice_bridge.agenticorg_llm import build_llm
from voice_bridge.config import VoiceConfig
from voice_bridge.conversation_log import CallLogger, ConversationLogHandler

log = logging.getLogger("voice_bridge.agent")

# The topic the worker sends its own call id on, for the portal to display. A text stream, like
# LiveKit's own `lk.transcription`, so the browser reads it with the same mechanism.
CALL_ID_TOPIC = "kirro.call_id"

# The portal's "the agent's voice just died / just came back" banner, on the same text-stream
# mechanism. A Gnani TTS failure that exhausts its retries is unrecoverable, so the agent's answer
# reaches the transcript while the caller hears silence (docs/testing.md, "We are facing technical
# difficulties"); the worker cannot speak it, so it tells the portal to. `ERROR` carries
# `{call_id, stage, label, message}`, `OK` carries `{call_id}`.
VOICE_ERROR_TOPIC = "kirro.voice_error"
VOICE_OK_TOPIC = "kirro.voice_ok"

# The agent decides everything and its own prompt lives on AgenticOrg; these instructions only stop
# the pipeline's LLM stage from inventing a persona of its own between STT and the agent's answer.
INSTRUCTIONS = (
    "You are a relay. Answer strictly with what the booking agent returns; never add advice, "
    "never invent availability, prices, or confirmation."
)

# Spoken once, before the caller has said anything, so a caller who doesn't know to speak first never sits in
# silence: Gnani's streaming STT hard-closes its session after 60s with no detected speech (vendor behaviour, not
# configurable here), and speaking first means no call ever reaches that idle clock before the caller's first turn.
# Fixed text, spoken directly through TTS with no AgenticOrg call (2026-10-03): the earlier version sent a
# synthetic "Hi" to the agent as if the caller had said it, which both cost one scored turn per call on whichever
# agent is live (`docs/agenticorg/declare-v6-notes.md` §1) and put a line in the agent's own conversation thread
# that the caller never actually spoke.
GREETING_TEXT = (
    "Hi, I'm Kirro. Tell me what you'd like to book: the event, the date, how many people, and the "
    "most you'll pay per person."
)


def build_session(config: VoiceConfig, call_id: str | None = None, caller: str | None = None) -> AgentSession:
    """The voice pipeline: Gnani in, the AgenticOrg agent in the middle, Gnani out."""
    config.export_plugin_env()
    return AgentSession(
        # End-of-turn detection runs locally (the model ships inside the plugin), so the agent
        # needs no LiveKit Cloud account and no network beyond Gnani and AgenticOrg.
        vad=silero.VAD.load(),
        stt=GnaniSTT(
            language=config.language,
            api_key=config.gnani_api_key,
            # Gnani's own VAD closes a turn, so no separate local VAD plugin is needed.
            use_streaming=True,
        ),
        llm=build_llm(
            base_url=config.agenticorg_base_url,
            email=config.agenticorg_email,
            password=config.agenticorg_password,
            agent_id=config.agent_id,
            timeout_s=config.request_timeout_s,
            call_id=call_id,
            caller=caller,
        ),
        tts=GnaniTTS(
            voice=config.voice,
            model=config.tts_model,
            language=config.language,
            api_key=config.gnani_api_key,
            sample_rate=16000,
            container="raw",
            # Lowest latency transport for a live conversation.
            synthesize_method="websocket",
        ),
    )


def greet_caller(say: Callable[[str], object], call_log: logging.LoggerAdapter | None = None) -> None:
    """Speak a fixed opening line before the caller says anything, with no AgenticOrg call.

    `say` is `AgentSession.say`, taken as a callable rather than the session itself so this can be
    tested without building a real voice pipeline. Synchronous and cannot fail into silence the way the
    old agent-authored greeting could if AgenticOrg was unreachable (`docs/testing.md`, 2026-10-02).
    """
    logger = call_log or log
    logger.info("spoke opening greeting: %s", redact_text(GREETING_TEXT))
    say(GREETING_TEXT)


def room_publisher(room: rtc.Room, call_log: logging.LoggerAdapter) -> Callable[[str, str], None]:
    """Best-effort text-stream publisher around the room, safe to call from a sync event handler.

    LiveKit's session handlers run synchronously while `send_text` is a coroutine, so this schedules
    the send on the running loop instead of returning one. Every failure is swallowed to a warning:
    a telemetry publish must never break the call it is reporting on.
    """

    def publish(topic: str, payload: str) -> None:
        async def _send() -> None:
            try:
                await room.local_participant.send_text(payload, topic=topic)
            except Exception as exc:  # noqa: BLE001 - telemetry must never break a call
                call_log.warning("could not publish %s: %s", topic, exc)

        try:
            asyncio.get_running_loop().create_task(_send())
        except RuntimeError as exc:
            # No running loop (handler called outside a job): nothing to schedule the send on.
            call_log.warning("could not publish %s: %s", topic, exc)

    return publish


def _publish_voice_event(
    call_log: logging.LoggerAdapter,
    publish: Callable[[str, str], None] | None,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Send one JSON telemetry line on `topic`, never letting a failure escape into the pipeline."""
    if publish is None:
        return
    try:
        publish(topic, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 - telemetry must never break a call
        call_log.warning("could not publish %s: %s", topic, exc)


def on_pipeline_error(
    call_log: logging.LoggerAdapter,
    publish: Callable[[str, str], None] | None = None,
) -> Callable[[ErrorEvent], None]:
    """Every STT/LLM/TTS failure the pipeline sees, in one line instead of a vendored traceback.

    This is what would have made the Gnani TTS outage (`docs/testing.md`, "We are facing technical
    difficulties") immediately visible as a single clear line instead of something only found by
    reading through `_tts_inference_task` tracebacks after the fact.

    An unrecoverable TTS failure also publishes `kirro.voice_error` so the portal can tell the caller
    their agent has gone silent. Recoverable ones do not: those are retries that usually succeed, and
    a banner on every retry would be worse than no banner at all.
    """

    def handler(event: ErrorEvent) -> None:
        error = event.error
        call_log.error(
            "pipeline error",
            extra={
                "stage": error.type,
                "label": error.label,
                "recoverable": error.recoverable,
                "error": repr(error.error),
            },
        )
        if error.type == "tts_error" and error.recoverable is False:
            _publish_voice_event(
                call_log,
                publish,
                VOICE_ERROR_TOPIC,
                {
                    "call_id": (call_log.extra or {}).get("call_id"),
                    "stage": error.type,
                    "label": error.label,
                    "message": str(error.error),
                },
            )

    return handler


def on_metrics_collected(
    call_log: logging.LoggerAdapter,
    publish: Callable[[str, str], None] | None = None,
) -> Callable[[MetricsCollectedEvent], None]:
    """Clear the portal's voice-error banner once Gnani actually synthesizes audio again.

    A `tts_metrics` event with `characters_count > 0` is a completed synthesis. `cancelled` is
    deliberately not checked: audio was produced even when the agent was interrupted, which is
    exactly the evidence that TTS works — that synthesis is what clears the banner.
    """

    def handler(event: MetricsCollectedEvent) -> None:
        metrics = event.metrics
        if getattr(metrics, "type", None) == "tts_metrics" and (getattr(metrics, "characters_count", 0) or 0) > 0:
            call_log.debug("tts recovered, voice ok")
            _publish_voice_event(
                call_log,
                publish,
                VOICE_OK_TOPIC,
                {"call_id": (call_log.extra or {}).get("call_id")},
            )

    return handler


def on_session_close(
    call_log: logging.LoggerAdapter, started_at: float, room_name: str
) -> Callable[[CloseEvent], None]:
    def handler(event: CloseEvent) -> None:
        call_log.info(
            "voice session ended",
            extra={
                "room": room_name,
                "reason": event.reason.value,
                "duration_s": round(time.monotonic() - started_at, 1),
                "error": repr(event.error) if event.error else None,
            },
        )

    return handler


def on_user_input_transcribed(
    call_log: logging.LoggerAdapter,
) -> Callable[[UserInputTranscribedEvent], None]:
    """Every transcript the STT hands the pipeline, and whether it closed a turn.

    This is the line that makes a swallowed utterance visible: a final transcript with no
    `agenticorg turn` after it means the caller was heard and the turn never reached the LLM stage.
    Gnani's plugin emits only `FINAL_TRANSCRIPT` events, so `is_final` is normally true here.
    """

    def handler(event: UserInputTranscribedEvent) -> None:
        call_log.info(
            "user input transcribed",
            extra={
                "is_final": event.is_final,
                "transcript": redact_text(event.transcript),
                "item_id": event.item_id,
                "language": event.language,
            },
        )

    return handler


def on_agent_false_interruption(
    call_log: logging.LoggerAdapter,
) -> Callable[[AgentFalseInterruptionEvent], None]:
    """A barge-in LiveKit decided was not a real interruption and dropped instead of turning.

    The main hypothesis for a short utterance that got transcribed but never became a turn: VAD saw
    speech, the agent paused, no turn committed inside `false_interruption_timeout`, so the speech
    was discarded and the agent resumed. If this fires for the dropped turns, it is the cause.
    """

    def handler(event: AgentFalseInterruptionEvent) -> None:
        call_log.warning("agent false interruption", extra={"resumed": event.resumed})

    return handler


def on_user_state_changed(
    call_log: logging.LoggerAdapter,
) -> Callable[[UserStateChangedEvent], None]:
    """The caller's own speaking state, so a `speaking` that never becomes a turn stays visible."""

    def handler(event: UserStateChangedEvent) -> None:
        call_log.info(
            "user state changed",
            extra={"old_state": event.old_state, "new_state": event.new_state},
        )

    return handler


def on_overlapping_speech(
    call_log: logging.LoggerAdapter,
) -> Callable[[OverlappingSpeechEvent], None]:
    """Caller speech that overlapped the agent's, and whether the detector called it an interruption."""

    def handler(event: OverlappingSpeechEvent) -> None:
        call_log.info(
            "overlapping speech",
            extra={
                "is_interruption": event.is_interruption,
                "agent_ended": event.agent_ended,
                "detection_delay": round(event.detection_delay, 3),
            },
        )

    return handler


async def entrypoint(ctx: JobContext) -> None:
    config = VoiceConfig.from_env()
    await ctx.connect()
    # One id per call, minted here rather than reused from the room name: the portal keeps one room
    # per viewer, so the same room is every call that viewer makes. Everything logged for this call
    # carries it, and `ConversationLogHandler` files those lines under `<log_dir>/<call_id>.jsonl`.
    call_id = shortuuid("call_")
    call_log = CallLogger(log, {"call_id": call_id})
    started_at = time.monotonic()
    # The portal mints the caller's token with the signed-in email as its identity (app/api/voice/token),
    # which is the only authenticated identity in the call. The agent needs it to resolve account
    # details — the WhatsApp number above all — rather than asking the caller to recite them.
    caller = next(iter(ctx.room.remote_participants.values()), None)
    caller_id = caller.identity if caller else None
    call_log.info("caller identified", extra={"caller": caller_id, "room": ctx.room.name})
    # Built per job, so each call gets its own AgenticOrg conversation. Sharing one would leak the
    # previous caller's declaration into the next one.
    session = build_session(config, call_id=call_id, caller=caller_id)
    publish = room_publisher(ctx.room, call_log)
    session.on("error", on_pipeline_error(call_log, publish))
    session.on("close", on_session_close(call_log, started_at, ctx.room.name))
    session.on("metrics_collected", on_metrics_collected(call_log, publish))
    # Turn-level observation: a final transcript with no `agenticorg turn` after it, or an
    # `agent false interruption`, is how a swallowed utterance becomes visible instead of silent.
    session.on("user_input_transcribed", on_user_input_transcribed(call_log))
    session.on("agent_false_interruption", on_agent_false_interruption(call_log))
    session.on("user_state_changed", on_user_state_changed(call_log))
    session.on("overlapping_speech", on_overlapping_speech(call_log))
    await session.start(
        agent=Agent(instructions=INSTRUCTIONS),
        room=ctx.room,
    )
    call_log.info("voice session started", extra={"room": ctx.room.name})

    # Tell the portal which call this is, so the id it shows is the one the logs are filed under.
    try:
        await ctx.room.local_participant.send_text(call_id, topic=CALL_ID_TOPIC)
    except Exception as exc:  # noqa: BLE001 - a missing badge must never break the call itself
        call_log.warning("could not publish the call id to the room: %s", exc)

    greet_caller(session.say, call_log)


def main() -> None:
    config = VoiceConfig.from_env()
    # Every call writes its own file beside the pod's stdout log, so a conversation can be pulled up
    # by id after `kubectl logs` has rolled the line away (the directory is a PVC in k8s/pvc.yaml).
    logging.getLogger("voice_bridge").addHandler(ConversationLogHandler(config.log_dir))
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=config.livekit_url,
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret,
            # Health endpoint for the container probe.
            host="0.0.0.0",
            port=config.health_port,
        )
    )


if __name__ == "__main__":
    main()
