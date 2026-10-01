"""Gnani Inya platform client (GNANI_MODE=real). Not exercised without credentials.

DOCUMENTED (docs.gnani.ai, per docs/architecture-plan-v1.md, 2026-10-01); confirm on first real call:
  base   https://api.inya.ai/platform    header x-api-key
  POST /v1/agents/{botId}/trigger_call?environment=development
       body {phone, countryCode, name, clientReferenceId}; outbound only to WHITELISTED numbers
       (non-whitelisted -> HTTP 400). Handset spam filtering may still block the call.
  POST /v1/conversations/logs  -> transcripts with role, content, timestamp, detectedLanguage,
       totalResults, userInterruptionFlag
UNKNOWN: mapping API responses back into conversation variables ("Coming Soon" in one doc page).
Do not depend on it; KIRRO uses a post-call Custom API action -> POST /intake/gnani on KIRRO Core, then
fetches the transcript via conversations/logs.

TODO(credentials): request bodies for conversations/logs (filters) are not recorded in the plan.
Phone numbers are passed at call time only and are redacted in logs.
"""

from __future__ import annotations

from connectors.base import HttpConnector, NotConfiguredConnector, Op


class GnaniPlatformConnector(HttpConnector):
    source = "gnani"
    name = "gnani.inya"
    kind = "real"
    ops = {
        "trigger_call": Op("POST", "/v1/agents/{botId}/trigger_call?environment=development"),
        "conversation_logs": Op("POST", "/v1/conversations/logs"),
    }


def build_gnani(env: dict):
    if not env.get("GNANI_INYA_API_KEY") or not env.get("GNANI_AGENT_ID"):
        return NotConfiguredConnector("gnani.inya", "gnani", "missing GNANI_INYA_API_KEY or GNANI_AGENT_ID")
    import httpx

    client = httpx.Client(
        base_url=env.get("GNANI_INYA_BASE_URL", "https://api.inya.ai/platform"),
        headers={"x-api-key": env["GNANI_INYA_API_KEY"]},
    )
    return GnaniPlatformConnector(client)
