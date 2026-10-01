# ADR-002: Allocator not auction, capacity checked at assignment

Status: accepted (2026-10-01)

## Context

Speed-based allocation collapses when everyone automates (The Ken's premise).

## Decision

Declared-Interest Fair Draw: seeded weighted permutation, serial assignment (docs/allocation.md). Eligibility excludes
capacity so full slots WAITLIST instead of becoming UNALLOCATED (deviation from plan section 5.1).

## Consequences

Reproducible and auditable; needs a source of allocation history for weights (fixtures today).
