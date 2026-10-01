"""Store persistence: a process that restarts must see what the previous one wrote."""
from agent.schemas.models import ConnectorResult, Declaration
from agent.state.store import Store


def _hold() -> ConnectorResult:
    return ConnectorResult(source="venue", connector="venue_inventory", kind="mock", operation="create_hold",
                           request_id="req-1", status="success")


def test_declarations_and_ledger_reload_from_disk(tmp_path):
    state = tmp_path / "state"
    first = Store(state)
    first.put(Declaration(declaration_id="decl-1", state="VALIDATED"))
    first.ledger_put("key-1", _hold())

    reloaded = Store(state)

    assert reloaded.get("decl-1").state == "VALIDATED"
    assert reloaded.ledger_get("key-1").operation == "create_hold"


def test_declaration_written_after_load_is_visible_to_the_next_store(tmp_path):
    state = tmp_path / "state"
    store = Store(state)
    store.put(Declaration(declaration_id="decl-1"))
    store.put(Declaration(declaration_id="decl-2", state="CONFIRMED"))

    reloaded = Store(state)

    assert set(reloaded.declarations) == {"decl-1", "decl-2"}
    assert reloaded.get("decl-2").state == "CONFIRMED"


def test_corrupt_file_is_skipped_without_losing_the_others(tmp_path):
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "decl-bad.json").write_text("{ not json at all")
    (state / "decl-good.json").write_text(Declaration(declaration_id="decl-good").model_dump_json())

    store = Store(state)

    assert set(store.declarations) == {"decl-good"}


def test_ledger_file_is_not_mistaken_for_a_declaration(tmp_path):
    state = tmp_path / "state"
    first = Store(state)
    first.ledger_put("key-1", _hold())

    assert Store(state).declarations == {}
