"""Pine Labs mock connector (PINE_LABS_MODE=mock). Mirrors the DOCUMENTED P3P names
(authorizationId, Amount(value, currency), RESERVE_PAY) but response bodies are KIRRO mock schemas.
MOCK REQUIRED: sandbox onboarding not available; see docs/connectors.md."""

from __future__ import annotations

from connectors.base import HttpConnector, Op
from connectors.mock_schemas import BalanceResp, ExecuteResp, MandateReleaseResp, MandateResp, RefundResp


def _execute_ok(body: dict) -> tuple[bool, str, str]:
    if body.get("status") != "SUCCESS":
        return False, str(body.get("reason") or "PAYMENT_FAILED"), "payment was not captured"
    return True, "", ""


class PineLabsMockConnector(HttpConnector):
    source = "pine_labs"
    name = "pine_labs.mock"
    kind = "mock"
    ops = {
        "create_mandate": Op("POST", "/pinelabs/mandates", MandateResp),
        "get_mandate_balance": Op("GET", "/pinelabs/mandates/{authorizationId}/balance", BalanceResp),
        "execute_charge": Op("POST", "/pinelabs/mandates/{authorizationId}/execute", ExecuteResp, ok_check=_execute_ok),
        "release_mandate": Op("POST", "/pinelabs/mandates/{authorizationId}/release", MandateReleaseResp),
        "refund": Op("POST", "/pinelabs/payments/{payment_id}/refund", RefundResp),
    }
