"""Voice-bridge configuration, all from the environment (ADR-016, ADR-017).

The bridge is a LiveKit agent worker: it joins the room the browser publishes its microphone to,
with Gnani supplying speech-to-text and text-to-speech, and AgenticOrg's chat API standing in for
the model. Nothing here is a decision the bridge makes — these are addresses and credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# The live "Kirro Declare" agent on the competition tenant.
DEFAULT_AGENT_ID = "27ec9d3c-ffe2-423f-a397-7569bf8f0f61"

# The worker's own health endpoint (LiveKit's ServerOptions.port).
DEFAULT_HEALTH_PORT = 8082


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


def _require(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _first(env: Mapping[str, str], *keys: str) -> str:
    """First non-empty value among `keys`, for secrets already named elsewhere in this repo."""
    for key in keys:
        value = (env.get(key) or "").strip()
        if value:
            return value
    raise ConfigError(f"{keys[0]} is required")


@dataclass(frozen=True)
class VoiceConfig:
    """Everything the voice bridge reads from the environment."""

    gnani_api_key: str
    agenticorg_base_url: str
    agenticorg_email: str
    agenticorg_password: str
    agent_id: str
    language: str
    voice: str
    tts_model: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    health_port: int
    request_timeout_s: float
    log_dir: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "VoiceConfig":
        e = os.environ if env is None else env
        return cls(
            # `GNANI_API_KEY` is the plugin's own default; the longer names are what this repo's
            # .env and setup runbook already use for the same key.
            gnani_api_key=_first(e, "GNANI_API_KEY", "GNANI_API_KEY_ID", "VACHANA_API_KEY_ID"),
            agenticorg_base_url=_require(e, "AGENTICORG_BASE_URL").rstrip("/"),
            agenticorg_email=_require(e, "AGENTICORG_EMAIL"),
            agenticorg_password=_require(e, "AGENTICORG_PASSWORD"),
            agent_id=(e.get("VOICE_AGENT_ID") or DEFAULT_AGENT_ID).strip(),
            language=(e.get("VOICE_LANGUAGE") or "en-IN").strip(),
            voice=(e.get("VOICE_TTS_VOICE") or "Kaveri").strip(),
            tts_model=(e.get("VOICE_TTS_MODEL") or "timbre-v2.5").strip(),
            livekit_url=_require(e, "LIVEKIT_URL"),
            livekit_api_key=_require(e, "LIVEKIT_API_KEY"),
            livekit_api_secret=_require(e, "LIVEKIT_API_SECRET"),
            health_port=int(e.get("VOICE_HEALTH_PORT") or DEFAULT_HEALTH_PORT),
            request_timeout_s=float(e.get("VOICE_AGENT_TIMEOUT_S") or 180.0),
            # One JSONL file per call (ADR-017 §logging): same convention as the mock's
            # `logs/mock/<run_id>.jsonl` (MOCK_LOG_DIR).
            log_dir=(e.get("VOICE_LOG_DIR") or "logs/voice").strip(),
        )

    def export_plugin_env(self) -> None:
        """The Gnani plugin reads `GNANI_API_KEY` from the environment when no key is passed."""
        os.environ.setdefault("GNANI_API_KEY", self.gnani_api_key)
