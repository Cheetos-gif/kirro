"""Live policy: the Anthropic SDK drives the same tools. Needs ANTHROPIC_API_KEY. Not used by tests.

Model default claude-sonnet-5-5 (env KIRRO_MODEL). Notes from the claude-api skill: no `thinking` param
(Sonnet 5.5 runs adaptive by default), no temperature, no forced tool_choice (400 on this model), no prefill.
"""

from __future__ import annotations

import os

from agent.runner.prompt import build_system_prompt
from agent.runner.session import HumanTurn, Session
from agent.tools.render import render_connector_result  # noqa: F401  (used when connector text is shown to the model)
from agent.tools.toolset import TOOL_DEFS

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_STEPS = 6


class AnthropicPolicy:
    name = "anthropic"

    def __init__(self, prompt_version: str | None = None, model: str | None = None, client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.model = model or os.environ.get("KIRRO_MODEL", DEFAULT_MODEL)
        self.prompt_version = prompt_version
        self.history: list[dict] = []

    @staticmethod
    def _as_user_text(turn: HumanTurn) -> str:
        if not (turn.text or "").strip():
            return "[The user said nothing (silence).]"
        if turn.interrupted:
            return f"[The user interrupted you.] {turn.text}"
        return turn.text

    def respond(self, s: Session, turn: HumanTurn) -> None:
        self.history.append({"role": "user", "content": self._as_user_text(turn)})
        for _ in range(MAX_STEPS):
            _, system = build_system_prompt(s.decl, self.prompt_version)
            resp = self.client.messages.create(
                model=self.model, max_tokens=2048, system=system, tools=TOOL_DEFS, messages=self.history
            )
            self.history.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "refusal":
                s.engine._rec(
                    s.decl, decision="model_refusal", rule="stop_reason=refusal", decided_by="llm", result="refused"
                )
                return
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                return
            results = []
            for b in calls:
                out = s.tools.execute(b.name, dict(b.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": str(out),
                        "is_error": not out.get("ok", True),
                    }
                )
            self.history.append({"role": "user", "content": results})
            if s.tools.turn_ended:
                return
