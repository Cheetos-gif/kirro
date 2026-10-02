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
from typing import Callable

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero
from livekit.plugins.gnani import STT as GnaniSTT
from livekit.plugins.gnani import TTS as GnaniTTS

from voice_bridge.agenticorg import AgentChatError
from voice_bridge.agenticorg_llm import AgenticOrgChat, build_llm
from voice_bridge.config import VoiceConfig

log = logging.getLogger("voice_bridge.agent")

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


def build_session(config: VoiceConfig) -> AgentSession:
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


async def greet_caller(llm: AgenticOrgChat, say: Callable[[str], object]) -> None:
    """Speak the real AgenticOrg agent's own opening line before the caller says anything.

    `say` is `AgentSession.say`, taken as a callable rather than the session itself so this can be
    tested without building a real voice pipeline.
    """
    try:
        greeting = await llm.ask(GREETING_OPENER)
    except AgentChatError as exc:
        log.warning("greeting turn failed, starting silent: %s", exc)
        greeting = ""
    if greeting:
        say(greeting)


async def entrypoint(ctx: JobContext) -> None:
    config = VoiceConfig.from_env()
    await ctx.connect()
    # Built per job, so each call gets its own AgenticOrg conversation. Sharing one would leak the
    # previous caller's declaration into the next one.
    session = build_session(config)
    await session.start(
        agent=Agent(instructions=INSTRUCTIONS),
        room=ctx.room,
    )
    log.info("voice session started in room %s", ctx.room.name)

    llm = session.llm
    assert isinstance(llm, AgenticOrgChat)
    await greet_caller(llm, session.say)


def main() -> None:
    config = VoiceConfig.from_env()
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
