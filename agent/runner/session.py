"""A conversation session: Engine + declaration + tool set + transcript. Policy-agnostic."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agent.core import Engine
from agent.schemas.models import Declaration
from agent.tools.toolset import ToolSet


@dataclass
class HumanTurn:
    text: str | None = None
    interrupted: bool = False
    event: dict | None = None  # human/inventory event, e.g. {"type": "window_open"}


class Policy(Protocol):
    name: str

    def respond(self, session: "Session", turn: HumanTurn) -> None: ...


@dataclass
class Session:
    engine: Engine
    decl: Declaration
    policy: Policy
    prompt_version: str = "v0"
    tools: ToolSet = field(init=False)
    transcript: list[dict] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tools = ToolSet(self.engine, self.decl)

    def step(self, turn: HumanTurn) -> None:
        n_before = len(self.engine.messages)
        step = len(self.snapshots) + 1
        self.tools.turn_ended = False
        if turn.event is not None:
            self.transcript.append({"step": step, "role": "event", "text": str(turn.event)})
            self.engine.on_event(self.decl, turn.event)
        else:
            self.transcript.append({"step": step, "role": "user", "text": turn.text or "", "interrupted": turn.interrupted})
            self.engine.receive_user_turn(self.decl, turn.text, interrupted=turn.interrupted)
            self.policy.respond(self, turn)
        for m in self.engine.messages[n_before:]:
            self.transcript.append({"step": step, "role": "assistant", "text": m["text"], "state": m["state"]})
        self.snapshots.append(self.decl.model_dump(mode="json", exclude={"inventory_result", "payment_result"}))
