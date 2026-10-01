"""Explicit state machine. Pure functions; the LLM cannot mutate state, only request actions.

`transition()` is the ONLY place Declaration.state is assigned. Every legal edge is in TRANSITIONS and
each guard is a named function so a failure explains itself.
"""

from __future__ import annotations

from agent.schemas.models import ConnectorResult, Declaration, State

S = State

TERMINAL = {S.CLOSED, S.CANCELLED, S.RELEASED, S.FAILED, S.EXPIRED}
PRE_CONFIRMED = {
    S.INTAKE,
    S.AWAITING_USER,
    S.VALIDATED,
    S.AUTHORISING,
    S.AUTHORISED,
    S.WAITING_FOR_WINDOW,
    S.ALLOCATING,
    S.ALLOCATED,
    S.WAITLISTED,
    S.UNALLOCATED,
    S.HOLD_PLACED,
    S.PAYMENT_PENDING,
}

TRANSITIONS: dict[State, set[State]] = {
    S.INTAKE: {S.AWAITING_USER, S.VALIDATED},
    S.AWAITING_USER: {S.INTAKE},
    S.VALIDATED: {S.AUTHORISING},
    S.AUTHORISING: {S.AUTHORISED, S.AUTHORISING, S.AWAITING_USER},
    S.AUTHORISED: {S.WAITING_FOR_WINDOW},
    S.WAITING_FOR_WINDOW: {S.ALLOCATING},
    S.ALLOCATING: {S.ALLOCATED, S.WAITLISTED, S.UNALLOCATED},
    S.ALLOCATED: {S.HOLD_PLACED, S.ALLOCATING, S.WAITLISTED},
    S.WAITLISTED: {S.ALLOCATING, S.EXPIRED},
    S.UNALLOCATED: {S.EXPIRED},
    S.HOLD_PLACED: {S.PAYMENT_PENDING, S.RELEASED},
    S.PAYMENT_PENDING: {S.CONFIRMED, S.RELEASED},
    S.CONFIRMED: {S.FULFILMENT_PENDING, S.CLOSED},
    S.FULFILMENT_PENDING: {S.CLOSED},
}
# Any non-terminal state may go to FAILED; any pre-CONFIRMED non-terminal state may be CANCELLED.
for _s in list(PRE_CONFIRMED):
    TRANSITIONS.setdefault(_s, set()).add(S.CANCELLED)
for _s in PRE_CONFIRMED | {S.CONFIRMED, S.FULFILMENT_PENDING}:
    TRANSITIONS.setdefault(_s, set()).add(S.FAILED)


class IllegalTransition(Exception):
    def __init__(self, frm: State, to: State, reason: str):
        super().__init__(f"{frm.value} -> {to.value} refused: {reason}")
        self.frm, self.to, self.reason = frm, to, reason


def is_confirming(result: ConnectorResult | None, required_key: str) -> bool:
    """A result confirms an external action only if it is success (or an upstream duplicate that
    echoes the original identifier) AND carries the identifier we need."""
    if result is None or result.status not in ("success", "duplicate"):
        return False
    return bool(result.data.get(required_key))


def required_fields_present(d: Declaration) -> list[str]:
    missing = []
    if not d.event_id:
        missing.append("event")
    if not d.date:
        missing.append("date")
    if not d.group_size:
        missing.append("group_size")
    if d.max_price_paise is None:
        missing.append("max_price")
    return missing


def guard(d: Declaration, to: State) -> None:
    frm = d.state
    if frm in TERMINAL:
        raise IllegalTransition(frm, to, "source state is terminal")
    if to not in TRANSITIONS.get(frm, set()):
        raise IllegalTransition(frm, to, "edge not in transition table")
    if to == S.AWAITING_USER and frm == S.INTAKE and not d.open_field:
        raise IllegalTransition(frm, to, "no open field to ask about")
    if to == S.INTAKE and frm == S.AWAITING_USER and d.open_field:
        raise IllegalTransition(frm, to, "open field still unresolved")
    if to == S.VALIDATED:
        miss = required_fields_present(d)
        if miss:
            raise IllegalTransition(frm, to, f"missing required fields: {miss}")
        if not d.confirmed_by_user:
            raise IllegalTransition(frm, to, "user has not confirmed the read-back")
    if to == S.AUTHORISING and frm == S.VALIDATED:
        if not isinstance(d.max_price_paise, int) or isinstance(d.max_price_paise, bool) or d.max_price_paise <= 0:
            raise IllegalTransition(frm, to, "max_price is not an unambiguous integer paise value")
    if to == S.AUTHORISED and not d.mandate_id:
        raise IllegalTransition(frm, to, "no mandate id from the payment connector")
    if to == S.CONFIRMED:
        if not is_confirming(d.inventory_result, "booking_ref"):
            raise IllegalTransition(frm, to, "no successful inventory confirmation with booking_ref")
        if not is_confirming(d.payment_result, "payment_id"):
            raise IllegalTransition(frm, to, "no successful payment confirmation with payment_id")
    if to == S.HOLD_PLACED and not d.hold_id:
        raise IllegalTransition(frm, to, "no hold id from the inventory connector")
    if to == S.CANCELLED and frm not in PRE_CONFIRMED:
        raise IllegalTransition(frm, to, "cancel after confirmation is a separate refund flow")


def transition(d: Declaration, to: State) -> tuple[State, State]:
    """Validate and apply. Returns (before, after). Raises IllegalTransition."""
    guard(d, to)
    before = d.state
    d.state = to
    return before, to
