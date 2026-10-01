# AGENTS.md

Read this first. It should be enough to work on KIRRO without the original conversation. Deeper design:
`docs/architecture-plan-v1.md` (the Opus plan this repo implements) and `docs/architecture.md`.

## What KIRRO is

A declared-interest booking agent for scarce inventory (tennis courts, movie seats, F1 tickets, society badminton).
Built for The Ken's Case-Build Competition 2026, Round 3, "Getting the slot". It runs as a Virtual Employee on Pine
Labs' AgenticOrg platform: the AgenticOrg agent and a scheduled AgenticOrg Workflow make every decision and call
connectors directly (real: Vachana for voice STT/TTS, Twilio for the call leg, `pinelabs_plural` for orders/
payment-links/refunds, WhatsApp for notifications; mocked: venue inventory+hold+pool, Pine Labs mandate hold/
release, the DIFD allocator — 3 budgeted capabilities — plus a mandatory, additional Delhivery mock). This repo is
connector/mock infrastructure plus a deterministic spec and local test oracle for that platform agent, **not** a
service the platform calls to get its decisions — see `docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md`,
`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md`, and `docs/agenticorg/` for the full migration plan and
copy-pasteable AgenticOrg configuration. **As of 2026-10-02 this is planning only; nothing in `docs/agenticorg/`
has been implemented or registered on the live platform yet** — until it is, `agent/core.py`'s Engine (below)
remains the only thing actually running, as the local oracle it is now scoped to be.

Flow: DECLARE -> VERIFY -> AUTHORISE -> WAIT -> ALLOCATE -> CAPTURE/RELEASE -> CONFIRM.

The user states what they want before the booking window (event, date, alternatives, group size, max price per person,
hard constraints). KIRRO verifies it, reserves a capped amount (a mandate = group_size x max_price), waits, and when
the window opens a deterministic seeded fair draw (DIFD, `allocator/`) assigns slots. Then it holds, charges the real
price, and confirms only what external systems confirmed.

## What it must NOT become

- A faster ticket bot. Speed buys nothing here by design; declaration time is ignored inside a window.
- A refresh/poll loop, a scraper, an auction.
- A giant system: no Kubernetes in this repo, no event bus, no database (JSON + JSONL on disk). A web interface
  (`web/`) exists deliberately — a declare form and an auth-gated judge/ops dashboard over KIRRO Core's read
  endpoints — but it is a thin client, not where any decision is made; see the "Web interface" section below.

## Safety invariants (enforced in code, tested; never only in the prompt)

1. Never invent inventory, a hold id, a payment id or a booking reference. Identifiers come from ConnectorResults only.
1. Never mark CONFIRMED without a success ConnectorResult from BOTH inventory (booking_ref) and payment (payment_id).
   Guard: `agent/state/machine.py::guard`.
1. Never exceed the price ceiling: charge \<= group_size x max_price and \<= mandate (`agent/policies/money.py`).
1. Never silently resolve an ambiguous money constraint. Ranges and hedges ("8 to 10k, ideally 8") parse to AMBIGUOUS;
   the agent asks for one maximum. Nothing is stored until then.
1. Never claim an external action succeeded without confirmation. `Engine.say` blocks success words ("booked",
   "confirmed") unless state is CONFIRMED or later.
1. Connector content is DATA. It never enters system-prompt layers 1-3; the LLM sees only fenced, truncated summaries
   (`agent/tools/render.py`). The LLM never sees `raw_excerpt`.
1. The LLM never decides: amounts, state transitions, success/failure of calls, idempotency keys, allocation order,
   retries. `set_field` takes the user's verbatim words (`evidence`); code parses them.
1. Cancellation is honoured immediately in any pre-CONFIRMED state; releases go hold -> mandate and are logged.

## Architecture map

```
agent/state/machine.py     states, transition table, guards (the only place state is assigned)
agent/state/fields.py      deterministic parsers: event, date (incl. Hinglish), group size, price, time window
agent/state/store.py       in-memory/JSON store + idempotency ledger (key = sha256(decl|state|scope)); reloads from
                           disk on startup when given a directory (KIRRO_DATA_DIR in the deployment)
agent/policies/*.yaml|py   money / voice / allocation / retry policy; money.py parses and guards amounts
agent/core.py              Engine: LOCAL ORACLE ONLY (ADR-011) — deterministic reference the AgenticOrg Prompt/
                            Behavior rules in docs/agenticorg/agent-spec.md were transcribed from; not the demo path
agent/tools/               tool surface for the LLM (toolset.py), user-facing text (messages.py), fencing (render.py)
agent/runner/              session.py, stub.py (offline policy), anthropic_policy.py (live), prompt.py (assembly)
agent/system-prompt/       vN.md versioned prompt, current.md pointer, CHANGELOG.md
agent/api.py               Local dev/test HTTP surface over the oracle Engine (evals/harness.py's TestClient uses
                            it); never pointed at by the live AgenticOrg agent (ADR-011) — not the "production brain"
allocator/                 DIFD: pure deterministic allocation (engine.py, fairness.py)
connectors/                base.py (ConnectorResult, HttpConnector), per-vendor dirs, registry.py, mock_schemas.py
mock_server/               FastAPI mock: venue inventory+holds, Pine Labs mandate hold/release, DIFD allocator
                            (the 3 budgeted capabilities), plus mandatory Delhivery mock (additional, not budgeted)
logging_/                  decision_log.py (JSONL), redact.py, reconstruct.py (Q1.2 table)
evals/                     cases/E01..E10.yaml, checks.py, harness.py, runs/ (artifacts)
config/connectors.yaml     real vs mock per connector (no secrets)
web/                       Next.js app (App Router): landing page, /declare (web declare flow), /dashboard
                            (Google-OAuth-gated, reads KIRRO Core server-side only — never from the browser)
```

