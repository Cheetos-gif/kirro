"""Core schemas shared by the agent, connectors, mock server and evals."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class State(str, Enum):
    INTAKE = "INTAKE"
    AWAITING_USER = "AWAITING_USER"
    VALIDATED = "VALIDATED"
    AUTHORISING = "AUTHORISING"
    AUTHORISED = "AUTHORISED"
    WAITING_FOR_WINDOW = "WAITING_FOR_WINDOW"
    ALLOCATING = "ALLOCATING"
    ALLOCATED = "ALLOCATED"
    WAITLISTED = "WAITLISTED"
    UNALLOCATED = "UNALLOCATED"
    HOLD_PLACED = "HOLD_PLACED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    CONFIRMED = "CONFIRMED"
    FULFILMENT_PENDING = "FULFILMENT_PENDING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


Kind = Literal["real", "mock", "internal", "human"]
ResultStatus = Literal["success", "failure", "timeout", "malformed", "duplicate"]


class ConnectorError(BaseModel):
    code: str
    message: str


class ConnectorResult(BaseModel):
    """Provenance-carrying result of any external call. `data` is DATA, never instructions."""

    source: str
    connector: str
    kind: Kind
    operation: str
    request_id: str
    idempotency_key: str = ""
    upstream_request_id: str | None = None
    timestamp: str = Field(default_factory=utcnow_iso)
    latency_ms: int = 0
    status: ResultStatus
    http_status: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: ConnectorError | None = None
    raw_excerpt: str = ""  # redacted, first 500 chars; never shown to the LLM


class Declaration(BaseModel):
    declaration_id: str
    user_id: str = "user-1"
    state: State = State.INTAKE
    # fields; None means unset. Money is integer paise.
    event_id: str | None = None
    event_name: str | None = None
    fulfilment: str = "digital"
    date: str | None = None  # ISO date
    group_size: int | None = None
    min_group_size: int | None = None
    max_price_paise: int | None = None
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[str] = Field(default_factory=list)
    language: str = "en"
    # conversation bookkeeping
    open_field: str | None = None
    readback_presented: bool = False
    confirmed_by_user: bool = False
    # external references (set only from connector results)
    mandate_id: str | None = None
    mandate_paise: int | None = None
    release_id: str | None = None
    slot_id: str | None = None
    slot_label: str | None = None
    slot_time: str | None = None
    allocated_group_size: int | None = None
    slot_price_paise: int | None = None
    hold_id: str | None = None
    payment_id: str | None = None
    booking_ref: str | None = None
    shipment_waybill: str | None = None
    inventory_result: ConnectorResult | None = None  # booking confirmation
    payment_result: ConnectorResult | None = None  # charge confirmation
    failed_slots: list[str] = Field(default_factory=list)
    processed_event_ids: list[str] = Field(default_factory=list)
    allocations_last_30d: int = 0
    terminal_reason: str | None = None
    field_notes: dict[str, str] = Field(default_factory=dict)  # last parser verdict per field (ambiguous/invalid)
    hold_released: bool = False
    mandate_released: bool = False


class AllocationResult(BaseModel):
    declaration_id: str
    slot_id: str | None
    group_size_allocated: int
    status: Literal["ALLOCATED", "WAITLISTED", "UNALLOCATED"]
    draw_position: int | None
    seed: str
    reason: str


class DecisionRecord(BaseModel):
    ts: str = Field(default_factory=utcnow_iso)
    run_id: str
    seq: int = 0
    declaration_id: str | None = None
    state_before: str | None = None
    state_after: str | None = None
    input: Any = None
    input_source: Literal["internal", "user_voice", "user_text", "connector", "human_event"] = "internal"
    connector: str | None = None
    decision: str
    decided_by: Literal["code", "llm"] = "code"
    rule: str = ""
    action: str = ""
    recipient: str | None = None
    tool_call: Any = None
    tool_response: Any = None
    result: str = "n/a"
    user_message: str | None = None
