"""KIRRO engine: deterministic orchestration around the state machine.

The LLM (or the offline stub) may only call the intake-facing methods: set_field, ask_user,
report_to_user, confirm_readback, request_authorisation, cancel. Everything after authorisation
(allocation, hold, charge, booking, unwinding) runs from human/inventory EVENTS, never from the model.
Every state change and every connector call writes a DecisionRecord.
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from agent.policies.loader import load_policy
from agent.policies.money import charge_within_limits, mandate_amount_paise
from agent.schemas.models import AllocationResult, ConnectorResult, Declaration, State
from agent.state import fields as F
from agent.state.machine import PRE_CONFIRMED, TERMINAL, IllegalTransition, required_fields_present, transition
from agent.state.store import Store, idempotency_key
from agent.tools import messages as M
from allocator.engine import Bid, Slot, allocate
from connectors.registry import Connectors
from logging_.decision_log import DecisionLog

_CHANGE_RE = re.compile(r"(?i)\b(actually|instead|change|changed|make it|rather|nahi|no wait|correction|sorry)\b")
_CLAIM_OK_STATES = {State.CONFIRMED, State.FULFILMENT_PENDING, State.CLOSED}


def ok(**kw: Any) -> dict:
    return {"ok": True, **kw}


def refuse(reason: str, **kw: Any) -> dict:
    return {"ok": False, "reason": reason, **kw}


class Engine:
    def __init__(self, connectors: Connectors, store: Store, log: DecisionLog, catalogue: list[dict],
                 today: date | None = None, competitors: list[Bid] | None = None):
        self.c = connectors
        self.store = store
        self.log = log
        self.catalogue = catalogue
        self.today = today or date.today()
        self.competitors = competitors or []
        self.messages: list[dict] = []
        self.last_user_text: dict[str, str] = {}
        self.last_allocation: AllocationResult | None = None

    # ------------------------------------------------------------------ logging helpers
    def _rec(self, d: Declaration | None, **kw: Any) -> None:
        kw.setdefault("state_before", d.state.value if d else None)
        kw.setdefault("state_after", d.state.value if d else None)
        self.log.record(declaration_id=d.declaration_id if d else None, **kw)

    def _go(self, d: Declaration, to: State, *, rule: str, input: Any = None, input_source: str = "internal",
            decision: str | None = None, connector: str | None = None, result: str = "n/a", **kw: Any) -> None:
        try:
            before, after = transition(d, to)
        except IllegalTransition as e:
            self._rec(d, decision="transition_refused", rule=rule, input=input, input_source=input_source,
                      action=f"{d.state.value}->{to.value}", result="refused", tool_response=str(e))
            raise
        self.store.put(d)
        self._rec(d, state_before=before.value, state_after=after.value, decision=decision or f"transition:{to.value}",
                  rule=rule, input=input, input_source=input_source, connector=connector, action="state_change",
                  result=result, **kw)

    def say(self, d: Declaration, text: str, rule: str, decided_by: str = "code") -> None:
        """The only way text reaches the user. Claims of success are blocked unless state allows them."""
        if M.CLAIM_RE.search(text) and d.state not in _CLAIM_OK_STATES:
            self._rec(d, decision="message_blocked", rule="no success claim before CONFIRMED", decided_by=decided_by,
                      action="blocked_user_message", recipient="user", tool_response=text, result="refused")
            raise ValueError("message asserts a completed action but state is " + d.state.value)
        self.messages.append({"state": d.state.value, "text": text, "declaration_id": d.declaration_id})
        self._rec(d, decision="message_to_user", rule=rule, decided_by=decided_by, action="speak",
                  recipient="user", user_message=text, result="success")

    # ------------------------------------------------------------------ connector calls with ledger
    def _call(self, d: Declaration, conn: Any, op: str, payload: dict, scope: str, rule: str,
              reattempt_on_malformed: bool = False) -> ConnectorResult:
        key = idempotency_key(d.declaration_id, d.state.value, scope)
        cached = self.store.ledger_get(key)
        if cached is not None:
            self._rec(d, decision="ledger_replay", rule="idempotency ledger: same key returns stored result",
                      connector=cached.connector, action=f"skip:{op}", tool_call={"operation": op, "key": key},
                      tool_response=self._summ(cached), result=cached.status, input_source="connector")
            return cached
        res = conn.call(op, payload, idempotency_key=key)
        self._log_call(d, conn, op, payload, key, rule, res)
        if res.status == "malformed" and reattempt_on_malformed:
            res = conn.call(op, payload, idempotency_key=key)  # same key: safe because upstream is idempotent
            self._log_call(d, conn, op, payload, key, "ADR-007: one same-key re-attempt after unreadable response", res)
        self.store.ledger_put(key, res)
        return res

    @staticmethod
    def _summ(r: ConnectorResult) -> dict:
        return {"status": r.status, "http_status": r.http_status, "error": r.error.model_dump() if r.error else None,
                "data_keys": sorted(r.data)[:12], "request_id": r.request_id, "latency_ms": r.latency_ms}

    def _log_call(self, d: Declaration, conn: Any, op: str, payload: dict, key: str, rule: str, r: ConnectorResult) -> None:
        self._rec(d, decision=f"call:{op}", rule=rule, connector=r.connector, action="tool_call",
                  recipient=r.source, input_source="connector", tool_call={"operation": op, "payload": payload, "idempotency_key": key},
                  tool_response={**self._summ(r), "data": r.data, "raw_excerpt": r.raw_excerpt}, result=r.status)

    # ------------------------------------------------------------------ intake
    def new_declaration(self, user_id: str = "user-1", declaration_id: str | None = None) -> Declaration:
        d = Declaration(declaration_id=declaration_id or f"decl-{uuid.uuid4().hex[:8]}", user_id=user_id)
        self.store.put(d)
        self._rec(d, decision="declaration_created", rule="new declaration starts in INTAKE", action="create")
        self._refresh(d)
        return d

    def receive_user_turn(self, d: Declaration, text: str | None, *, interrupted: bool = False,
                          source: str = "user_voice") -> None:
        text = text or ""
        self.last_user_text[d.declaration_id] = text
        if text.strip():
            d.language = F.detect_language(text)
        kind = "silence" if not text.strip() else ("interrupted" if interrupted else "speech")
        self._rec(d, decision=f"user_turn:{kind}", rule="input recorded before any decision", input=text,
                  input_source=source, action="receive", result="n/a")

    def _refresh(self, d: Declaration) -> None:
        """Recompute the single open field and move INTAKE <-> AWAITING_USER. Never clears a set field."""
        if d.state not in (State.INTAKE, State.AWAITING_USER) or d.open_field == "payment":
            return
        if d.group_size and d.min_group_size is None:
            d.min_group_size = d.group_size  # default all-or-nothing; stated in the read-back
        missing = required_fields_present(d)
        if d.state == State.AWAITING_USER and d.open_field and d.open_field not in missing:
            d.open_field = None
            self._go(d, State.INTAKE, rule="field supplied: AWAITING_USER->INTAKE")
        if missing:
            new_open = missing[0]
            if d.state == State.INTAKE:
                d.open_field = new_open
                self._go(d, State.AWAITING_USER, rule=f"required field missing or ambiguous: {new_open}")
            else:
                d.open_field = new_open
        self.store.put(d)

    def set_field(self, d: Declaration, name: str, evidence: str, decided_by: str = "llm") -> dict:
        user_text = self.last_user_text.get(d.declaration_id, "")
        norm = lambda s: re.sub(r"\s+", " ", s.strip().lower())  # noqa: E731
        if d.state not in (State.INTAKE, State.AWAITING_USER):
            return refuse(f"fields cannot be changed in state {d.state.value}")
        if name not in F.PARSEABLE_FIELDS:
            return refuse(f"unknown field {name!r}; allowed: {list(F.PARSEABLE_FIELDS)}")
        if not evidence.strip() or norm(evidence) not in norm(user_text):
            self._rec(d, decision="field_rejected", rule="evidence must be a verbatim span of the user's last turn",
                      decided_by=decided_by, input=evidence, input_source="user_voice", action=f"set_field:{name}",
                      result="refused")
            return refuse("evidence is not a verbatim part of what the user just said")
        p = F.parse_field(name, evidence, today=self.today, catalogue=self.catalogue)
        if p.status != "ok":
            d.field_notes[name] = p.status
            opts = p.extra.get("options")
            self._rec(d, decision=f"field_{p.status}", rule=f"parser: {p.detail}", decided_by=decided_by, input=evidence,
                      input_source="user_voice", action=f"set_field:{name}", result="refused",
                      tool_response={"status": p.status, "options": opts})
            if p.status == "ambiguous" and name in required_fields_present(d):
                d.open_field = d.open_field or name
            self._refresh(d)
            return refuse(p.detail or p.status, status=p.status, options=opts, field=name)
        current = self._current(d, name)
        if current not in (None, {}, p.value):
            if not _CHANGE_RE.search(user_text):
                self._rec(d, decision="field_change_refused", rule="a set field changes only on an explicit correction",
                          decided_by=decided_by, input=evidence, input_source="user_voice", action=f"set_field:{name}",
                          result="refused")
                return refuse("field already set; change only on an explicit user correction")
        changed = current != p.value
        self._store_field(d, name, p)
        d.field_notes.pop(name, None)
        if changed and (d.readback_presented or d.confirmed_by_user):
            d.readback_presented = d.confirmed_by_user = False
        self._rec(d, decision="field_stored" if changed else "field_unchanged", rule="parser ok; deterministic store",
                  decided_by=decided_by, input=evidence, input_source="user_voice", action=f"set_field:{name}",
                  tool_response={"value": p.value}, result="success")
        self._refresh(d)
        return ok(field=name, value=p.value)

    @staticmethod
    def _current(d: Declaration, name: str) -> Any:
        return {"event": d.event_id, "date": d.date, "group_size": d.group_size, "min_group_size": d.min_group_size,
                "max_price": d.max_price_paise, "time_window": d.hard_constraints or None}.get(name)

    def _store_field(self, d: Declaration, name: str, p: F.FieldParse) -> None:
        if name == "event":
            d.event_id, d.event_name = p.value, p.extra["name"]
            d.fulfilment = next(e.get("fulfilment", "digital") for e in self.catalogue if e["event_id"] == p.value)
        elif name == "date":
            d.date = p.value
        elif name == "group_size":
            if d.min_group_size is None or d.min_group_size == d.group_size:
                d.min_group_size = None  # re-default from the new group size
            d.group_size = p.value
        elif name == "min_group_size":
            d.min_group_size = min(p.value, d.group_size or p.value)
        elif name == "max_price":
            d.max_price_paise = p.value
        elif name == "time_window":
            d.hard_constraints = {**d.hard_constraints, **p.value}

    def event_options(self, d: Declaration) -> list[str] | None:
        """Names of catalogue events that the user's last words matched ambiguously."""
        p = F.parse_event(self.last_user_text.get(d.declaration_id, ""), self.catalogue)
        return p.extra.get("options") if p.status == "ambiguous" else None

    def ask_user(self, d: Declaration, question: str, decided_by: str = "llm") -> dict:
        if question.count("?") > load_policy("voice")["max_questions_per_turn"]:
            self._rec(d, decision="message_blocked", rule="one question per turn", decided_by=decided_by,
                      action="ask_user", recipient="user", tool_response=question, result="refused")
            return refuse("ask exactly one question per turn")
        try:
            self.say(d, question, "ask the single open question", decided_by)
        except ValueError as e:
            return refuse(str(e))
        return ok(turn_ended=True)

    def report_to_user(self, d: Declaration, message: str, decided_by: str = "llm") -> dict:
        try:
            self.say(d, message, "report without asserting unconfirmed actions", decided_by)
        except ValueError as e:
            return refuse(str(e))
        return ok(turn_ended=True)

    def present_readback(self, d: Declaration, decided_by: str = "code") -> dict:
        if d.state != State.INTAKE or required_fields_present(d):
            return refuse("read-back only when all required fields are set")
        d.readback_presented = True
        self.store.put(d)
        return self.ask_user(d, M.readback(d), decided_by)

    def confirm_readback(self, d: Declaration, user_confirmed: bool, decided_by: str = "llm") -> dict:
        if d.state != State.INTAKE or not d.readback_presented:
            return refuse("no read-back is pending")
        if not user_confirmed:
            return self.cancel(d, "user declined the read-back", decided_by=decided_by)
        d.confirmed_by_user = True
        self._go(d, State.VALIDATED, rule="validator passed AND user confirmed the read-back", input="user said yes",
                 input_source="user_voice", decided_by=decided_by)
        return ok(state=d.state.value)

    # ------------------------------------------------------------------ authorise
    def request_authorisation(self, d: Declaration, decided_by: str = "llm") -> dict:
        if d.state != State.VALIDATED:
            return refuse(f"authorisation requires VALIDATED, state is {d.state.value}")
        self._go(d, State.AUTHORISING, rule="max_price is an unambiguous integer paise value", decided_by=decided_by)
        amount = mandate_amount_paise(d.group_size, d.max_price_paise)
        res = self._call(d, self.c.pine_labs, "create_mandate", {
            "customerReference": d.user_id, "amount": {"value": amount, "currency": "INR"},
            "paymentMethod": "RESERVE_PAY"}, "create_mandate", "money.yaml: mandate = group_size * max_price")
        if res.status in ("success", "duplicate") and res.data.get("authorizationId"):
            d.mandate_id, d.mandate_paise = res.data["authorizationId"], amount
            self._go(d, State.AUTHORISED, rule="mandate connector confirmed with authorizationId", connector=res.connector,
                     result=res.status)
            self._go(d, State.WAITING_FOR_WINDOW, rule="automatic after AUTHORISED")
            self.say(d, M.msg_authorised(d), "state-derived confirmation of a confirmed mandate")
            return ok(state=d.state.value, turn_ended=True)
        d.open_field = "payment"
        self._go(d, State.AWAITING_USER, rule="authorisation failed; ask the user about payment", connector=res.connector,
                 result=res.status)
        self.say(d, M.question_for(d), "tell the truth about the failed authorisation")
        return refuse("authorisation failed", status=res.status, turn_ended=True)

    # ------------------------------------------------------------------ cancel / unwind
    def _unwind(self, d: Declaration) -> tuple[list[str], list[str]]:
        """Release in order hold -> mandate. Returns (confirmed_released, unconfirmed)."""
        done, unconfirmed = [], []
        if d.hold_id and not d.hold_released:
            r = self._call(d, self.c.inventory, "release_hold", {"hold_id": d.hold_id}, "unwind_hold", "release hold first")
            if r.status == "success":
                d.hold_released = True
                done.append("the slot hold")
            else:
                unconfirmed.append("the slot hold")
        if d.mandate_id and not d.mandate_released:
            r = self._call(d, self.c.pine_labs, "release_mandate", {"authorizationId": d.mandate_id},
                           "unwind_mandate", "release mandate second")
            if r.status == "success":
                d.mandate_released = True
                done.append("your reserved amount")
            else:
                unconfirmed.append("your reserved amount")
        self.store.put(d)
        return done, unconfirmed

    def cancel(self, d: Declaration, reason: str, decided_by: str = "llm", source: str = "user_voice") -> dict:
        if d.state in TERMINAL:
            return refuse(f"already {d.state.value}")
        if d.state not in PRE_CONFIRMED:
            msg = "That booking is already confirmed, so cancelling it needs a refund request, which I cannot do yet."
            self.say(d, msg, "cancel after confirmation is out of scope")
            return refuse("cancel after confirmation is a separate refund flow", turn_ended=True)
        done, unconf = self._unwind(d)
        d.terminal_reason = reason
        self._go(d, State.CANCELLED, rule="cancellation honoured immediately before CONFIRMED", input=reason,
                 input_source=source, decided_by=decided_by)
        self.say(d, M.msg_cancelled(d, done, unconf), "state-derived cancellation notice")
        return ok(state=d.state.value, turn_ended=True)

    # ------------------------------------------------------------------ events after authorisation
    def on_event(self, d: Declaration, event: dict) -> dict:
        """Human/inventory events. Duplicate event ids are acknowledged and ignored."""
        eid = event.get("event_id") or f"{event.get('type')}-{len(d.processed_event_ids)}"
        if eid in d.processed_event_ids:
            self._rec(d, decision="event_duplicate_ignored", rule="duplicate event ids are ignored", input=event,
                      input_source="human_event", action="ignore", result="duplicate")
            return ok(ignored=True)
        d.processed_event_ids.append(eid)
        self._rec(d, decision=f"event:{event.get('type')}", rule="external event received", input=event,
                  input_source="human_event", action="receive")
        t = event.get("type")
        if t == "window_open":
            return self.on_window_open(d, event.get("release_id"))
        if t == "window_end":
            return self.on_window_end(d)
        if t == "user_cancel":
            return self.cancel(d, "user cancelled", decided_by="code", source="human_event")
        return refuse(f"unknown event type {t!r}")

    def _fail(self, d: Declaration, why: str) -> dict:
        done, unconf = self._unwind(d)
        unwound = ("Released: " + ", ".join(done) + ". " if done else "") + \
                  ("I could not confirm release of: " + ", ".join(unconf) + "; please check with your payment provider."
                   if unconf else "")
        d.terminal_reason = why
        self._go(d, State.FAILED, rule="unrecoverable connector failure; reversible effects reversed", result="failure")
        self.say(d, M.msg_failed(d, why, unwound.strip()), "tell the truth about the failure")
        return refuse(why, state=d.state.value)

    def _release_by_payment(self, d: Declaration, why: str) -> dict:
        was_hold = bool(d.hold_id)
        done, unconf = self._unwind(d)
        d.terminal_reason = why
        self._go(d, State.RELEASED, rule="hold and mandate released after failure", result="failure")
        self.say(d, M.msg_released(d, why, was_hold and "the slot hold" in done, "your reserved amount" in done),
                 "tell the truth about the failure")
        return refuse(why, state=d.state.value)

    def on_window_open(self, d: Declaration, release_id: str | None = None) -> dict:
        if d.state != State.WAITING_FOR_WINDOW:
            return refuse(f"window_open ignored in state {d.state.value}")
        bal = self._call(d, self.c.pine_labs, "get_mandate_balance", {"authorizationId": d.mandate_id},
                         "balance_before_allocation", "verify mandate still live before allocating")
        need = mandate_amount_paise(d.group_size, d.max_price_paise)
        if bal.status != "success" or bal.data.get("status") != "ACTIVE" or bal.data["balance"]["value"] < need:
            return self._fail(d, "I could not verify your reserved amount is still active")
        if not release_id:
            lr = self._call(d, self.c.inventory, "list_releases", {"event_id": d.event_id, "date": d.date},
                            "list_releases", "find the release for the declared event and date")
            rels = lr.data.get("releases") if lr.status == "success" else None
            if lr.status != "success":
                return self._fail(d, "the inventory system did not give a readable answer")
            if not rels:
                self._go(d, State.ALLOCATING, rule="window opened")
                self._go(d, State.UNALLOCATED, rule="no release exists for that event and date")
                return self._finish_unallocated(d, "no release exists for that date")
            release_id = rels[0]["release_id"]
        d.release_id = release_id
        rel = self._call(d, self.c.inventory, "get_release", {"release_id": release_id}, "get_release",
                         "read slots, capacity and price of the release")
        if rel.status != "success":
            return self._fail(d, "the inventory system did not give a readable answer")
        self._go(d, State.ALLOCATING, rule="window opened; balance verified", input={"release_id": release_id},
                 input_source="human_event")
        slots = [Slot(s["slot_id"], s["capacity"], s["price_per_person_paise"], s["starts_at"]) for s in rel.data["slots"]]
        order = sorted(slots, key=lambda s: (s.starts_at, s.price_per_person_paise))
        bid = Bid(d.declaration_id, d.user_id, tuple(s.slot_id for s in order), d.group_size, d.min_group_size or d.group_size,
                  d.max_price_paise, d.allocations_last_30d, True, dict(d.hard_constraints))
        results = allocate(slots, [bid, *self.competitors], release_id, rel.data["opens_at"])
        mine = next(r for r in results if r.declaration_id == d.declaration_id)
        self.last_allocation = mine
        self._rec(d, decision="allocation", rule="DIFD seeded fair draw (docs/allocation.md)", action="allocate",
                  tool_response={"seed": mine.seed, "order": [r.declaration_id for r in results],
                                 "mine": mine.model_dump()}, result=mine.status)
        if mine.status == "UNALLOCATED":
            self._go(d, State.UNALLOCATED, rule=mine.reason)
            return self._finish_unallocated(d, mine.reason)
        if mine.status == "WAITLISTED":
            self._go(d, State.WAITLISTED, rule=mine.reason)
            self.say(d, M.msg_waitlisted(d, mine.reason), "state-derived waitlist notice")
            return ok(state=d.state.value)
        self._go(d, State.ALLOCATED, rule=mine.reason)
        candidates = [(mine.slot_id, mine.group_size_allocated)] + [
            (s.slot_id, min(d.group_size, s.capacity)) for s in order
            if s.slot_id != mine.slot_id and s.price_per_person_paise <= d.max_price_paise
            and s.capacity >= (d.min_group_size or d.group_size)]
        return self._hold_and_pay(d, candidates, {s.slot_id: s for s in slots})

    def _finish_unallocated(self, d: Declaration, reason: str) -> dict:
        done, unconf = self._unwind(d)
        self._go(d, State.EXPIRED, rule="unallocated: mandate released")
        self.say(d, M.msg_unallocated(d, reason) if not unconf else M.msg_expired(d, False), "state-derived notice")
        return ok(state=d.state.value)

    def on_window_end(self, d: Declaration) -> dict:
        if d.state in (State.WAITLISTED, State.UNALLOCATED):
            done, unconf = self._unwind(d)
            self._go(d, State.EXPIRED, rule="window ended without allocation; mandate released")
            self.say(d, M.msg_expired(d, not unconf), "state-derived notice")
            return ok(state=d.state.value)
        self._rec(d, decision="window_end_ignored", rule=f"nothing to expire in {d.state.value}", action="ignore")
        return ok(ignored=True)

    def _hold_and_pay(self, d: Declaration, candidates: list[tuple[str, int]], slots: dict[str, Slot]) -> dict:
        ttl = load_policy("money")["hold_ttl_s"]
        hold = None
        for slot_id, qty in candidates:
            if slot_id in d.failed_slots:
                continue
            res = self._call(d, self.c.inventory, "create_hold", {
                "release_id": d.release_id, "declaration_id": d.declaration_id, "slot_id": slot_id,
                "quantity": qty, "ttl_s": ttl}, f"hold:{slot_id}", "place a time-boxed hold before any charge",
                reattempt_on_malformed=True)
            if res.status in ("success", "duplicate") and res.data.get("hold_id"):
                hold = res
                break
            if res.status == "failure" and (res.http_status or 0) < 500:
                d.failed_slots.append(slot_id)
                self._go(d, State.ALLOCATING, rule="hold refused; try next acceptable slot", connector=res.connector, result=res.status)
                self._go(d, State.ALLOCATED, rule="next acceptable slot chosen deterministically")
                continue
            return self._fail(d, "the inventory system did not give a usable answer when placing the hold")
        if hold is None:
            self._go(d, State.WAITLISTED, rule="every acceptable slot refused the hold")
            self.say(d, M.msg_waitlisted(d, "the slots were taken while I tried to hold them"), "state-derived waitlist notice")
            return ok(state=d.state.value)
        slot = slots[hold.data["slot_id"]]
        d.hold_id, d.slot_id = hold.data["hold_id"], slot.slot_id
        d.allocated_group_size, d.slot_price_paise = hold.data["quantity"], hold.data["price_per_unit_paise"]
        d.slot_time = slot.starts_at[11:16]
        self._go(d, State.HOLD_PLACED, rule="inventory connector confirmed hold with hold_id", connector=hold.connector,
                 result=hold.status)
        chk = self._call(d, self.c.inventory, "get_hold", {"hold_id": d.hold_id}, "check_hold", "hold must be alive before charging")
        if chk.status != "success":
            return self._fail(d, "I could not verify that the slot hold is still valid")
        if chk.data["status"] != "active":
            return self._release_by_payment(d, "the slot hold expired before payment")
        charge = d.allocated_group_size * d.slot_price_paise
        okc, why = charge_within_limits(charge, d.group_size, d.max_price_paise, d.mandate_paise or 0)
        if not okc:
            return self._release_by_payment(d, f"charge blocked by policy ({why})")
        self._go(d, State.PAYMENT_PENDING, rule="charge only after hold (money.yaml charge_only_after_hold)")
        pay = self._call(d, self.c.pine_labs, "execute_charge", {
            "authorizationId": d.mandate_id, "amount": {"value": charge, "currency": "INR"},
            "reference": d.declaration_id}, "execute_charge", "charge actual price, never above ceiling*group",
            reattempt_on_malformed=True)
        if pay.status == "failure" and (pay.http_status or 0) < 500:
            return self._release_by_payment(d, "the payment was declined")
        if pay.status not in ("success", "duplicate") or not pay.data.get("payment_id"):
            return self._fail(d, "I could not confirm whether the payment went through, so I did not book")
        d.payment_result, d.payment_id = pay, pay.data["payment_id"]
        bk = self._call(d, self.c.inventory, "confirm_booking", {
            "hold_id": d.hold_id, "declaration_id": d.declaration_id, "payment_id": d.payment_id,
            "amount_paise": charge}, "confirm_booking", "booking needs venue confirmation", reattempt_on_malformed=True)
        if bk.status not in ("success", "duplicate") or not bk.data.get("booking_ref"):
            rf = self._call(d, self.c.pine_labs, "refund", {"payment_id": d.payment_id}, "refund_after_failed_booking",
                            "venue did not confirm; reverse the charge")
            return self._release_by_payment(d, "the venue did not confirm the booking" +
                                            ("" if rf.status == "success" else " and I could not confirm the refund"))
        d.inventory_result, d.booking_ref = bk, bk.data["booking_ref"]
        self._go(d, State.CONFIRMED, rule="inventory AND payment connectors both confirmed", connector=bk.connector, result=bk.status)
        self.say(d, M.msg_confirmed(d), "state-derived message after CONFIRMED")
        rel = self._call(d, self.c.pine_labs, "release_mandate", {"authorizationId": d.mandate_id}, "release_residual_mandate",
                         "release unused part of the mandate")
        d.mandate_released = rel.status == "success"
        if d.fulfilment == "physical":
            self.say(d, "This one is a physical pass. I need a delivery pincode to arrange shipping. What is your pincode?",
                     "physical fulfilment needs an address")
            return ok(state=d.state.value)
        self._go(d, State.CLOSED, rule="digital booking confirmed and user notified")
        return ok(state=d.state.value)

    def fulfil(self, d: Declaration, pincode: str) -> dict:
        """Delhivery MOCK: serviceability -> create shipment. Physical passes only."""
        if d.state != State.CONFIRMED or d.fulfilment != "physical":
            return refuse("fulfilment applies to CONFIRMED physical bookings only")
        sv = self._call(d, self.c.delhivery, "check_serviceability", {"filter_codes": pincode}, "serviceability", "check before shipping")
        if sv.status != "success" or not sv.data.get("delivery_codes"):
            self.say(d, "That pincode is not serviceable for delivery. Please give another pincode.", "tell the truth about serviceability")
            return refuse("non-serviceable pincode")
        sh = self._call(d, self.c.delhivery, "create_shipment", {"shipments": [{"order": d.booking_ref, "pin": pincode}]},
                        "create_shipment", "ship the confirmed physical pass")
        if sh.status != "success":
            self.say(d, "I could not create the shipment. Your booking is confirmed, but delivery is not arranged yet.", "tell the truth")
            return refuse("shipment failed")
        d.shipment_waybill = sh.data["packages"][0]["waybill"]
        self._go(d, State.FULFILMENT_PENDING, rule="Delhivery mock confirmed shipment with waybill", connector=sh.connector)
        self.say(d, f"Your pass is on its way. Waybill {d.shipment_waybill}.", "state-derived message")
        self._go(d, State.CLOSED, rule="confirmed and fulfilment created")
        return ok(state=d.state.value)
