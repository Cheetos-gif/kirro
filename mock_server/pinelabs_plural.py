"""Optional real call-out to Pine Labs Plural's UAT sandbox (ADR-019).

KIRRO's own Pine Labs mandate (authorize/hold/capture/release) has no Plural equivalent
(ADR-010 decision 2) and stays this mock's own simulation — source of truth for ceiling
enforcement, idempotency and offline tests (`uv run pytest` must stay network-free). What
Plural does have, for real, is an order/refund rail: the official `pinelabs-python` SDK against
its UAT sandbox. When `PINELABS_CLIENT_ID` / `PINELABS_CLIENT_SECRET` are set, a successful mock
capture also places a real UAT order, and a mock refund also places a real UAT refund — the
mandate bookkeeping is unaffected either way. Unset (the default, and every offline test): this
module makes zero network calls, `enabled` is False.

A failed or unreachable UAT call is caught and returned as `{"error": ...}` on the payment
record; it never raises and never changes the mock's own response status — a flaky sandbox must
not break the KIRRO demo.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pinelabs import Amount, PinelabsApi
from pinelabs.core.api_error import ApiError
from pinelabs.refunds import CreateRefundRequestOrderAmount

log = logging.getLogger("mock_server.pinelabs_plural")

DEFAULT_BASE_URL = "https://pluraluat.v2.pinepg.in"


class RealPinelabsClient:
    """Lazily authenticates (OAuth2 client_credentials) and caches the token until it is close
    to expiry. Every public method is best-effort: disabled returns `None`, a failure returns
    `{"error": ...}`, neither ever raises — a flaky UAT sandbox must not break the mock."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id if client_id is not None else os.environ.get("PINELABS_CLIENT_ID")
        self.client_secret = client_secret if client_secret is not None else os.environ.get("PINELABS_CLIENT_SECRET")
        self.base_url = base_url or os.environ.get("PINELABS_BASE_URL", DEFAULT_BASE_URL)
        self.enabled = bool(self.client_id and self.client_secret)
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: datetime | None = None
        # A bare `httpx.Client` for the token endpoint only: `pinelabs-python` 0.2.1's own
        # client_wrapper unconditionally sends `Authorization: Bearer {token}`, so its documented
        # `token=""` bootstrap pattern sends `Bearer ` (trailing space) and httpx/h11 reject that
        # as an illegal header value before the request ever reaches the token endpoint. Fetching
        # the token with a plain POST sidesteps the SDK entirely for this one call; every other
        # call goes through the SDK once a real, non-empty token exists.
        self._token_http = httpx_client or httpx.Client()
        self._client: PinelabsApi | None = None
        if self.enabled:
            self._client = PinelabsApi(base_url=self.base_url, token=self._token_value, httpx_client=httpx_client)

    def _token_value(self) -> str:
        with self._lock:
            now = datetime.now(timezone.utc)
            if self._token and self._expires_at and now < self._expires_at - timedelta(seconds=30):
                return self._token
            resp = self._token_http.post(
                f"{self.base_url}/api/auth/v1/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("access_token") or ""
            expires_at_raw = data.get("expires_at")
            self._expires_at = (
                datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
                if expires_at_raw
                else now + timedelta(minutes=5)
            )
            return self._token

    def create_order(self, amount_paise: int, reference: str) -> dict[str, Any] | None:
        """Place a real UAT order for a successful mock capture. `None` when disabled (the
        default); otherwise `{"order_id", "status"}` or `{"error": ...}`."""
        if not self.enabled:
            return None
        try:
            assert self._client is not None
            order = self._client.orders.create_order(
                merchant_order_reference=reference,
                order_amount=Amount(value=amount_paise, currency="INR"),
            )
            data = order.data
            return {"order_id": getattr(data, "order_id", None), "status": getattr(data, "status", None)}
        except ApiError as e:
            log.warning("pinelabs_plural create_order failed for %s: %s", reference, e)
            return {"error": str(e)}
        except Exception as e:  # pragma: no cover - network/library surprises
            log.warning("pinelabs_plural create_order errored for %s: %s", reference, e)
            return {"error": str(e)}

    def create_refund(self, order_id: str, amount_paise: int, reference: str) -> dict[str, Any] | None:
        """Place a real UAT refund against a real order `create_order` returned earlier. `None`
        when disabled or there is no real order to refund against; otherwise `{"order_id",
        "status"}` (Plural models a refund as an order of `type: refund`) or `{"error": ...}`."""
        if not self.enabled:
            return None
        try:
            assert self._client is not None
            refund = self._client.refunds.create_refund(
                order_id,
                merchant_order_reference=reference,
                order_amount=CreateRefundRequestOrderAmount(value=amount_paise, currency="INR"),
            )
            data = refund.data
            return {"order_id": getattr(data, "order_id", None), "status": getattr(data, "status", None)}
        except ApiError as e:
            log.warning("pinelabs_plural create_refund failed for %s: %s", reference, e)
            return {"error": str(e)}
        except Exception as e:  # pragma: no cover - network/library surprises
            log.warning("pinelabs_plural create_refund errored for %s: %s", reference, e)
            return {"error": str(e)}


_singleton: RealPinelabsClient | None = None
_singleton_lock = threading.Lock()


def get_real_pinelabs_client() -> RealPinelabsClient:
    """Process-wide instance, built once from the environment at first use. Tests construct
    their own `RealPinelabsClient(...)` directly (with a stub `httpx_client`) instead of using
    this singleton, so toggling env vars mid-suite never races this cache."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = RealPinelabsClient()
        return _singleton
