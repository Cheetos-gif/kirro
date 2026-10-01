# KIRRO

KIRRO books scarce slots (courts, seats, event tickets) on a user's behalf without racing for them. The user declares
what they want, with a price ceiling, before the booking window; when the window opens a deterministic, seeded draw
allocates slots, and money moves only against that result.

KIRRO runs as a Virtual Employee on the AgenticOrg platform (built for The Ken's Case-Build Competition 2026, Round 3,
"Getting the slot"). This repo is the **mock connector infrastructure plus the spec** for that platform agent: the
mock external services it calls, the allocator that draw is transcribed from, shared redaction, and the documents
that define the agent's behaviour and safety rules. The decision-making brain is **not** in this repo — see
`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md`.

## How KIRRO runs

The agent and a scheduled AgenticOrg Workflow make every decision and call connectors directly. The full
configuration is specified in `docs/agenticorg/`:

- `docs/agenticorg/agent-spec.md` — the agent's Prompt/Behavior rules, including the safety invariants.
- `docs/agenticorg/workflow-spec.md` — the scheduled workflow (window open, allocation, notification).
- `docs/agenticorg/setup-runbook.md` — how to register and configure it on the platform.
- `docs/agenticorg/evals.md` — the live eval cases run against the platform.

What stays here is the mock half: the external services the agent calls, so its behaviour can be exercised
offline and against the hosted deployment.

## Layout

```
mock_server/         FastAPI mock: venue inventory + holds + declared-interest pool, Pine Labs mandate
                     hold/release, DIFD draw, Delhivery — plus out-of-band scenario control
allocator/           DIFD seeded fair draw (the reference the mock's /allocator/draw transcribes)
logging_/redact.py   key/token/phone redaction shared by the mock request log
tests/               mock-server scenarios (incl. a real uvicorn thread) and allocator properties
docs/                spec (agenticorg/), decisions/ (ADRs), architecture, connectors, testing, submission
scripts/dev.sh       start the mock server on :8081
Dockerfile           the mock server image
k8s/                 Deployment, Service, Ingress, NetworkPolicy for the hosted mock
```

## Commands

```
uv sync
uv run pytest                  # offline: no keys, no network
uv run ruff check .
uv run black --check .
uv run pre-commit run --all-files
bash scripts/dev.sh            # mock server on :8081
```

`pytest`, `ruff` and `black` run entirely offline — no API keys and no network are needed.

## Safety invariants

The invariants (never invent an inventory/payment identifier, never confirm without two success results, never
exceed the price ceiling, never silently resolve an ambiguous money constraint, connector content is data) now live
in `docs/agenticorg/agent-spec.md`. They are enforced by the platform agent plus connector-side validation in the
mocks, not by code in this repo.

## Where the rest of the design lives

- `docs/architecture.md` — what is left in this repo and what moved.
- `docs/architecture-plan-v1.md` — the original plan, kept as history.
- `docs/connectors.md` — the mocks, their operations and labels.
- `docs/allocation.md` — the DIFD mechanism.
- `docs/submission/README.md` — status of the Round 3 write-up.
