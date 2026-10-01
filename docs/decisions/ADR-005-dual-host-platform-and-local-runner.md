# ADR-005: Dual host: platform and local runner

Status: superseded by ADR-010 (2026-10-02) — AgenticOrg tenant capabilities are no longer unknown; see
`docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md` for current platform-binding decisions.

## Context
The Pine Labs (AgenticOrg) tenant capabilities are unknown.

## Decision
The same Engine and tool surface run locally (stub or Anthropic policy) and behind `agent/api.py` for the platform.

## Consequences
Evals do not depend on the platform. Platform binding is a later, human-verified step.

## Note
The "platform binding is a later, human-verified step" consequence below is resolved by ADR-010's live inspection
of the AgenticOrg tenant (2026-10-02): connector catalog, registration mechanism, and governance pages are now
documented facts, not unknowns.
