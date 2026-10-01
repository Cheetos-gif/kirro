"""The tool surface the LLM sees (names final, per plan section 13). Handlers route to Engine.

Deliberate narrowing vs the plan: set_field takes the user's own words (`evidence`), not a value.
Code parses them. The model therefore cannot introduce an amount, date or event the user did not say.
Allocation, holds, charging and confirmation are NOT tools; they run from events in code.
"""

from __future__ import annotations

from typing import Any

from agent.core import Engine, refuse
from agent.schemas.models import Declaration, State
from agent.state.fields import PARSEABLE_FIELDS
from agent.state.machine import PRE_CONFIRMED, required_fields_present
from agent.tools import messages as M

TOOL_DEFS: list[dict] = [
    {
        "name": "set_field",
        "description": "Store one field the user just stated. Pass the exact words the user said as `evidence`; the system "
        "parses them. Rejected if the words are ambiguous (e.g. a price range) or not from the user's last turn.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": list(PARSEABLE_FIELDS)},
                "evidence": {"type": "string", "description": "verbatim words from the user's last turn"},
            },
            "required": ["field", "evidence"],
        },
    },
    {
        "name": "ask_user",
        "description": "Say exactly ONE question to the user (at most one '?'). Ends your turn. Ask only about the open field.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
    {
        "name": "confirm_readback",
        "description": "Record whether the user said yes or no to the read-back summary. Only after a read-back was asked.",
        "input_schema": {
            "type": "object",
            "properties": {"user_confirmed": {"type": "boolean"}},
            "required": ["user_confirmed"],
        },
    },
    {
        "name": "request_authorisation",
        "description": "Ask the system to reserve the user's capped amount. Only legal after the user confirmed the read-back.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_declaration",
        "description": "Cancel the declaration because the user asked to stop. Always honoured before a booking is confirmed.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    },
    {
        "name": "report_to_user",
        "description": "Tell the user something that is not a question. Never claim a booking, payment or release that a tool result has not confirmed.",
        "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
    },
    {
        "name": "get_state",
        "description": "Read the declaration state, confirmed fields, the single open field and the legal actions.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def allowed_actions(d: Declaration) -> list[str]:
    acts = ["get_state", "report_to_user"]
    if d.state in (State.INTAKE, State.AWAITING_USER):
        acts += ["set_field", "ask_user"]
        if d.state == State.INTAKE and d.readback_presented and not required_fields_present(d):
            acts.append("confirm_readback")
    if d.state == State.VALIDATED:
        acts.append("request_authorisation")
    if d.state in PRE_CONFIRMED:
        acts.append("cancel_declaration")
    return acts


def state_view(d: Declaration) -> dict:
    """What the model may know. No connector text, no ids it could misuse."""
    return {
        "state": d.state.value,
        "confirmed_fields": {
            k: v
            for k, v in {
                "event": d.event_name,
                "date": d.date,
                "group_size": d.group_size,
                "min_group_size": d.min_group_size,
                "max_price_per_person": M.rupees(d.max_price_paise) if d.max_price_paise is not None else None,
                "constraints": d.hard_constraints or None,
            }.items()
            if v is not None
        },
        "open_field": d.open_field,
        "open_field_note": d.field_notes.get(d.open_field or "", None),
        "readback_presented": d.readback_presented,
        "allowed_actions": allowed_actions(d),
    }


class ToolSet:
    """Binds tools to one declaration. `turn_ended` is set when a message has been said to the user."""

    def __init__(self, engine: Engine, declaration: Declaration):
        self.e, self.d = engine, declaration
        self.turn_ended = False

    def execute(self, name: str, args: dict[str, Any]) -> dict:
        if name not in allowed_actions(self.d) and name != "get_state":
            self.e._rec(
                self.d,
                decision="tool_refused",
                rule=f"{name} not legal in {self.d.state.value}",
                decided_by="llm",
                action=name,
                tool_call=args,
                result="refused",
            )
            return refuse(f"{name} is not legal in state {self.d.state.value}", allowed_actions=allowed_actions(self.d))
        if name == "get_state":
            return {"ok": True, **state_view(self.d)}
        if name == "set_field":
            r = self.e.set_field(self.d, args.get("field", ""), args.get("evidence", ""))
        elif name == "ask_user":
            r = self.e.ask_user(self.d, args.get("question", ""))
        elif name == "report_to_user":
            r = self.e.report_to_user(self.d, args.get("message", ""))
        elif name == "confirm_readback":
            r = self.e.confirm_readback(self.d, bool(args.get("user_confirmed")))
        elif name == "request_authorisation":
            r = self.e.request_authorisation(self.d)
        elif name == "cancel_declaration":
            r = self.e.cancel(self.d, args.get("reason", "user asked to cancel"))
        else:
            r = refuse(f"unknown tool {name!r}")
        if (
            name == "set_field"
            and r.get("ok")
            and self.d.state == State.INTAKE
            and not required_fields_present(self.d)
            and not self.d.readback_presented
        ):
            # deterministic read-back: code speaks it, so the wording and amounts come from validated fields
            r = {**r, **self.e.present_readback(self.d), "readback_asked": True}
        if r.get("turn_ended"):
            self.turn_ended = True
        return r
