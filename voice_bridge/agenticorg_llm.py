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

One thing it does track across turns: the text it last sent. LiveKit can re-invoke the pipeline for
what is logically still the same utterance — once with the same words (an exact repeat) and again with
more words appended as the caller keeps talking (a growing transcript) — before the caller is actually
done. Each of those used to go to AgenticOrg as its own scored turn, producing a repeated read-back
("solah ek" -> "solah ek ek din" -> ...). `AgenticOrgChat.next_turn_text` collapses that: an exact
repeat is skipped, a growing transcript sends only the new suffix, and anything else is sent whole.
Every skip is logged.
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
from voice_bridge.conversation_log import CallLogger

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
        to_send = chat.next_turn_text(text)
        if to_send is None:
            # An exact repeat, or a growing transcript with no new suffix yet: already answered,
            # or nothing new to tell the agent. `next_turn_text` has already logged why.
            return
        try:
            answer = await chat.ask(chat.with_caller(to_send))
        except AgentChatError as exc:
            # The call's own logger, so a failed turn lands in that call's file too: this is the
            # line that says "the caller heard the fallback", and it has to sit beside the turns.
            chat.call_log.warning("agent turn failed: %s", exc)
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

    def __init__(self, *, client: AgentChat, call_id: str | None = None, caller: str | None = None) -> None:
        super().__init__()
        self._client = client
        self.call_log = CallLogger(log, {"call_id": call_id} if call_id else {})
        # The last text actually sent to AgenticOrg, for `next_turn_text`'s cumulative-transcript
        # collapse. Empty means "no turn sent yet this call".
        self._last_sent_text = ""
        # The signed-in caller, taken from the LiveKit token the portal minted (identity = email).
        # The platform's chat API identifies every call as the bridge's own login, so without this
        # the agent cannot know who it is talking to — and would have to ask for details the account
        # already holds, like the WhatsApp number. Attached once, as metadata, never read aloud.
        self._caller = caller
        self._caller_announced = False

    def with_caller(self, text: str) -> str:
        """Prefix the first turn with the caller's identity, once per call."""
        if not self._caller or self._caller_announced:
            return text
        self._caller_announced = True
        return f"[caller: {self._caller}] {text}"

    @property
    def model(self) -> str:
        return "agenticorg"

    @property
    def provider(self) -> str:
        return "agenticorg"

    @property
    def _stream_cls(self) -> type[LLMStream]:
        return AgenticOrgStream

    # A caller who re-says a short confirmation on purpose — "yes", "haan", "no" — must reach the
    # agent even if it is character-for-character what was last sent; the exact-repeat collapse below
    # exists for the framework re-invoking the pipeline with an unchanged transcript, not for a
    # genuine one-word reply that happens to repeat the previous one (e.g. the agent asked a yes/no
    # question twice). Case/punctuation-insensitive; Hindi forms included since the agent mirrors the
    # caller's language (declare-v6-notes.md §4).
    _SHORT_CONFIRMATIONS = frozenset(
        {
            "yes",
            "yeah",
            "yep",
            "yup",
            "ok",
            "okay",
            "correct",
            "right",
            "confirm",
            "confirmed",
            "no",
            "nope",
            "nah",
            "haan",
            "han",
            "ha",
            "haanji",
            "sahi",
            "theek",
            "thik",
            "theek hai",
            "thik hai",
            "nahi",
            "nahin",
            "nai",
        }
    )

    def next_turn_text(self, text: str) -> str | None:
        """Collapse a cumulative transcript re-send into the one new thing to tell the agent.

        Returns `None` when there is nothing new to send (an exact repeat, or a growing transcript
        whose only addition is whitespace); otherwise returns the text to send — the new suffix for
        a growing transcript, or the whole thing for a genuinely new utterance. A short yes/no-shaped
        answer is always sent, even if identical to the last sent text (see `_SHORT_CONFIRMATIONS`).
        """
        last = self._last_sent_text
        normalized = text.strip().lower().rstrip(".!?")
        if text == last:
            if normalized in self._SHORT_CONFIRMATIONS:
                self.call_log.info(
                    "voice transcript resend sent as a genuine confirmation repeat",
                    extra={"text": text},
                )
                return text
            self.call_log.info("voice transcript resend skipped", extra={"reason": "exact_repeat", "text": text})
            return None
        if last and text.startswith(last):
            suffix = text[len(last) :].strip()
            self._last_sent_text = text
            if not suffix:
                self.call_log.info("voice transcript resend skipped", extra={"reason": "no_new_suffix", "text": text})
                return None
            self.call_log.info(
                "voice transcript resend collapsed to suffix", extra={"suffix": suffix, "full_text": text}
            )
            return suffix
        self._last_sent_text = text
        return text

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


def build_llm(
    *,
    base_url: str,
    email: str,
    password: str,
    agent_id: str,
    timeout_s: float,
    call_id: str | None = None,
    caller: str | None = None,
) -> AgenticOrgChat:
    """Wire an `AgenticOrgChat` to a fresh HTTP client."""
    return AgenticOrgChat(
        call_id=call_id,
        caller=caller,
        client=AgentChat(
            base_url=base_url,
            email=email,
            password=password,
            agent_id=agent_id,
            timeout_s=timeout_s,
            call_id=call_id,
        ),
    )


__all__ = ["AgenticOrgChat", "AgenticOrgStream", "build_llm", "latest_user_text"]
