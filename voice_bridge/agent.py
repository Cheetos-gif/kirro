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

import logging
import time
from typing import Callable

from livekit.agents import (
    Agent,
    AgentSession,
    CloseEvent,
    ErrorEvent,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.utils import shortuuid
from livekit.plugins import silero
from livekit.plugins.gnani import STT as GnaniSTT
from livekit.plugins.gnani import TTS as GnaniTTS

from logging_.redact import redact_text
from voice_bridge.agenticorg import AgentChatError
from voice_bridge.agenticorg_llm import AgenticOrgChat, build_llm
from voice_bridge.config import VoiceConfig
from voice_bridge.conversation_log import CallLogger, ConversationLogHandler

log = logging.getLogger("voice_bridge.agent")

# The topic the worker sends its own call id on, for the portal to display. A text stream, like
# LiveKit's own `lk.transcription`, so the browser reads it with the same mechanism.
CALL_ID_TOPIC = "kirro.call_id"

# The agent decides everything and its own prompt lives on AgenticOrg; these instructions only stop
# the pipeline's LLM stage from inventing a persona of its own between STT and the agent's answer.
INSTRUCTIONS = (
    "You are a relay. Answer strictly with what the booking agent returns; never add advice, "
    "never invent availability, prices, or confirmation."
)

# Sent once, before the caller has said anything, so the real AgenticOrg agent's own opening line
# plays immediately. A caller who doesn't know to speak first sits in silence, and Gnani's streaming
# STT hard-closes its session after 60s with no detected speech (vendor behaviour, not configurable
# here) — greeting first means no call ever reaches that idle clock before the caller's first turn.
GREETING_OPENER = "Hi"


def build_session(config: VoiceConfig, call_id: str | None = None) -> AgentSession:
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


async def greet_caller(
    llm: AgenticOrgChat, say: Callable[[str], object], call_log: logging.LoggerAdapter | None = None
) -> None:
    """Speak the real AgenticOrg agent's own opening line before the caller says anything.

    `say` is `AgentSession.say`, taken as a callable rather than the session itself so this can be
    tested without building a real voice pipeline.
    """
    logger = call_log or log
    try:
        greeting = await llm.ask(GREETING_OPENER)
    except AgentChatError as exc:
        logger.warning("greeting turn failed, starting silent: %s", exc)
        greeting = ""
    if greeting:
        logger.info("spoke opening greeting: %s", redact_text(greeting))
        say(greeting)
    else:
        logger.warning("no greeting to speak, call starts silent")


def on_pipeline_error(call_log: logging.LoggerAdapter) -> Callable[[ErrorEvent], None]:
    """Every STT/LLM/TTS failure the pipeline sees, in one line instead of a vendored traceback.

    This is what would have made the Gnani TTS outage (`docs/testing.md`, "We are facing technical
    difficulties") immediately visible as a single clear line instead of something only found by
    reading through `_tts_inference_task` tracebacks after the fact.
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


async def entrypoint(ctx: JobContext) -> None:
    config = VoiceConfig.from_env()
    await ctx.connect()
    # One id per call, minted here rather than reused from the room name: the portal keeps one room
    # per viewer, so the same room is every call that viewer makes. Everything logged for this call
    # carries it, and `ConversationLogHandler` files those lines under `<log_dir>/<call_id>.jsonl`.
    call_id = shortuuid("call_")
    call_log = CallLogger(log, {"call_id": call_id})
    started_at = time.monotonic()
    # Built per job, so each call gets its own AgenticOrg conversation. Sharing one would leak the
    # previous caller's declaration into the next one.
    session = build_session(config, call_id=call_id)
    session.on("error", on_pipeline_error(call_log))
    session.on("close", on_session_close(call_log, started_at, ctx.room.name))
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

    llm = session.llm
    assert isinstance(llm, AgenticOrgChat)
    await greet_caller(llm, session.say, call_log)


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
