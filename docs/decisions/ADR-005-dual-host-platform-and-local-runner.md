# ADR-005: Dual host: platform and local runner

Status: accepted (2026-10-01)

## Context
The Pine Labs (AgenticOrg) tenant capabilities are unknown.

## Decision
The same Engine and tool surface run locally (stub or Anthropic policy) and behind `agent/api.py` for the platform.

## Consequences
Evals do not depend on the platform. Platform binding is a later, human-verified step.
