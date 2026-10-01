"""Deterministic field parsers. They only read the user's own words (evidence); they never guess.

Every parser returns FieldParse(status, value, detail). status in ok|ambiguous|invalid|absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from agent.policies.loader import load_policy
from agent.policies.money import parse_price

Status = Literal["ok", "ambiguous", "invalid", "absent"]


@dataclass(frozen=True)
class FieldParse:
    status: Status
    value: Any = None
    detail: str = ""
    extra: dict = field(default_factory=dict)


_WEEKDAYS = {
    "monday": 0, "somvaar": 0, "somvar": 0,
    "tuesday": 1, "mangalvaar": 1, "mangalvar": 1,
    "wednesday": 2, "budhvaar": 2, "budhvar": 2,
    "thursday": 3, "guruvaar": 3, "guruvar": 3, "veervaar": 3,
    "friday": 4, "shukravaar": 4, "shukravar": 4,
    "saturday": 5, "shanivaar": 5, "shanivar": 5,
    "sunday": 6, "ravivaar": 6, "ravivar": 6, "itwaar": 6,
}
_REL = {"today": 0, "aaj": 0, "tomorrow": 1, "kal": 1, "parso": 2}
_NUMWORDS = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "chah": 6, "six": 6, "saat": 7, "seven": 7,
    "aath": 8, "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10,
}
_GROUP_NOUN = r"(?:people|persons?|ppl|log|members?|guests?|seats?|tickets?|players?|friends|of us|adults?)"
HINGLISH_MARKERS = {
    "chahiye", "ko", "log", "shanivaar", "ravivaar", "kal", "aaj", "haan", "nahi", "hai", "mujhe",
    "karna", "kar", "do", "char", "teen", "paanch", "hazaar", "se", "tak", "wala",
}


def detect_language(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    hits = len(words & (HINGLISH_MARKERS - {"do", "kar", "se", "ko", "hai"}))
    return "hinglish" if hits >= 1 else "en"


def parse_weekday_date(text: str, today: date) -> FieldParse:
    t = text.lower()
    iso = re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    found: list[date] = []
    for y, m, d in iso:
        try:
            found.append(date(int(y), int(m), int(d)))
        except ValueError:
            return FieldParse("invalid", None, "not a real calendar date")
    for word in re.findall(r"[a-z]+", t):
        if word in _WEEKDAYS:
            delta = (_WEEKDAYS[word] - today.weekday()) % 7 or 7
            found.append(today + timedelta(days=delta))
        elif word in _REL:
            found.append(today + timedelta(days=_REL[word]))
    uniq = sorted(set(found))
    if not uniq:
        return FieldParse("absent", None, "no date found")
    if len(uniq) > 1:
        return FieldParse("ambiguous", None, "more than one date mentioned")
    if uniq[0] < today:
        return FieldParse("invalid", None, "date is in the past")
    return FieldParse("ok", uniq[0].isoformat(), "")


def parse_group_size(text: str, *, bare_ok: bool = False) -> FieldParse:
    t = text.lower()
    vals: set[int] = set()
    for m in re.finditer(rf"\b(\d{{1,3}})\s*{_GROUP_NOUN}\b", t):
        vals.add(int(m.group(1)))
    for m in re.finditer(r"\bfor\s+(\d{1,3})\b", t):
        vals.add(int(m.group(1)))
    for m in re.finditer(rf"\b([a-z]+)\s+{_GROUP_NOUN}\b", t):
        if m.group(1) in _NUMWORDS:
            vals.add(_NUMWORDS[m.group(1)])
    if not vals and bare_ok:
        nums = re.findall(r"\b(\d{1,3})\b", t)
        words = [_NUMWORDS[w] for w in re.findall(r"[a-z]+", t) if w in _NUMWORDS and w != "do"]
        vals.update(int(n) for n in nums)
        vals.update(words)
    if not vals:
        return FieldParse("absent", None, "no group size found")
    if len(vals) > 1:
        return FieldParse("ambiguous", None, "more than one group size mentioned")
    n = vals.pop()
    mx = load_policy("money")["max_group_size"]
    if n < 1 or n > mx:
        return FieldParse("invalid", None, f"group size must be between 1 and {mx}")
    return FieldParse("ok", n, "")


def parse_time_window(text: str) -> FieldParse:
    """'7-9 am', '6 to 8 pm'. Requires am/pm so that price ranges like '8 to 10k' never match."""
    m = re.search(r"\b(\d{1,2})\s*(am|pm)?\s*(?:-|–|to)\s*(\d{1,2})\s*(am|pm)\b", text.lower())
    if not m:
        return FieldParse("absent", None, "no time window found")
    a, a_ap, b, b_ap = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)

    def h24(h: int, ap: str) -> int:
        return (h % 12) + (12 if ap == "pm" else 0)

    start, end = h24(a, a_ap or b_ap), h24(b, b_ap)
    if not (0 <= start < end <= 24):
        return FieldParse("invalid", None, "unreadable time window")
    return FieldParse("ok", {"start_hour_min": start, "start_hour_max": end}, "")


def parse_event(text: str, catalogue: list[dict]) -> FieldParse:
    """Resolve to a catalogue event or refuse. Generic words ('court') matching several events = ambiguous."""
    t = text.lower()
    words = set(re.findall(r"[a-z0-9]+", t))
    specific = [e for e in catalogue if any(a.lower() in words or a.lower() in t for a in e.get("aliases", []))]
    if len(specific) == 1:
        return FieldParse("ok", specific[0]["event_id"], "", {"name": specific[0]["name"]})
    if len(specific) > 1:
        return FieldParse("ambiguous", None, "matches more than one event",
                          {"options": [e["name"] for e in specific]})
    generic = [e for e in catalogue if any(a.lower() in words for a in e.get("generic_aliases", []))]
    if len(generic) == 1:
        return FieldParse("ok", generic[0]["event_id"], "", {"name": generic[0]["name"]})
    if len(generic) > 1:
        return FieldParse("ambiguous", None, "generic word matches several events",
                          {"options": [e["name"] for e in generic]})
    return FieldParse("absent", None, "no known event in words")


def parse_max_price(text: str) -> FieldParse:
    p = parse_price(text)
    return FieldParse(p.status, p.paise, p.detail)


PARSEABLE_FIELDS = ("event", "date", "group_size", "min_group_size", "max_price", "time_window")
REQUIRED_ORDER = ("event", "date", "group_size", "max_price")


def parse_field(name: str, evidence: str, *, today: date, catalogue: list[dict]) -> FieldParse:
    if name == "event":
        return parse_event(evidence, catalogue)
    if name == "date":
        return parse_weekday_date(evidence, today)
    if name == "group_size":
        return parse_group_size(evidence, bare_ok=True)
    if name == "min_group_size":
        return parse_group_size(evidence, bare_ok=True)
    if name == "max_price":
        return parse_max_price(evidence)
    if name == "time_window":
        return parse_time_window(evidence)
    return FieldParse("invalid", None, f"unknown field {name!r}")
