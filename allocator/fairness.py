"""Fairness weight and seeded weighted permutation (Efraimidis-Spirakis)."""

from __future__ import annotations

import hashlib
import random


def fairness_weight(allocations_in_window: int) -> float:
    return 1.0 / (1 + max(0, allocations_in_window))


def make_seed(release_id: str, window_open_iso: str) -> str:
    return hashlib.sha256((release_id + window_open_iso).encode()).hexdigest()


def weighted_order(items: list[tuple[str, float]], seed: str) -> list[str]:
    """items: (id, weight). Key = u ** (1/w); larger key first. Sorted by id first so the
    result depends only on (set of ids, weights, seed), never on input order or arrival time."""
    rng = random.Random(int(seed, 16))
    keyed = []
    for ident, w in sorted(items):
        u = rng.random() or 1e-12
        keyed.append((u ** (1.0 / w), ident))
    keyed.sort(key=lambda kv: (-kv[0], kv[1]))
    return [ident for _, ident in keyed]
