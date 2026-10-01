"""Deterministic offline policy. It plays the role of the LLM using the SAME tools and rules, so evals
can run structurally without an API key. It is not a model: it proves harness + engine + guards, not
prompt quality. Live mode (anthropic_policy.py) is what evaluates the prompt."""

from __future__ import annotations

import re

from agent.runner.session import HumanTurn, Session
from agent.tools import messages as M
from connectors.gnani.extract import extract_intake

_YES = re.compile(r"(?i)\b(yes|yeah|yep|haan|han|ha|ok|okay|sure|go ahead|confirm|correct|sahi|theek hai)\b")
_NO = re.compile(r"(?i)\b(no|nope|nahi|na|don'?t|do not)\b")
_STOP = re.compile(r"(?i)\b(cancel|stop|forget it|never ?mind|rehne do|band karo|nahi chahiye)\b")
_ORDER = ["time_window", "event", "date", "group_size", "max_price"]


class StubPolicy:
    name = "stub"

    def respond(self, s: Session, turn: HumanTurn) -> None:
        d, e, t = s.decl, s.engine, (turn.text or "")
        run = s.tools.execute
        if d.state.value in ("CANCELLED", "CLOSED", "FAILED", "RELEASED", "EXPIRED", "CONFIRMED"):
            run("report_to_user", {"message": "This request is finished. Tell me if you want to start a new one."})
            return
        if t.strip() and _STOP.search(t):
            run("cancel_declaration", {"reason": "user asked to stop"})
            return
        if d.state.value in ("WAITING_FOR_WINDOW", "WAITLISTED"):
            if t.strip():
                run(
                    "report_to_user",
                    {"message": "Your request is in. I will act when the window opens and tell you what happens."},
                )
            return
        ex = extract_intake(t, today=e.today, catalogue=e.catalogue, focus=d.open_field) if t.strip() else None
        cands = sorted(ex.candidates, key=lambda c: _ORDER.index(c.field)) if ex else []
        pending_readback = d.readback_presented and d.state.value == "INTAKE"
        if pending_readback and not cands:
            if _YES.search(t) and not _NO.search(t) and not turn.interrupted:
                if run("confirm_readback", {"user_confirmed": True}).get("ok"):
                    run("request_authorisation", {})
                return
            if _NO.search(t) and not turn.interrupted:
                run("confirm_readback", {"user_confirmed": False})
                return
        for c in cands:
            r = run("set_field", {"field": c.field, "evidence": c.evidence})
            if r.get("turn_ended"):
                return  # read-back was asked
        if d.state.value == "INTAKE" and d.readback_presented:
            run(
                "ask_user", {"question": M.readback(d)}
            )  # silence / interruption / unclear: repeat only the open question
            return
        opts = e.event_options(d) if d.open_field == "event" else None
        run("ask_user", {"question": M.question_for(d, options=opts)})
