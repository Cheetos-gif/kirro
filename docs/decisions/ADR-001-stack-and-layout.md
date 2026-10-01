# ADR-001: Stack and layout

Status: accepted (2026-10-01)

## Context

Hackathon, two people, one language preferred, Claude Code must modify everything quickly.

## Decision

Python 3.11+, uv, FastAPI, Pydantic v2, httpx, pytest, ruff, Anthropic SDK. JSON/JSONL on disk, no database. Top-level
packages use underscores (`pine_labs`, `mock_server`, `logging_`) because hyphenated directory names from the brief
cannot be imported; the brief's `connectors/external` was replaced by `connectors/inventory` (the real external
need is the venue). `package = false` in uv: this is an application, run from the repo root.

## Consequences

One toolchain, shared schemas between mock and clients, OpenAPI docs for free. No build step.
