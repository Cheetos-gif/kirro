"""Declared-Interest Fair Draw (DIFD). Pure, deterministic, no I/O. See docs/allocation.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent.schemas.models import AllocationResult
from allocator.fairness import fairness_weight, make_seed, weighted_order


@dataclass(frozen=True)
class Slot:
    slot_id: str
    capacity: int
    price_per_person_paise: int
    starts_at: str  # ISO 8601


@dataclass(frozen=True)
class Bid:
    declaration_id: str
    user_id: str
    acceptable_slot_ids: tuple[str, ...]  # preference order
    group_size: int
    min_group_size: int
    max_price_paise: int
    allocations_last_30d: int = 0
    mandate_active: bool = True
    constraints: dict = field(default_factory=dict, hash=False, compare=False)


def _start_hour(iso: str) -> int:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).hour


def eligible(bid: Bid, slot: Slot) -> bool:
    """Hard filter. Capacity is checked at assignment time, not here, so that a full slot
    still leaves the bidder WAITLISTED (capacity can grow through cancellations)."""
    if not bid.mandate_active or slot.slot_id not in bid.acceptable_slot_ids:
        return False
    if slot.price_per_person_paise > bid.max_price_paise:
        return False
    c = bid.constraints
    h = _start_hour(slot.starts_at)
    if "start_hour_min" in c and h < c["start_hour_min"]:
        return False
    if "start_hour_max" in c and h >= c["start_hour_max"]:
        return False
    return True


def allocate(slots: list[Slot], bids: list[Bid], release_id: str, window_open_iso: str) -> list[AllocationResult]:
    seed = make_seed(release_id, window_open_iso)
    remaining = {s.slot_id: s.capacity for s in slots}
    by_id = {s.slot_id: s for s in slots}
    order = weighted_order([(b.declaration_id, fairness_weight(b.allocations_last_30d)) for b in bids], seed)
    bid_by_id = {b.declaration_id: b for b in bids}
    winners_by_user: set[str] = set()
    results: dict[str, AllocationResult] = {}

    for pos, did in enumerate(order, start=1):
        bid = bid_by_id[did]
        elig = [by_id[sid] for sid in bid.acceptable_slot_ids if sid in by_id and eligible(bid, by_id[sid])]
        if not elig:
            results[did] = AllocationResult(
                declaration_id=did,
                slot_id=None,
                group_size_allocated=0,
                status="UNALLOCATED",
                draw_position=pos,
                seed=seed,
                reason="no acceptable slot within ceiling and constraints",
            )
            continue
        if bid.user_id in winners_by_user:
            results[did] = AllocationResult(
                declaration_id=did,
                slot_id=None,
                group_size_allocated=0,
                status="UNALLOCATED",
                draw_position=pos,
                seed=seed,
                reason="user already allocated another declaration in this release",
            )
            continue
        chosen = None
        for slot in elig:  # preference order
            rem = remaining[slot.slot_id]
            if rem >= bid.group_size:
                chosen, n = slot, bid.group_size
                break
            if rem >= bid.min_group_size and rem > 0:
                chosen, n = slot, rem
                break
        if chosen is None:
            best = max(remaining[s.slot_id] for s in elig)
            results[did] = AllocationResult(
                declaration_id=did,
                slot_id=None,
                group_size_allocated=0,
                status="WAITLISTED",
                draw_position=pos,
                seed=seed,
                reason=f"eligible but capacity exhausted (best remaining {best}, needs {bid.min_group_size})",
            )
            continue
        remaining[chosen.slot_id] -= n
        winners_by_user.add(bid.user_id)
        partial = n < bid.group_size
        results[did] = AllocationResult(
            declaration_id=did,
            slot_id=chosen.slot_id,
            group_size_allocated=n,
            status="ALLOCATED",
            draw_position=pos,
            seed=seed,
            reason="partial group accepted" if partial else "assigned",
        )
    return [results[d] for d in order]
