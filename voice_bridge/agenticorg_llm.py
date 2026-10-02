"""The model behind the voice: AgenticOrg's "Kirro Declare" agent (ADR-016).

LiveKit's pipeline expects an `llm.LLM` between speech-to-text and text-to-speech. KIRRO has no
separate model — the agent runs on AgenticOrg, decides everything, and calls its own connectors.
This adapter makes that agent *look* like an LLM to the pipeline: it takes the newest user turn from
the LiveKit chat context, posts it to AgenticOrg's chat API, and streams the agent's answer back as
a single chunk.

What it deliberately does not do: keep its own copy of the conversation. AgenticOrg owns the dialogue
state, and it does that by *thread* — so this adapter sends the newest user turn plus the `thread_id`
the agent's last reply returned. A turn sent without that id starts a brand-new conversation, which is
what it looked like when the agent asked for the same field over and over: it had genuinely never
heard the previous sentence. The local transcript LiveKit keeps is for captions, not a second source
of truth.
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from livekit.agents.llm import (
    LLM,
    ChatChunk,
    ChatContext,
    ChoiceDelta,
    LLMStream,
    Tool,
    ToolChoice,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import shortuuid

from voice_bridge.agenticorg import AgentChat, AgentChatError

log = logging.getLogger("voice_bridge.llm")


def latest_user_text(chat_ctx: ChatContext) -> str:
    """The most recent user utterance as plain text."""
    for message in reversed(chat_ctx.messages()):
        if message.role != "user":
            continue
        parts: list[str] = []
        for content in message.content:
            if isinstance(content, str):
                parts.append(content)
            else:
                text = getattr(content, "text", None)
                if text:
                    parts.append(str(text))
        combined = " ".join(part.strip() for part in parts if part).strip()
        if combined:
            return combined
    return ""


class AgenticOrgStream(LLMStream):
    """One turn: post the caller's utterance, stream the agent's answer."""

    async def _run(self) -> None:
        text = latest_user_text(self._chat_ctx)
        if not text:
            return
        chat = self._llm
        assert isinstance(chat, AgenticOrgChat)
        try:
            answer = await chat.ask(text)
        except AgentChatError as exc:
            log.warning("agent turn failed: %s", exc)
            answer = "Sorry, I could not reach the booking agent just now. Please try again."
        if not answer:
            answer = "Sorry, I did not catch that. Could you say that again?"
        self._event_ch.send_nowait(
            ChatChunk(
                id=shortuuid("chatcmpl_"),
                delta=ChoiceDelta(role="assistant", content=answer),
            )
        )


class AgenticOrgChat(LLM):
    """An `llm.LLM` whose completions come from the AgenticOrg agent."""

    def __init__(self, *, client: AgentChat) -> None:
        super().__init__()
        self._client = client

    @property
    def model(self) -> str:
        return "agenticorg"

    @property
    def provider(self) -> str:
        return "agenticorg"

    @property
    def _stream_cls(self) -> type[LLMStream]:
        return AgenticOrgStream

    async def ask(self, text: str) -> str:
        return await self._client.ask(text)

    async def aclose(self) -> None:
        await self._client.aclose()

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> LLMStream:
        return AgenticOrgStream(
            llm=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )


def build_llm(*, base_url: str, email: str, password: str, agent_id: str, timeout_s: float) -> AgenticOrgChat:
    """Wire an `AgenticOrgChat` to a fresh HTTP client."""
    return AgenticOrgChat(
        client=AgentChat(
            base_url=base_url,
            email=email,
            password=password,
            agent_id=agent_id,
            timeout_s=timeout_s,
        )
    )


__all__ = ["AgenticOrgChat", "AgenticOrgStream", "build_llm", "latest_user_text"]
