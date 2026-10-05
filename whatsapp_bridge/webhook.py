"""Real-time acknowledgement for the WhatsApp "opener" message (ADR-022).

`Kirro Declare` has no WhatsApp channel linked — confirmed live via AgenticOrg's own agent API
(`docs/agenticorg/declare-v6-notes.md` §2, `GET /api/v1/agents/{id}` returning no whatsapp
connector/tool). Even if it ever is, running this exchange through the scored LLM agent means every
occurrence prices in at the cheap, tool-less 0.60 confidence bucket (`declare-v6-notes.md` §1,
`docs/agenticorg/agent-spec.md`'s scoring rule). The message itself is entirely mechanical: the
WhatsApp Business Platform only lets Kirro send the draw result inside the 24-hour window the user
opens by messaging first, and the one message the `/talk` popup's "Open WhatsApp" button sends is
always the same fixed shape (`whatsAppOpeningMessage`, `web/src/app/talk/talk-client.tsx`). So this
bridge, not the agent, owns the exchange end to end: receive Meta's Cloud API webhook, recognise
that one deterministic opener, and reply with a canned acknowledgement directly over the Graph API.
Anything else inbound is logged and ignored — this bridge never attempts a declaration or any other
conversational turn; that stays the voice/chat channel's job.

A relay, not a decision-maker — same shape as `voice_bridge/` and `allocator_bridge/`.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from collections import OrderedDict
from typing import Any

import httpx
from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from whatsapp_bridge.config import WhatsAppBridgeConfig

log = logging.getLogger("whatsapp_bridge")

# Mirrors talk-client.tsx's `whatsAppOpeningMessage`: both its named-booking and fallback shapes
# start with this exact greeting and state. Matching on the stable prefix rather than the whole
# string survives the booking detail that varies per call.
OPENER_PATTERN = re.compile(r"^Hi Kirro!\s+I['’]ve entered the draw\b", re.IGNORECASE)

ACK_TEXT = "Got it - I'll send your result here once the window closes."

# Meta redelivers a webhook it did not get a timely 200 for; an in-memory, size-capped LRU of
# recently seen message ids is enough to answer an immediate redelivery without acknowledging the
# same opener twice. No database: this bridge is stateless across restarts, like `allocator_bridge`
# and `voice_bridge` — a restart just means an at-most-one-extra-ack window, never a missed one.
_SEEN_MAX = 2048


class _SeenMessages:
    def __init__(self, maximum: int = _SEEN_MAX) -> None:
        self._ids: "OrderedDict[str, float]" = OrderedDict()
        self._maximum = maximum

    def seen_before(self, message_id: str) -> bool:
        if message_id in self._ids:
            self._ids.move_to_end(message_id)
            return True
        self._ids[message_id] = time.monotonic()
        if len(self._ids) > self._maximum:
            self._ids.popitem(last=False)
        return False


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    """Checks Meta's `X-Hub-Signature-256` against the raw request body.

    Meta signs the exact bytes it sent; re-serialising parsed JSON before checking would silently
    accept a tampered payload the moment formatting differs, so the caller must pass the untouched
    body straight from the request.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def _extract_text_messages(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """`(message_id, from_wa_id, text)` for every inbound text message in one webhook delivery.

    Meta's payload nests one webhook delivery into `entry[].changes[].value`; a single delivery can
    carry zero messages (e.g. a status update: sent/delivered/read) or several.
    """
    found: list[tuple[str, str, str]] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for message in value.get("messages") or []:
                if message.get("type") != "text":
                    continue
                text = ((message.get("text") or {}).get("body") or "").strip()
                message_id = message.get("id")
                sender = message.get("from")
                if text and message_id and sender:
                    found.append((message_id, sender, text))
    return found


async def _send_text(client: httpx.AsyncClient, config: WhatsAppBridgeConfig, to: str, body: str) -> None:
    response = await client.post(
        f"{config.graph_api_base}/{config.phone_number_id}/messages",
        headers={"Authorization": f"Bearer {config.access_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        },
    )
    if response.status_code >= 400:
        log.error("whatsapp send failed", extra={"status": response.status_code, "body": response.text[:300]})


def create_app(config: WhatsAppBridgeConfig, *, graph_client: httpx.AsyncClient | None = None) -> FastAPI:
    app = FastAPI(title="kirro-whatsapp-bridge")
    client = graph_client or httpx.AsyncClient(timeout=10.0)
    seen = _SeenMessages()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/webhook")
    async def verify(request: Request) -> Response:
        """Meta's one-time handshake when the Callback URL is saved in the app dashboard."""
        params = request.query_params
        if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == config.verify_token:
            return PlainTextResponse(params.get("hub.challenge") or "")
        return PlainTextResponse("verification failed", status_code=403)

    @app.post("/webhook")
    async def receive(request: Request, x_hub_signature_256: str | None = Header(default=None)) -> Response:
        body = await request.body()
        if not verify_signature(config.app_secret, body, x_hub_signature_256):
            log.warning("whatsapp webhook rejected: bad signature")
            return JSONResponse({"error": "bad signature"}, status_code=401)

        payload = await request.json()
        for message_id, sender, text in _extract_text_messages(payload):
            if seen.seen_before(message_id):
                continue
            if OPENER_PATTERN.search(text):
                log.info("whatsapp opener acknowledged", extra={"to": sender, "message_id": message_id})
                await _send_text(client, config, sender, ACK_TEXT)
            else:
                # Deliberately not a declaration channel (ADR-022): log and move on, never reply,
                # never call an agent.
                log.info(
                    "whatsapp inbound message ignored (not the opener)",
                    extra={"from": sender, "message_id": message_id},
                )
        # Meta only cares about the 2xx; the body is ignored.
        return JSONResponse({"status": "ok"})

    return app
