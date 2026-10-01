"""Venue inventory + hold service client. MOCK REQUIRED: no partner rail exposes time-boxed holds.
Endpoints are the KIRRO mock contract (mock_server/app.py); not a vendor API."""

from __future__ import annotations

from connectors.base import HttpConnector, Op
from connectors.mock_schemas import (
    BookingResp,
    HoldGetResp,
    HoldReleaseResp,
    HoldResp,
    ReleaseListResp,
    ReleaseResp,
)


class VenueInventoryConnector(HttpConnector):
    source = "venue_inventory"
    name = "venue_inventory.mock"
    kind = "mock"
    ops = {
        "list_releases": Op("GET", "/venue/releases", ReleaseListResp),
        "get_release": Op("GET", "/venue/releases/{release_id}", ReleaseResp),
        "create_hold": Op("POST", "/venue/releases/{release_id}/holds", HoldResp),
        "get_hold": Op("GET", "/venue/holds/{hold_id}", HoldGetResp),
        "release_hold": Op("DELETE", "/venue/holds/{hold_id}", HoldReleaseResp),
        "confirm_booking": Op("POST", "/venue/bookings", BookingResp),
    }