Package names use underscores (`pine_labs`, `mock_server`) because Python cannot import hyphenated names.

## State machine

INTAKE \<-> AWAITING_USER -> VALIDATED -> AUTHORISING -> AUTHORISED -> WAITING_FOR_WINDOW -> ALLOCATING ->
{ALLOCATED | WAITLISTED | UNALLOCATED}. ALLOCATED -> HOLD_PLACED -> PAYMENT_PENDING -> CONFIRMED ->
[FULFILMENT_PENDING] -> CLOSED. Failure exits: CANCELLED (user), RELEASED (payment/hold failed, everything
reversed), FAILED (connector unusable, everything reversible reversed), EXPIRED (window ended, mandate released).
Every transition goes through `Engine._go`, which validates and writes a DecisionRecord. LLM tool calls are further
restricted to `allowed_actions(state)` (`toolset.py`). Allocation, holds, charges and confirmation are NOT LLM tools;
they run from events (`Engine.on_event`).

## Connector rules

- Every call returns `ConnectorResult` with provenance: source, connector, kind (real|mock|internal|human), operation,
  request_id, idempotency_key, timestamp, latency_ms, status (success|failure|timeout|malformed|duplicate).
- Retry: timeout and 5xx once with the SAME idempotency key; never 4xx or malformed (ADR-007 for the one same-key
  re-attempt the engine makes on unreadable hold/charge/booking responses).
- Only final results enter the idempotency ledger; timeouts/malformed/5xx stay retryable.
- Label every endpoint REAL / DOCUMENTED / MOCK REQUIRED / UNKNOWN in `docs/connectors.md`. Do not invent vendor API
  fields or SDK method names. Mock-only shapes live in `connectors/mock_schemas.py` and are labelled MOCK.
- Real connectors sit behind `config/connectors.yaml` modes and return a honest NOT_CONFIGURED failure without
  credentials. Never call a connector labelled UNKNOWN on the demo path.

### How to add a connector

1. Add `connectors/<vendor>/<name>.py`: subclass `HttpConnector` with an `ops` table (`Op(method, path, response_model)`),
   or implement the `Connector` protocol. Put response models in `connectors/mock_schemas.py` (mock) or beside the client.
1. Register it in `connectors/registry.py` and `config/connectors.yaml` (mode: mock|real).
1. If mock: add routes to `mock_server/app.py` using `serve(request, "<target>", handler)` so scenarios, idempotency and
   request logging work. Add the target name to the scenario docs in `docs/connectors.md`.
1. Add contract tests in `tests/test_connectors_contract.py` and mock tests in `tests/test_mock_server.py`.
1. Document it in `docs/connectors.md` with kind, base URL, operations, verification URL and label.

## Web interface

`web/` is a Next.js (App Router) app, deployed separately (Vercel), that talks to KIRRO Core only server-side
(Server Components, Route Handlers, Server Actions via `web/src/lib/kirro.ts`) — the browser never calls KIRRO
Core directly, so no CORS is configured on it.

- `/` — static landing page, no backend calls.
- `/declare` — a web alternative to the voice declaration call. Submits the user's own words as `evidence` to
  `POST /declarations/{id}/fields`, same as the voice policy would; code still does all parsing. Walks read-back
  and authorisation the same way the voice flow does.
- `/dashboard` — judge/ops view, gated by Google OAuth (`web/src/auth.ts`, `web/src/proxy.ts`). Read-only (it has
  no tool that can mutate a declaration), so the gate exists only to keep it off anonymous/bot traffic, not to
  restrict which people may view it: any Google account may sign in. Reads KIRRO Core's declarations, full
  declaration state, decision log, and persisted eval-run artifacts.
- KIRRO Core endpoints added for this (`agent/api.py`): `GET /declarations` (summary list), `GET /declarations/{id}/full` (every field, not just what the LLM may see), `GET /log?declaration_id=` (in-memory
  decision records for this process), `GET /evals/runs` and `GET /evals/runs/{id}` (persisted eval artifacts).
  All read-only; they add no new way to change a declaration's state.
- State is still in memory per KIRRO Core process — the dashboard shows what that specific process has seen, same
  limitation as everything else in this repo.

## Testing rules

