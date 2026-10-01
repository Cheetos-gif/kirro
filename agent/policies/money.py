"""Deterministic money parsing. The LLM never decides an amount.

parse_price() turns the user's own words into integer paise or refuses:
  - "300", "Rs 300", "Rs. 1,200", "8k", "2 lakh"  -> OK
  - "8 to 10k, ideally 8", "around 300", "300 or 400" -> AMBIGUOUS (never guessed)
  - no number -> ABSENT; out of policy bounds -> INVALID
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from agent.policies.loader import load_policy

Status = Literal["ok", "ambiguous", "invalid", "absent"]

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|hazaar|hazar|lakh|lac)?\b", re.I)
_HEDGE = re.compile(
    r"\b(ideally|preferably|around|about|approx(?:imately)?|roughly|maybe|perhaps|between|or|ya|"
    r"somewhere)\b|\d\s*[-–—]\s*\d",
    re.I,
)
_MULT = {"k": 1000, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "lakh": 100000, "lac": 100000}


@dataclass(frozen=True)
class PriceParse:
    status: Status
    paise: int | None = None
    detail: str = ""


def parse_price(text: str) -> PriceParse:
    if not text or not text.strip():
        return PriceParse("absent", None, "empty input")
    numbers = []
    for m in _NUM.finditer(text):
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        numbers.append(value * _MULT.get(unit, 1))
    if not numbers:
        return PriceParse("absent", None, "no number found")
    if len(numbers) > 1 or _HEDGE.search(text):
        return PriceParse(
            "ambiguous",
            None,
            "range, hedge or multiple amounts; ask for one maximum per person",
        )
    return validate_ceiling_paise(int(round(numbers[0] * 100)))


def validate_ceiling_paise(paise: object) -> PriceParse:
    """Validate an already-parsed per-person ceiling in paise."""
    pol = load_policy("money")
    if isinstance(paise, bool) or not isinstance(paise, int):
        return PriceParse("invalid", None, "ceiling must be an integer number of paise")
    if paise < pol["min_ceiling_per_person_paise"]:
        return PriceParse("invalid", None, "ceiling below policy minimum")
    if paise > pol["max_ceiling_per_person_paise"]:
        return PriceParse("invalid", None, "ceiling above policy maximum")
    return PriceParse("ok", paise, "")


def mandate_amount_paise(group_size: int, max_price_paise: int) -> int:
    pol = load_policy("money")
    return group_size * max_price_paise * int(pol["mandate_multiplier"])


def charge_within_limits(
    charge_paise: int, group_size: int, max_price_paise: int, mandate_paise: int
) -> tuple[bool, str]:
    """Deterministic guard used before any charge: never above ceiling*group or mandate."""
    if charge_paise <= 0:
        return False, "charge must be positive"
    if charge_paise > group_size * max_price_paise:
        return False, "charge exceeds declared per-person ceiling"
    if charge_paise > mandate_paise:
        return False, "charge exceeds mandate"
    return True, ""
