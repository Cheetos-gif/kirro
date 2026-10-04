"""Agent-stats sync configuration, all from the environment (ADR-020).

Mirrors `allocator_bridge/config.py`'s shape and naming, so the two scheduled jobs read the same
AgenticOrg credentials and the same `MOCK_API_URL`/`MOCK_RUN_ID` conventions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# The live agents on the competition tenant (docs/agenticorg/declare-v6-notes.md,
# docs/agenticorg/platform-map.md). Kept as a default list so the CronJob needs no extra config;
# `AGENT_STATS_AGENT_IDS` (comma-separated) overrides it without a code change.
DEFAULT_AGENT_IDS = (
    "6596b872-abb5-465a-87d3-fff8de17536d",  # Kirro Declare v6
    "5591e57a-79f9-4b30-a95e-0b910a467ce3",  # Kirro Allocator
)

DEFAULT_RUN_ID = "default"


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


def _require(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


@dataclass(frozen=True)
class StatsSyncConfig:
    """Everything the stats sync reads from the environment."""

    mock_base_url: str
    agenticorg_base_url: str
    agenticorg_email: str
    agenticorg_password: str
    agent_ids: tuple[str, ...]
    mock_admin_key: str
    run_id: str
    request_timeout_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "StatsSyncConfig":
        e = os.environ if env is None else env
        raw_ids = (e.get("AGENT_STATS_AGENT_IDS") or "").strip()
        agent_ids = tuple(part.strip() for part in raw_ids.split(",") if part.strip()) or DEFAULT_AGENT_IDS
        return cls(
            mock_base_url=_require(e, "MOCK_API_URL").rstrip("/"),
            agenticorg_base_url=_require(e, "AGENTICORG_BASE_URL").rstrip("/"),
            agenticorg_email=_require(e, "AGENTICORG_EMAIL"),
            agenticorg_password=_require(e, "AGENTICORG_PASSWORD"),
            agent_ids=agent_ids,
            # Optional: the mock's `/__admin/*` guard is a no-op until an operator provisions the key,
            # so a deployment without it still syncs (the `PUT` simply is not gated).
            mock_admin_key=(e.get("MOCK_ADMIN_KEY") or "").strip(),
            run_id=(e.get("MOCK_RUN_ID") or DEFAULT_RUN_ID).strip(),
            request_timeout_s=float(e.get("AGENT_STATS_TIMEOUT_S") or 30.0),
        )
