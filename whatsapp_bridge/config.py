"""WhatsApp bridge configuration, all from the environment (ADR-022).

The bridge is a plain webhook receiver for Meta's WhatsApp Cloud API: it owns no state and makes no
booking decisions. These are addresses and credentials only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# Kirro's own WhatsApp Business number (docs/agenticorg/declare-v6-notes.md §2). Matches the
# `whatsapp_kirro` connector's `base_url` on AgenticOrg (`https://graph.facebook.com/v21.0/<id>`),
# confirmed live via `GET /api/v1/connectors/{id}`.
DEFAULT_PHONE_NUMBER_ID = "1387147764471942"

DEFAULT_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

DEFAULT_PORT = 8083


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


def _require(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


@dataclass(frozen=True)
class WhatsAppBridgeConfig:
    """Everything the bridge reads from the environment."""

    access_token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    graph_api_base: str
    port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WhatsAppBridgeConfig":
        e = os.environ if env is None else env
        return cls(
            access_token=_require(e, "WHATSAPP_ACCESS_TOKEN"),
            phone_number_id=(e.get("WHATSAPP_PHONE_NUMBER_ID") or DEFAULT_PHONE_NUMBER_ID).strip(),
            verify_token=_require(e, "WHATSAPP_VERIFY_TOKEN"),
            app_secret=_require(e, "WHATSAPP_APP_SECRET"),
            graph_api_base=(e.get("WHATSAPP_GRAPH_API_BASE") or DEFAULT_GRAPH_API_BASE).rstrip("/"),
            port=int(e.get("WHATSAPP_BRIDGE_PORT") or DEFAULT_PORT),
        )
