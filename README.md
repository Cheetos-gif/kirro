# KIRRO

KIRRO books scarce slots (courts, seats, event tickets) on a user's behalf without racing for them. The user declares
what they want, with a price ceiling, before the booking window. When the window opens a deterministic, seeded draw
allocates slots, and money moves only against that result. Built for The Ken's Case-Build Competition 2026, Round 3
("Getting the slot"), to run on Pine Labs' agent platform with Gnani voice and Pine Labs payments.

## Why

If everyone runs the fastest-finger-first bot, speed stops mattering and the inventory owner just gets load. KIRRO
changes the mechanism: interest is declared up front, allocation ignores arrival time inside the window, and the
payment is a capped authorisation rather than a checkout race. It still works if every other user also automates.

## How it works

```
declare -> verify -> authorise -> wait -> allocate -> capture/release -> confirm
```

- An LLM talks to the user and picks among legal actions. Code decides everything that matters: field validity, price
  parsing, state transitions, allocation, retries, and whether an external call succeeded.
- Connectors return provenance-carrying results. The agent never invents a booking and never says "booked" before the
  venue and the payment rail both confirmed.
- Mock external services (venue inventory and holds, Pine Labs mandate, Delhivery) run in `mock_server/` with
  scenarios (no inventory, timeout, malformed, payment failure, ...) that a test harness sets out of band.

Python 3.11+, FastAPI, Pydantic v2, httpx, pytest, ruff, Anthropic SDK for the local runner. No database.

## Setup

```
uv sync
cp .env.example .env     # only needed for live mode or real connectors
```

## Commands

```
uv run pytest                          # offline: no key, no network
uv run ruff check .
bash scripts/dev.sh                    # mock :8081 and core :8080
uv run python scripts/chat.py          # chat with the offline stub; type /open to open the window
bash scripts/run_eval.sh all           # ten eval cases, offline stub policy
bash scripts/run_eval.sh E08 --mode live   # real model (needs ANTHROPIC_API_KEY; KIRRO_MODEL defaults to claude-sonnet-5-5)
bash scripts/reconstruct.sh evals/runs/<run>/log.jsonl     # decision log -> Q1.2 table
```

## Layout

```
AGENTS.md            how Claude sessions work in this repo
agent/               state machine, engine, tools, policies, prompt versions, runners, core API
allocator/           DIFD seeded fair draw
connectors/          ConnectorResult contract, gnani/, pine_labs/, delhivery/, inventory/, registry
mock_server/         mock venue, Pine Labs and Delhivery APIs plus scenario control
logging_/            decision log, redaction, Q1.2 reconstruction
evals/               10 cases, checks.py, harness.py, runs/ (artifacts)
config/              connector modes
docs/                architecture, allocation, connectors, evals, testing, demo, decisions/, submission/
tests/               unit, contract, mock server, state, eval harness
scripts/             dev, eval, reconstruct, chat
web/                 Next.js app: landing page, web declare flow, auth-gated judge/ops dashboard (see web/README.md)
.claude/             project subagents and skills
```

## Web interface

`web/` is a separate Next.js app (deployed on Vercel) that talks to KIRRO Core server-side only — see
`web/README.md` and `AGENTS.md` → "Web interface". It is not required to run KIRRO: voice (Gnani) remains the
primary declaration channel, and `scripts/chat.py` remains the primary local dev/demo loop.

## Eval workflow

1. Pick a case in `evals/cases/` (E01 happy path to E10 group cannot be fulfilled).
2. `scripts/run_eval.sh E0X` writes `evals/runs/<ts>_p<prompt>_E0X_<slug>/{log.jsonl,transcript.md,verdict.json}`.
3. Offline runs prove the harness, guards and mocks. Live runs test the prompt. A failure goes into `docs/testing.md`
   and, if it needs a prompt change, becomes a new version under `agent/system-prompt/` (see AGENTS.md).

## Current limitations

- Only prompt v0 exists. No live (LLM) eval has been run yet, so there are no recorded prompt failures. Offline
  results come from a deterministic stub, not a model.
- Real Pine Labs P3P sandbox, Gnani Inya and Delhivery connectors are not implemented; they need credentials and
  platform configuration. They return an explicit NOT_CONFIGURED failure. See `docs/connectors.md`.
- The Pine Labs mock collapses the real two-party flow (challenge, client token, server capture) into one call.
- The Pine Labs platform (AgenticOrg) binding of the tool surface is not done and is unverified.
- Waitlist promotion after a cancellation, group split-pay links, and Delhivery Maps reachability constraints are
  not built. "Any day" or flexible dates are treated as not understood.
- Questions are English-only in the stub and in code-generated messages; the live model mirrors Hinglish by prompt.
- State is in memory per process unless `KIRRO_DATA_DIR` is set; with it, declarations, the idempotency ledger and
  the decision log persist as JSON/JSONL under that directory and reload on startup (the Kubernetes deployment
  mounts a PVC for this). Still one process only — the store is not shared across replicas.
