import random

from allocator.engine import Bid, Slot, allocate
from allocator.fairness import fairness_weight, make_seed, weighted_order

SLOTS = [
    Slot("s1", 4, 25000, "2026-10-03T07:00:00Z"),
    Slot("s2", 4, 28000, "2026-10-03T08:00:00Z"),
    Slot("s3", 4, 90000, "2026-10-03T18:00:00Z"),
]


def bid(i, n=2, price=30000, prior=0, user=None, **kw):
    return Bid(f"d{i}", user or f"u{i}", ("s1", "s2", "s3"), n, kw.pop("min", n), price, prior, **kw)


def run(bids, slots=SLOTS):
    return {r.declaration_id: r for r in allocate(slots, bids, "rel1", "2026-10-02T06:00:00Z")}


def test_deterministic_and_input_order_independent():
    bids = [bid(i) for i in range(6)]
    a = run(bids)
    shuffled = bids[:]
    random.Random(3).shuffle(shuffled)
    b = run(shuffled)
    assert {k: v.model_dump() for k, v in a.items()} == {k: v.model_dump() for k, v in b.items()}


def test_capacity_respected():
    res = run([bid(i) for i in range(10)])
    used = {}
    for r in res.values():
        if r.slot_id:
            used[r.slot_id] = used.get(r.slot_id, 0) + r.group_size_allocated
    assert all(used[s.slot_id] <= s.capacity for s in SLOTS if s.slot_id in used)
    assert sum(1 for r in res.values() if r.status == "WAITLISTED") > 0  # 10*2 > 8 eligible seats


def test_ceiling_respected_and_unallocated_when_nothing_fits():
    res = run([bid(1, price=20000)])
    assert res["d1"].status == "UNALLOCATED" and res["d1"].slot_id is None
    res = run([bid(2, price=26000)])
    assert res["d2"].slot_id == "s1"  # s2 (28000) and s3 are above the ceiling


def test_min_group_blocks_partial_but_partial_allowed_when_min_lower():
    tiny = [Slot("s1", 3, 25000, "2026-10-03T07:00:00Z")]
    assert run([bid(1, n=4, min=4)], tiny)["d1"].status == "WAITLISTED"
    r = run([bid(2, n=4, min=2)], tiny)["d2"]
    assert r.status == "ALLOCATED" and r.group_size_allocated == 3 and "partial" in r.reason


def test_time_constraint_hard_filter():
    r = run([bid(1, constraints={"start_hour_min": 8, "start_hour_max": 9})])["d1"]
    assert r.slot_id == "s2"


def test_one_win_per_user_per_release():
    res = run([bid(1, user="same"), bid(2, user="same")])
    assert sorted(r.status for r in res.values()) == ["ALLOCATED", "UNALLOCATED"]


def test_speed_buys_nothing_and_fairness_favours_unlucky():
    wins = {"fresh": 0, "lucky": 0}
    one = [Slot("s1", 1, 25000, "2026-10-03T07:00:00Z")]
    for n in range(300):
        bids = [Bid("fresh", "f", ("s1",), 1, 1, 30000, 0), Bid("lucky", "l", ("s1",), 1, 1, 30000, 3)]
        r = {x.declaration_id: x for x in allocate(one, bids, f"rel{n}", "t")}
        for k in wins:
            wins[k] += r[k].status == "ALLOCATED"
    assert wins["fresh"] > wins["lucky"] * 2  # weight 1 vs 1/4


def test_seed_and_weights():
    assert make_seed("a", "b") == make_seed("a", "b") != make_seed("a", "c")
    assert fairness_weight(0) == 1 and fairness_weight(3) == 0.25
    assert weighted_order([("a", 1), ("b", 1)], make_seed("x", "y")) == weighted_order(
        [("b", 1), ("a", 1)], make_seed("x", "y")
    )
