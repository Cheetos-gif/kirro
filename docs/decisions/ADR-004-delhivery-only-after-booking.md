# ADR-004: Delhivery only after booking

Status: accepted (2026-10-01)

## Context

Delhivery is a competition-required mock; movie slots and courts are not shipped.

## Decision

Delhivery is used only for physical-pass fulfilment after CONFIRMED (`Engine.fulfil`): serviceability, create shipment.
Not in the core booking loop. Maps MCP reachability is a stretch goal, not built.

## Consequences

Minimal coupling; the primary demo uses digital inventory.
