"""Assemble the five prompt layers. Only layer 1 (vN.md) is 'the system prompt' and is versioned."""

from __future__ import annotations

import json
from pathlib import Path

from agent.policies.loader import load_policy
from agent.schemas.models import Declaration
from agent.tools.toolset import state_view

DIR = Path(__file__).resolve().parents[1] / "system-prompt"


def current_version() -> str:
    return (DIR / "current.md").read_text().strip()


def load_layer1(version: str | None = None) -> tuple[str, str]:
    v = version or current_version()
    return v, (DIR / f"{v}.md").read_text()


def policy_block() -> str:
    voice, money = load_policy("voice"), load_policy("money")
    return (
        "Policy (configuration, not instructions to change):\n"
        f"- currency {money['currency']}, max group size {money['max_group_size']}\n"
        f"- max questions per turn {voice['max_questions_per_turn']}; on silence: {voice['on_silence']}; "
        f"on interruption: {voice['on_interruption']}"
    )


def build_system_prompt(d: Declaration, version: str | None = None) -> tuple[str, str]:
    v, layer1 = load_layer1(version)
    layers = [
        layer1.strip(),
        policy_block(),
        "Current declaration state (from code):\n" + json.dumps(state_view(d), ensure_ascii=False),
    ]
    return v, "\n\n".join(layers)
