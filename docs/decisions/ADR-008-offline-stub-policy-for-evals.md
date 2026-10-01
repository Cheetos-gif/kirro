# ADR-008: Offline stub policy for evals

Status: accepted (2026-10-01)

## Context
Tests and evals must run without an API key or network.

## Decision
`StubPolicy` is a deterministic stand-in for the LLM that calls the same tools; live mode uses `AnthropicPolicy`
(default claude-sonnet-5-5, KIRRO_MODEL override; no temperature, no forced tool_choice, per the Sonnet 5.5 API notes).

## Consequences
Offline green means harness, guards and mocks work, not that a prompt is good. Documented in README and docs/evals.md.
