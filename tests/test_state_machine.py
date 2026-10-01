import pytest

from agent.schemas.models import ConnectorResult, Declaration, State
from agent.state.machine import PRE_CONFIRMED, TERMINAL, TRANSITIONS, IllegalTransition, transition


def ok_result(**data):
    return ConnectorResult(
        source="x", connector="x.mock", kind="mock", operation="op", request_id="r", status="success", data=data
    )


def decl(state=State.INTAKE, **kw):
    return Declaration(declaration_id="d", state=state, **kw)


def test_arbitrary_jump_refused():
    with pytest.raises(IllegalTransition):
        transition(decl(State.INTAKE), State.CONFIRMED)
    with pytest.raises(IllegalTransition):
        transition(decl(State.WAITING_FOR_WINDOW), State.HOLD_PLACED)


def test_terminal_states_are_final():
    for s in TERMINAL:
        with pytest.raises(IllegalTransition):
            transition(decl(s), State.INTAKE)


def test_validated_requires_fields_and_user_confirmation():
    d = decl(group_size=4, event_id="e", date="2026-10-03", max_price_paise=30000)
    with pytest.raises(IllegalTransition, match="read-back"):
        transition(d, State.VALIDATED)
    d.confirmed_by_user = True
    transition(d, State.VALIDATED)
    with pytest.raises(IllegalTransition, match="missing"):
        transition(decl(confirmed_by_user=True), State.VALIDATED)


def test_authorising_needs_integer_paise():
    d = decl(State.VALIDATED, max_price_paise=None)
    with pytest.raises(IllegalTransition, match="integer paise"):
        transition(d, State.AUTHORISING)


def test_confirmed_needs_both_external_confirmations():
    d = decl(State.PAYMENT_PENDING)
    with pytest.raises(IllegalTransition, match="inventory"):
        transition(d, State.CONFIRMED)
    d.inventory_result = ok_result(booking_ref="BK-1")
    with pytest.raises(IllegalTransition, match="payment"):
        transition(d, State.CONFIRMED)
    d.payment_result = ConnectorResult(
        source="p",
        connector="p.mock",
        kind="mock",
        operation="op",
        request_id="r",
        status="failure",
        data={"payment_id": "p1"},
    )
    with pytest.raises(IllegalTransition, match="payment"):
        transition(d, State.CONFIRMED)  # failure result never confirms, even if it carries an id
    d.payment_result = ok_result(payment_id="p1")
    transition(d, State.CONFIRMED)
    assert d.state == State.CONFIRMED


def test_confirmed_needs_identifier_not_just_success():
    d = decl(State.PAYMENT_PENDING, inventory_result=ok_result(), payment_result=ok_result(payment_id="p"))
    with pytest.raises(IllegalTransition):
        transition(d, State.CONFIRMED)


@pytest.mark.parametrize("s", sorted(PRE_CONFIRMED, key=lambda x: x.value))
def test_cancel_from_every_pre_confirmed_state(s):
    d = decl(s)
    transition(d, State.CANCELLED)
    assert d.state == State.CANCELLED


def test_cancel_after_confirmed_is_not_a_transition():
    with pytest.raises(IllegalTransition):
        transition(decl(State.CONFIRMED), State.CANCELLED)


def test_awaiting_user_needs_open_field():
    with pytest.raises(IllegalTransition):
        transition(decl(State.INTAKE), State.AWAITING_USER)
    d = decl(State.INTAKE, open_field="date")
    transition(d, State.AWAITING_USER)
    with pytest.raises(IllegalTransition):
        transition(d, State.INTAKE)  # open field still unresolved


def test_every_declared_edge_targets_a_real_state():
    for frm, tos in TRANSITIONS.items():
        assert frm in State and all(t in State for t in tos)
