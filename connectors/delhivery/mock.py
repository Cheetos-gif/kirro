"""Delhivery Express MOCK connector (competition-required mock).

Shapes follow the paths in the Delhivery Express docs (delhivery-express-api-doc.readme.io) as recorded in
docs/architecture-plan-v1.md: pincode serviceability, cmu/create.json, packages tracking. The query name
`filter_codes` is DOCUMENTED via community sources, not verified. Retarget to staging with a token only after
verifying each path; TODO marker below."""

from __future__ import annotations

from connectors.base import HttpConnector, NotConfiguredConnector, Op
from connectors.mock_schemas import CreateShipmentResp, PinResp, TrackResp


def _create_ok(body: dict) -> tuple[bool, str, str]:
    if not body.get("success"):
        return False, "CREATE_FAILED", str(body.get("rmk", ""))[:200]
    return True, "", ""


class DelhiveryMockConnector(HttpConnector):
    source = "delhivery"
    name = "delhivery.express.mock"
    kind = "mock"
    ops = {
        "check_serviceability": Op("GET", "/delhivery/c/api/pin-codes/json/", PinResp),
        "create_shipment": Op(
            "POST", "/delhivery/api/cmu/create.json", CreateShipmentResp, ok_check=_create_ok, form=True
        ),
        "track": Op("GET", "/delhivery/api/v1/packages/json/", TrackResp),
    }


def build_real_delhivery(env: dict) -> NotConfiguredConnector:
    # TODO(credentials): point DelhiveryExpress at https://staging-express.delhivery.com with
    # 'Authorization: Token <DELHIVERY_API_TOKEN>' after verifying each path on the readme.io docs.
    return NotConfiguredConnector("delhivery.express.staging", "delhivery", "real Delhivery connector not implemented")
