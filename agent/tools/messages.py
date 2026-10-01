"""Code-generated user-facing text. Outcome messages state only what connector results confirmed.
Amounts are formatted from integer paise by code. No external free text (labels) is interpolated."""

from __future__ import annotations

import re

from agent.schemas.models import Declaration

# Words that assert a completed external action. Only allowed once state is CONFIRMED or later.
CLAIM_RE = re.compile(r"(?i)\b(booked|confirmed|confirmation|booking (is|has been) (done|complete|successful))\b")
POST_CONFIRM_STATES = {"CONFIRMED", "FULFILMENT_PENDING", "CLOSED"}


def rupees(paise: int) -> str:
    whole, frac = divmod(paise, 100)
    return f"Rs {whole:,}" + (f".{frac:02d}" if frac else "")


def question_for(
    d: Declaration, catalogue_names: dict[str, str] | None = None, options: list[str] | None = None
) -> str:
    f = d.open_field
    note = d.field_notes.get(f or "", "")
    if f == "event":
        if options:
            return f"Which one do you mean: {' or '.join(options)}?"
        return "Which event or venue do you want?"
    if f == "date":
        if note == "ambiguous":
            return "I heard more than one date. Which single date do you want?"
        if note == "invalid":
            return "I could not use that date. Which date do you want?"
        return "Which date do you want?"
    if f == "group_size":
        return "How many people is this for?"
    if f == "max_price":
        if note == "ambiguous":
            return "I heard a range or more than one amount. What is the single maximum you will pay per person?"
        if note == "invalid":
            return "I could not use that amount. What is the maximum you will pay per person?"
        return "What is the maximum you will pay per person?"
    if f == "payment":
        return "I could not reserve that amount on your payment method. Do you want to try again, or cancel?"
    return "Could you say that again?"


def readback(d: Declaration) -> str:
    n, mn = d.group_size or 0, d.min_group_size or d.group_size or 0
    group = f"{n} people" + (" (all of them or none)" if mn == n else f" (at least {mn})")
    window = ""
    c = d.hard_constraints
    if "start_hour_min" in c:
        window = f", starting between {c['start_hour_min']:02d}:00 and {c['start_hour_max']:02d}:00"
    hold = rupees((d.group_size or 0) * (d.max_price_paise or 0))
    return (
        f"To confirm: {d.event_name} on {d.date}{window}, {group}, at most "
        f"{rupees(d.max_price_paise or 0)} per person. I will reserve up to {hold} and charge only the real price. "
        f"Shall I go ahead?"
    )


def msg_authorised(d: Declaration) -> str:
    return (
        f"Done. I have reserved up to {rupees(d.mandate_paise or 0)} on your payment method; nothing is charged yet. "
        f"I will act when the booking window opens."
    )


def msg_confirmed(d: Declaration) -> str:
    total = (d.allocated_group_size or 0) * (d.slot_price_paise or 0)
    part = ""
    if d.allocated_group_size != d.group_size:
        part = f" This is for {d.allocated_group_size} of your {d.group_size} people, which is within your minimum."
    return (
        f"Booking confirmed by the venue: {d.event_name} on {d.date} at {d.slot_time or ''}, "
        f"{d.allocated_group_size} people. Reference {d.booking_ref}. Charged {rupees(total)}.{part}"
    )


def msg_waitlisted(d: Declaration, reason: str) -> str:
    return (
        f"I could not get you a slot in this round ({reason}). You are on the waitlist. No booking has been "
        f"made and nothing has been charged. Your reserved amount stays held until the window ends."
    )


def msg_unallocated(d: Declaration, reason: str) -> str:
    return f"No slot fits your limits ({reason}). No booking was made and nothing was charged, and your reserved amount is released."


def msg_expired(d: Declaration, released: bool) -> str:
    tail = (
        "Your reserved amount is released."
        if released
        else "I could not confirm that your reserved amount was released; please check with your payment provider."
    )
    return f"The window has ended without a slot. No booking was made and nothing was charged. {tail}"


def msg_released(d: Declaration, why: str, released_hold: bool, released_mandate: bool) -> str:
    bits = []
    if d.hold_id:
        bits.append("the slot hold is released" if released_hold else "I could not confirm the slot hold was released")
    bits.append(
        "your reserved amount is released"
        if released_mandate
        else "I could not confirm your reserved amount was released; please check with your payment provider"
    )
    return f"It did not go through: {why}. No booking was made. " + "; ".join(bits).capitalize() + "."


def msg_failed(d: Declaration, why: str, unwound: str) -> str:
    return f"I hit a problem and stopped: {why}. No booking was made. {unwound}"


def msg_cancelled(d: Declaration, released: list[str], unconfirmed: list[str]) -> str:
    text = "Cancelled."
    if released:
        text += " Released: " + ", ".join(released) + "."
    if unconfirmed:
        text += (
            " I could not confirm release of: " + ", ".join(unconfirmed) + "; please check with your payment provider."
        )
    if not released and not unconfirmed:
        text += " Nothing had been reserved or charged."
    return text
