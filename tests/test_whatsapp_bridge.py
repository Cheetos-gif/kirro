"""WhatsApp bridge (ADR-022) — offline tests.

No network, no real Meta Graph API: outbound sends go through an `httpx.MockTransport` stand-in, and
the webhook's inbound side is exercised with FastAPI's `TestClient` against synthetic Cloud API
payloads shaped like Meta's own documented webhook format.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from whatsapp_bridge.config import ConfigError, WhatsAppBridgeConfig
from whatsapp_bridge.webhook import ACK_TEXT, OPENER_PATTERN, create_app, verify_signature

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"


def _config() -> WhatsAppBridgeConfig:
    return WhatsAppBridgeConfig(
        access_token="test-token",
        phone_number_id="1387147764471942",
        verify_token=VERIFY_TOKEN,
        app_secret=APP_SECRET,
        graph_api_base="https://graph.facebook.com/v21.0",
        port=8083,
    )


class _GraphAPI:
    """Stand-in for Meta's Graph API: records every outbound send."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("authorization"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"messages": [{"id": "wamid.ack"}]})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def _sign(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _message_payload(message_id: str, sender: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "170940770644405",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "918167312268",
                                "phone_number_id": "1387147764471942",
                            },
                            "contacts": [{"profile": {"name": "Test"}, "wa_id": sender}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "timestamp": "1700000000",
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


class TestOpenerPattern:
    def test_matches_a_named_booking_opener(self) -> None:
        assert OPENER_PATTERN.search(
            "Hi Kirro! I've entered the draw for tennis on 10 October. Please send my result here."
        )

    def test_matches_the_fallback_opener(self) -> None:
        assert OPENER_PATTERN.search("Hi Kirro! I've entered the draw. Please send my result here.")

    def test_does_not_match_an_unrelated_message(self) -> None:
        assert not OPENER_PATTERN.search("Hi, what time does badminton open tomorrow?")


class TestSignatureVerification:
    def test_accepts_a_correctly_signed_body(self) -> None:
        body = b'{"object":"whatsapp_business_account"}'
        assert verify_signature(APP_SECRET, body, _sign(body)) is True

    def test_rejects_a_tampered_body(self) -> None:
        body = b'{"object":"whatsapp_business_account"}'
        signature = _sign(body)
        assert verify_signature(APP_SECRET, b'{"object":"tampered"}', signature) is False

    def test_rejects_a_missing_header(self) -> None:
        assert verify_signature(APP_SECRET, b"{}", None) is False

    def test_rejects_a_malformed_header(self) -> None:
        assert verify_signature(APP_SECRET, b"{}", "not-sha256") is False


class TestWebhookVerificationHandshake:
    def test_echoes_the_challenge_on_a_matching_verify_token(self) -> None:
        client = TestClient(create_app(_config(), graph_client=_GraphAPI().client()))
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"},
        )
        assert response.status_code == 200
        assert response.text == "12345"

    def test_refuses_a_wrong_verify_token(self) -> None:
        client = TestClient(create_app(_config(), graph_client=_GraphAPI().client()))
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
        )
        assert response.status_code == 403


class TestInboundOpener:
    def test_acknowledges_the_opener_without_calling_any_agent(self) -> None:
        graph = _GraphAPI()
        client = TestClient(create_app(_config(), graph_client=graph.client()))
        body = json.dumps(
            _message_payload("wamid.1", "919876543210", "Hi Kirro! I've entered the draw for tennis on 10 October.")
        ).encode()

        response = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _sign(body)})

        assert response.status_code == 200
        assert len(graph.sent) == 1
        sent = graph.sent[0]
        assert sent["url"].endswith("/1387147764471942/messages")
        assert sent["auth"] == "Bearer test-token"
        assert sent["body"] == {
            "messaging_product": "whatsapp",
            "to": "919876543210",
            "type": "text",
            "text": {"body": ACK_TEXT},
        }

    def test_ignores_a_message_that_is_not_the_opener(self) -> None:
        graph = _GraphAPI()
        client = TestClient(create_app(_config(), graph_client=graph.client()))
        body = json.dumps(_message_payload("wamid.2", "919876543210", "What time does badminton open?")).encode()

        response = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _sign(body)})

        assert response.status_code == 200
        assert graph.sent == []

    def test_does_not_acknowledge_the_same_message_twice(self) -> None:
        graph = _GraphAPI()
        client = TestClient(create_app(_config(), graph_client=graph.client()))
        body = json.dumps(_message_payload("wamid.3", "919876543210", "Hi Kirro! I've entered the draw.")).encode()
        headers = {"X-Hub-Signature-256": _sign(body)}

        first = client.post("/webhook", content=body, headers=headers)
        second = client.post("/webhook", content=body, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert len(graph.sent) == 1

    def test_rejects_a_badly_signed_delivery(self) -> None:
        graph = _GraphAPI()
        client = TestClient(create_app(_config(), graph_client=graph.client()))
        body = json.dumps(_message_payload("wamid.4", "919876543210", "Hi Kirro!")).encode()

        response = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=deadbeef"})

        assert response.status_code == 401
        assert graph.sent == []

    def test_ignores_a_status_update_delivery(self) -> None:
        """Meta also posts delivery/read receipts on the same webhook; they carry no `messages`."""
        graph = _GraphAPI()
        client = TestClient(create_app(_config(), graph_client=graph.client()))
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "170940770644405",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "statuses": [{"id": "wamid.ack", "status": "delivered"}],
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode()

        response = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _sign(body)})

        assert response.status_code == 200
        assert graph.sent == []


class TestHealth:
    def test_health_ok(self) -> None:
        client = TestClient(create_app(_config(), graph_client=_GraphAPI().client()))
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestConfig:
    def test_from_env_reads_required_and_defaulted_values(self) -> None:
        config = WhatsAppBridgeConfig.from_env(
            {
                "WHATSAPP_ACCESS_TOKEN": "tok",
                "WHATSAPP_VERIFY_TOKEN": "vtok",
                "WHATSAPP_APP_SECRET": "secret",
            }
        )
        assert config.access_token == "tok"
        assert config.phone_number_id == "1387147764471942"
        assert config.graph_api_base == "https://graph.facebook.com/v21.0"
        assert config.port == 8083

    def test_from_env_requires_access_token(self) -> None:
        with pytest.raises(ConfigError):
            WhatsAppBridgeConfig.from_env({"WHATSAPP_VERIFY_TOKEN": "v", "WHATSAPP_APP_SECRET": "s"})
