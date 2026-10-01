# Allocation: Declared-Interest Fair Draw (DIFD)

## Why this exists

A race rewards the fastest automation, and when everyone has it, nobody gains. DIFD removes arrival time from the
outcome inside a window and gives people who recently got nothing a better chance.

## How it works (`allocator/engine.py`, `allocator/fairness.py`)

1. **Eligibility (hard filter)**: slot is in the declaration's acceptable set, price per person \<= max price,
   time-window constraint holds (`start_hour_min <= hour < start_hour_max`), mandate active.
1. **Weight**: `w = 1 / (1 + allocations_in_last_30_days)`.
1. **Seed**: `sha256(release_id + window_open_iso)`.
1. **Draw order**: Efraimidis-Spirakis weighted permutation (`key = u^(1/w)`), declarations sorted by id before drawing
   so the order depends only on ids, weights and seed.
1. **Serial assignment**: in draw order each declaration takes its first acceptable slot (preference = start time, then
   price) with enough remaining capacity. If remaining capacity is below group size but at least the minimum group
   size, a partial group is allocated and logged as partial.
1. **Waitlist**: eligible but capacity exhausted -> WAITLISTED. No eligible slot at all -> UNALLOCATED.
1. **Conflicts**: a user wins at most one declaration per release; the others are UNALLOCATED.

Deviation from the plan: capacity is checked at assignment, not in eligibility. The plan's eligibility rule
(`capacity >= min_group_size`) would make a full slot UNALLOCATED; with the change a full slot WAITLISTs the
declaration, which is correct because cancellations can free capacity.

The same pure function is exposed to AgenticOrg as `POST /allocator/draw` (see `docs/connectors.md`): the request
carries the release's slots (with remaining capacity) and the pool's bids, and the response is one
`AllocationResult` per bid. Nothing else calls it — the live agent's Window Allocation Workflow does.

## Properties (each has a test in `tests/test_allocator.py`)

Deterministic; independent of input order and arrival time; capacity-respecting; ceiling-respecting; fairness-improving
over rounds (fresh users win about 4x as often as users with 3 recent wins in a single-seat test).

## Worked example

Six declarations of 2 seats compete for a 4-seat slot. The seed fixes the weighted order; the first two get the slot,
the next four are WAITLISTED in draw order. Re-running with the same inputs gives the same answer; the seed and the
per-bid `draw_position` are in the draw response, so the Workflow can log the order it acted on.

## Not built

Waitlist promotion on cancellation/expired holds (TODO), history source for `allocations_last_30d` (demo fixtures only).

## How to test

`uv run pytest tests/test_allocator.py`
