"""MOCK response schemas, shared by mock_server (producer) and connector clients (validator).

These are NOT vendor-verified schemas. Where a shape mirrors a documented vendor shape it is noted in
docs/connectors.md; everything else is a KIRRO mock contract. A response that fails validation is
classified `malformed` by the connector layer.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Money(BaseModel):
    value: int  # paise
    currency: str = "INR"


class VenueSlot(BaseModel):
    slot_id: str
    label: str
    starts_at: str
    capacity: int
    price_per_person_paise: int


class ReleaseResp(BaseModel):
    release_id: str
    event_id: str
    opens_at: str
    slots: list[VenueSlot]


class ReleaseSummary(BaseModel):
    release_id: str
    event_id: str
    date: str
    opens_at: str


class ReleaseListResp(BaseModel):
    releases: list[ReleaseSummary]


class HoldResp(BaseModel):
    hold_id: str
    slot_id: str
    quantity: int
    price_per_unit_paise: int
    expires_at: str


class HoldGetResp(BaseModel):
    hold_id: str
    status: Literal["active", "expired", "released"]
    expires_at: str


class HoldReleaseResp(BaseModel):
    hold_id: str
    released: bool


class BookingResp(BaseModel):
    booking_ref: str
    status: Literal["CONFIRMED"]
    hold_id: str
    amount_paise: int


class MandateResp(BaseModel):
    authorizationId: str
    status: Literal["ACTIVE"]
    amount: Money


class BalanceResp(BaseModel):
    authorizationId: str
    status: Literal["ACTIVE", "RELEASED", "EXHAUSTED"]
    balance: Money


class ExecuteResp(BaseModel):
    payment_id: str
    status: Literal["SUCCESS", "FAILED"]
    receipt_id: str | None = None
    reason: str | None = None
    amount: Money


class MandateReleaseResp(BaseModel):
    authorizationId: str
    status: Literal["RELEASED"]
    released_amount: Money


class RefundResp(BaseModel):
    refund_id: str
    payment_id: str
    status: Literal["REFUNDED"]


class PinPostal(BaseModel):
    pin: int
    pre_paid: str
    cash: str
    pickup: str
    district: str
    state_code: str


class PinEntry(BaseModel):
    postal_code: PinPostal


class PinResp(BaseModel):
    delivery_codes: list[PinEntry]


class Package(BaseModel):
    waybill: str
    refnum: str
    status: str


class CreateShipmentResp(BaseModel):
    success: bool
    packages: list[Package] = []
    rmk: str = ""


class TrackStatus(BaseModel):
    Status: str


class TrackShipment(BaseModel):
    AWB: str
    Status: TrackStatus


class TrackEntry(BaseModel):
    Shipment: TrackShipment


class TrackResp(BaseModel):
    ShipmentData: list[TrackEntry]


class ExtractField(BaseModel):
    value: object | None
    confidence: float
    evidence: str
    status: str


class ExtractResp(BaseModel):
    fields: dict[str, ExtractField]
    language: str
