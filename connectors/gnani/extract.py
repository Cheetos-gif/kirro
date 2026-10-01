"""Deterministic intake extractor (capability B in the plan). Turns transcript text into per-field
candidates with *heuristic* confidence. Gnani exposes no field confidence, so this is ours.

It finds evidence spans; the actual parsing/validation is done by agent.state.fields, which is also what
the engine applies when a field is set. So extraction can suggest, but only validation can store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from agent.state import fields as F

_PRICE_KW = re.compile(
    r"(?i)\b(max(?:imum)?|budget|under|up\s*to|upto|at most|not more than|ceiling|rs\.?|rupees?|inr)\b|₹"
)
_HEDGE_START = re.compile(r"(?i)^\s*(ideally|preferably|or|maybe|around|about|ya|lekin|but|if possible)\b")


@dataclass
class FieldCandidate:
    field: str
    status: str  # ok | ambiguous | invalid
    evidence: str
    value: object = None
    detail: str = ""
    confidence: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class IntakeExtraction:
    language: str
    candidates: list[FieldCandidate]

    def get(self, name: str) -> FieldCandidate | None:
        return next((c for c in self.candidates if c.field == name), None)


def _price_clause(text: str) -> str | None:
    segs = re.split(r"(?<=[,;])", text)
    for i, seg in enumerate(segs):
        if _PRICE_KW.search(seg):
            clause = seg
            j = i + 1
            while j < len(segs) and _HEDGE_START.match(segs[j]):
                clause += segs[j]
                j += 1
            return clause.strip(" ,;")
    return None


def extract_intake(text: str, *, today: date, catalogue: list[dict], focus: str | None = None) -> IntakeExtraction:
    text = text or ""
    cands: list[FieldCandidate] = []

    def add(name: str, evidence: str, p: F.FieldParse, conf: float) -> None:
        if p.status == "absent":
            return
        cands.append(
            FieldCandidate(name, p.status, evidence, p.value, p.detail, conf if p.status == "ok" else 0.0, p.extra)
        )

    add("event", text, F.parse_event(text, catalogue), 0.9)
    add("date", text, F.parse_weekday_date(text, today), 0.85)
    add("group_size", text, F.parse_group_size(text), 0.85)
    add("time_window", text, F.parse_time_window(text), 0.8)
    clause = _price_clause(text)
    if clause:
        add("max_price", clause, F.parse_max_price(clause), 0.9)
    # focused answer to a single open question: accept a bare reply for exactly that field
    if focus and text.strip() and not any(c.field == focus for c in cands):
        if focus == "max_price" and re.search(r"\d", text):
            add("max_price", text, F.parse_max_price(text), 0.7)
        elif focus in ("group_size", "min_group_size"):
            add(focus, text, F.parse_group_size(text, bare_ok=True), 0.7)
    return IntakeExtraction(F.detect_language(text), cands)
