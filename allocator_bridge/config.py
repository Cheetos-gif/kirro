"""Allocator-trigger bridge configuration, all from the environment (ADR-018).

Mirrors `voice_bridge/config.py`'s shape and naming so the two bridges read the same AgenticOrg
credentials and conventions; this one talks to the mock over HTTP instead of a LiveKit room.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# The live "Kirro Allocator" agent on the competition tenant (docs/agenticorg/platform-map.md).
DEFAULT_ALLOCATOR_AGENT_ID = "5591e57a-79f9-4b30-a95e-0b910a467ce3"

# Everything in this repo that is keyed by run defaults to this, same as the mock and the portal.
DEFAULT_RUN_ID = "default"


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


def _require(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


@dataclass(frozen=True)
class AllocatorConfig:
    """Everything the allocator-trigger bridge reads from the environment."""

    mock_base_url: str
    agenticorg_base_url: str
    agenticorg_email: str
    agenticorg_password: str
    agent_id: str
    run_id: str
    request_timeout_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AllocatorConfig":
        e = os.environ if env is None else env
        return cls(
            # `MOCK_API_URL`/`MOCK_RUN_ID`: the same names `web/` already reads (web/example.env).
            mock_base_url=_require(e, "MOCK_API_URL").rstrip("/"),
            agenticorg_base_url=_require(e, "AGENTICORG_BASE_URL").rstrip("/"),
            agenticorg_email=_require(e, "AGENTICORG_EMAIL"),
            agenticorg_password=_require(e, "AGENTICORG_PASSWORD"),
            agent_id=(e.get("ALLOCATOR_AGENT_ID") or DEFAULT_ALLOCATOR_AGENT_ID).strip(),
            run_id=(e.get("MOCK_RUN_ID") or DEFAULT_RUN_ID).strip(),
            request_timeout_s=float(e.get("ALLOCATOR_TIMEOUT_S") or 180.0),
        )
