# ADR-003: Mandate as authorisation, money never an LLM input

Status: accepted (2026-10-01)

## Context

The agent must never exceed a ceiling and must not decide money.

## Decision

Mandate = group_size x max_price (paise, integer). Charge guarded by `charge_within_limits`. `set_field` accepts the
user's verbatim words as evidence and code parses them, so the model cannot introduce an amount (stricter than the plan's
`max_price_paise: int` tool argument).

## Consequences

Prices the model could have normalised (e.g. '8k') are parsed by code; unusual phrasings may be refused and re-asked.