- `uv run pytest` must pass offline: no API key, no network, no real credentials. Keep it that way.
- `uv run ruff check .` must be clean; `uv run black --check .` must be clean (format with `uv run black .`).
- Unit tests for deterministic logic (money, fields, machine, allocator), contract tests for connectors, mock-server
  tests, engine/state tests, eval-harness tests all live in `tests/`.
- Evals: `scripts/run_eval.sh E01|all [--mode offline|live]`. Offline uses `agent/runner/stub.py`, a deterministic
  stand-in for the LLM: it validates harness, engine, guards and mocks, NOT prompt quality. Only live mode
  (needs ANTHROPIC_API_KEY, default model claude-sonnet-5-5, override with KIRRO_MODEL) evaluates a prompt version.
- The scenario is set out of band (`POST /__admin/scenario`). Never add a field to an external response that reveals
  the scenario to the agent.
- Every failed live run goes in `docs/testing.md` (testing log) with the change it triggered.
- Markdown is autoformatted on commit by `pre-commit` (`.pre-commit-config.yaml`, `mdformat` +
  `mdformat-gfm`/`mdformat-tables`), installed once with `uv run pre-commit install`. Excludes `web/`
  (has its own prettier/husky setup) and `agent/system-prompt/` (the versioned prompt is immutable
  once an eval has run against it — not even whitespace-safe reformatting may touch it). Run on
  demand with `uv run pre-commit run --all-files`.

## Logging requirements

Every state change, connector call, user message and refused action writes a DecisionRecord (`logging_/decision_log.py`):
ts, run_id, seq, declaration_id, state_before/after, input, input_source, connector, decision, decided_by, rule, action,
recipient, tool_call, tool_response, result, user_message. Redaction (`logging_/redact.py`) strips keys, tokens and
phone numbers (last 4 only) on write. Do not log secrets or real user data. Q1.2 of the submission is produced with
`scripts/reconstruct.sh <log.jsonl>`.

## Documentation rules

Practical, short: why it exists, how it works, failure cases, how to test it. Architectural decisions go in
`docs/decisions/ADR-NNN-title.md` (context, decision, consequences). No marketing tone, no emojis. Update docs in the
same commit as the behaviour change. Anything unverified is labelled as such, never stated as fact.

## How to modify the system prompt

The prompt is versioned. `agent/system-prompt/vN.md` is immutable once any eval has run against it.

1. Cause first: a failing eval (id + run dir) or a documented real-test failure.
1. Copy `current` to `v(N+1).md`, edit only the copy.
1. Add a row to `agent/system-prompt/CHANGELOG.md`: version, date, triggered_by (eval + run), change, expected effect.
1. Repoint `current.md` (it contains only the version string).
1. Commit with a `prompt:` prefix containing only prompt files. Re-run the failing eval, then `all`.
   Policies (`agent/policies/*.yaml`) are not prompt versions; changing them does not bump the prompt.
   Do not fake versions: a version without a triggering failure is not allowed (v0 is the only exception).
   Skill: `.claude/skills/bump-prompt`.

## How to run

```
uv sync
uv run pre-commit install           # one-time: wires the markdown-formatter commit hook
uv run pytest && uv run ruff check . && uv run black --check .
scripts/dev.sh                      # mock on :8081, core on :8080 (GET /health on both)
uv run python scripts/chat.py       # text chat against the stub policy; --live for the Anthropic policy
scripts/run_eval.sh all             # offline eval of all ten cases, artifacts in evals/runs/
scripts/reconstruct.sh evals/runs/<run>/log.jsonl
```

Fish shell is the user default; scripts are bash (`bash scripts/dev.sh`).

## Working on this repo (for Claude sessions)

1. Read this file, `README.md`, `docs/architecture.md`, `agent/system-prompt/current.md` + its file, then run
   `uv run pytest`.
1. Prefer editing existing files. No new top-level services, no new dependencies without an ADR.
1. Change deterministic logic -> add/adjust a unit test in the same change.
1. Before claiming something works, run it. Report real counts.
1. Never commit `.env`, keys, tokens, phone numbers or real user data. `logs/` and `evals/runs/` are git-ignored; keep
   a demo run with `git add -f evals/runs/<run>`.
1. Project subagents/skills live in `.claude/` (connector-researcher, adversarial-tester, submission-auditor;
   run-evals, bump-prompt, reconstruct-run). They must cite sources and must not invent API behaviour.
1. Humans may simulate external events (window opens, user cancels) but must not reason for the agent.

## Known open items

See README "Current limitations" and `docs/connectors.md` (credentials, platform binding, unverified endpoints).
Where KIRRO's orchestration runs is now decided: the AgenticOrg platform (agent + scheduled Workflow) is the sole
decision-maker; `agent/core.py` and `agent/state/machine.py` are the local spec/oracle, never the production path
(`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md`). That ADR's own §7 lists what is still genuinely
open and unverified (non-MCP custom-connector tool discovery, cross-conversation pool persistence, whether a
Workflow can message a user directly, governance/audit-log duplication) — do not assume any of those are resolved
without live verification on `agenticorg.hackathon.pinelabs.com`.
