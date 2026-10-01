"""Redaction applied before anything is logged. Secrets, tokens and phone numbers never reach logs."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY = re.compile(r"(api[-_]?key|secret|token|authorization|password|client[-_]?id|grantex|credential)", re.I)
_PHONE_KEY = re.compile(r"(phone|mobile|msisdn)", re.I)
_PHONE_VAL = re.compile(r"(?<![\d-])(\+\d{1,3}[ -]?\d{5}[ -]?\d{5}|\+?\d{10,13})(?![\d-])")
_BEARER = re.compile(r"(Bearer|Token|Payment)\s+[A-Za-z0-9._~+/=-]{8,}")


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return "******" + digits[-4:] if len(digits) >= 4 else "[PHONE]"


def redact_text(text: str) -> str:
    text = _BEARER.sub(lambda m: f"{m.group(1)} [REDACTED]", text)
    return _PHONE_VAL.sub(lambda m: _mask_phone(m.group(1)), text)


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY.search(k):
                out[k] = "[REDACTED]"
            elif isinstance(k, str) and _PHONE_KEY.search(k) and isinstance(v, (str, int)):
                out[k] = _mask_phone(str(v))
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
