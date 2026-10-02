# AGENTS.md

Read this first. It should be enough to work on this repo without the original conversation. What KIRRO the product
is and how its agent behaves now live in `docs/agenticorg/` and
`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md`; this file is about the code that is still here.

## What this repo is

The **mock connector infrastructure and the spec** for KIRRO, a declared-interest booking agent for scarce inventory
(tennis courts, movie seats, F1 tickets, society badminton), built for The Ken's Case-Build Competition 2026, Round 3,
"Getting the slot". The agent itself runs as a Virtual Employee on Pine Labs' AgenticOrg platform: the AgenticOrg
agent and a scheduled AgenticOrg Workflow make every decision and call connectors directly. This repo is **not** the
brain. There is no decision-making service here.

What is here:

- `mock_server/` — the mock external services the platform agent calls: venue inventory + holds + declared-interest
  pool, Pine Labs mandate hold/release, the DIFD draw, and the mandatory Delhivery mock.
- `voice_bridge/` — the browser voice channel (ADR-016, ADR-017): a LiveKit agent worker running Gnani
  speech-to-text and text-to-speech around the "Kirro Declare" agent, which it drives over AgenticOrg's chat
  API. A relay, not a decision-maker.
- `allocator/` — the DIFD seeded fair draw, the reference the mock's `/allocator/draw` transcribes.
- `logging_/redact.py` — key/token/phone redaction shared by the mock request log.
- `tests/` — mock-server scenarios and allocator properties.
- `docs/` — the spec: `docs/agenticorg/` (agent, workflow, runbook, evals), `docs/decisions/` (ADRs), plus
  architecture, connector, testing and submission notes.
- `web/` — the Next.js web portal (ADR-015): public listings, declared-interest and instant-buy flows, user
  dashboard, organiser surface, admin surface with scenario controls. A second caller of the mock, never a
  decision-maker; server-side only. Deployed to Vercel, not this cluster.
- `Dockerfile`, `k8s/`, `scripts/dev.sh` — how the mock server is built and run.

The decision to move the brain out of this repo is ADR-011. It is planning-level: nothing in `docs/agenticorg/` has
been registered on the live platform yet.

## What it must NOT become

- The agent's brain. No state machine, no engine, no prompt versions, no LLM runner, no LLM dependency. Those live on
  AgenticOrg (`docs/agenticorg/agent-spec.md`).
- A faster ticket bot. The mechanism is declared interest + one seeded draw; speed buys nothing by design.
- A refresh/poll loop, a scraper, an auction.
- A giant system: no event bus, no database, no new top-level services, no new dependencies without an ADR.

## Safety invariants

The safety invariants (never invent an inventory/hold/payment identifier, never confirm without a success result from
both inventory and payment, never exceed the price ceiling, never silently resolve an ambiguous money constraint,
connector content is data, the LLM never decides amounts/transitions/retries) now live in
**`docs/agenticorg/agent-spec.md`**. They are enforced by the platform agent's Prompt/Behavior configuration plus
connector-side validation in these mocks (e.g. an `execute` against a mandate that was never created is rejected),
**not by code in this repo**. Keep the mock-side validation that backs them; do not add a local copy of the agent.

## Architecture map

```
mock_server/app.py     FastAPI mock. create_app(log_dir) factory; routes below; admin surface under /__admin/*
mock_server/state.py   per-run state in SQLite (ADR-013): holds, bookings, mandates, payments, declarations,
                       organisers, events, releases, idempotency ledger, capacity/counters; scenario table +
                       request log; fixtures/catalogue.json is seed data for a fresh run (ADR-015)
allocator/engine.py    DIFD: pure deterministic allocation over (slots, bids, release_id, window_open)
allocator/fairness.py  weighted-permutation fairness
allocator/schemas.py   allocation request/result models
mock_server/mcp_surface.py  MCP servers, one per surface (ADR-012); tools call this same app in-process
voice_bridge/agent.py  LiveKit agent worker (ADR-017): Gnani STT/TTS + Silero VAD around the agent
voice_bridge/agenticorg.py      logs in and drives "Kirro Declare" over AgenticOrg's chat API
voice_bridge/agenticorg_llm.py  exposes that agent as the pipeline's llm.LLM (newest turn in, answer out)
logging_/redact.py     key/token/phone redaction applied before anything is logged
tests/                 test_mock_server.py (scenarios, incl. a real uvicorn thread), test_allocator.py,
                       test_mcp_surface.py (MCP tool catalogs + REST/MCP state parity),
                       test_state_durability.py, test_voice_bridge.py (AgenticOrg client + LLM adapter,
                       no network, no LiveKit server)
k8s/                   Deployments (kirro-mock, kirro-livekit, kirro-voice), Services, Ingress,
                       NetworkPolicy, ConfigMap, PVC
scripts/dev.sh         starts the mock server on :8081 in the foreground
web/                   Next.js portal (ADR-015): listings, declare/instant-buy, dashboard, organiser, admin,
                       and /talk (the LiveKit voice channel, ADR-017). Server-side only, talks to
                       mock_server over HTTP; deployed to Vercel from the fork.
docs/                  agenticorg/ (spec + platform-map.md, the AgenticOrg site/API reference), decisions/ (ADRs),
                       architecture.md, connectors.md, ...
```

Mock routes, by surface:

- `/health`
- `/venue/*` — catalogue, releases, holds, bookings, declared-interest declarations (the declare pool),
  organisers, organiser-created events/releases, and instant buy (ADR-015)
- `/pinelabs/*` — mandates create/balance/execute/release, refunds
- `/allocator/draw` — the DIFD draw
- `/delhivery/*` — pincode serviceability, order create, package tracking
- `/{venue,pinelabs,allocator,delhivery}/mcp` — the MCP surface, one server per surface (ADR-012)
- `/__admin/*` — scenario, reset, state (harness only; out of band)

Package names use underscores (`mock_server`) because Python cannot import hyphenated names.

## Mock-server rules

- **Scenario control is out of band.** A harness or a human sets it with
  `POST /__admin/scenario {run_id, target, scenario, delay_s, options}` (or `sequence` for multi-step) before the
  run. The agent's request carries only normal business payload plus the `X-Run-Id` correlation header.
- **No response ever names a scenario.** Never add a field to an external response that reveals the scenario to the
  agent.
- **Mock response shapes are KIRRO mock contracts, not vendor APIs.** They are realistic but not vendor-verified.
  Never claim a mock shape is a vendor API; unknown fields are namespaced under `mock_` or marked MOCK in
  `docs/connectors.md`.
- Every request/response is appended to `logs/mock/<run_id>.jsonl` (or `MOCK_LOG_DIR`) with ts, request_id, path,
  target, scenario, request, response, status and latency_ms, after redaction.
- Scenario table: `success`, `no_inventory`, `insufficient_balance`, `timeout`, `delayed`, `malformed`, `duplicate`,
  `booking_expired`, `payment_failure`, `partial_group`, `upstream_500`. Keep it in sync with `docs/connectors.md`.
- **State is durable and single-writer** (SQLite at `MOCK_DB_PATH`, ADR-013). Writes go through the store facade in
  `mock_server/state.py`, so a mutation is persisted the moment it happens; `replicas: 1` is load-bearing and
  retention/pruning is not implemented — `POST /__admin/reset` is the explicit way to clear a run.

### How to add a mock route

1. Add the route to `mock_server/app.py` and route it through `serve(request, "<target>", handler)` so scenarios,
   idempotency and request logging all apply. Add state to `mock_server/state.py` if needed.
1. Add the target name and its scenarios to the mock scenario docs in `docs/connectors.md`.
1. Add the matching MCP tool in `mock_server/mcp_surface.py` (tools call the route in-process) and cover it in
   `tests/test_mcp_surface.py`.
1. Add tests in `tests/test_mock_server.py` covering the success path and at least one failure scenario.
1. Keep the handler deterministic for a given `(run_id, scenario, request)`.

## Web portal (`web/`)

- Server-side only: pages and server actions call `mock_server` from the Next server; nothing about the mock is
  exposed to the browser (server env `MOCK_API_URL`, never `NEXT_PUBLIC_*`).
- Never bypass the fair-draw chain from the UI. `mock_server` enforces it (409 on `/buy` for a `fair_draw`
  release); the UI renders the declare form for that mode, but correctness must not depend on that.
- Reuse the vendored shadcn/Base UI components in `src/components/ui/` rather than hand-rolling markup.
- Roles: user (default), organiser (an approved request), admin (`ADMIN_EMAILS` allowlist in env). Role is resolved
  per request from mock state plus the allowlist, never stored in the mock.
- Commits land in this repo and are mirrored to the fork for Vercel deploy.
- Portal-facing writes (organisers/events/releases/buy) are deliberately **not** on the MCP surface — that exists
  for the AgenticOrg agent.

## Testing rules

- `uv run pytest` must pass offline: no keys, no network, no real credentials, no uvicorn bind to a public interface.
  Keep it that way.
- `uv run ruff check .` must be clean; `uv run black --check .` must be clean (format with `uv run black .`).
- `uv run pre-commit run --all-files` must be clean.
- Mock-server tests cover the scenario table, idempotency and provenance; the timeout/delay scenarios exercise a real
  `uvicorn` thread in a background thread over real HTTP so the client timeout path is genuinely tested.
- Allocator tests assert the DIFD properties: determinism, capacity-respecting, ceiling-respecting, fairness-weighted
  ordering, waitlist order.
- Durable-state tests (`tests/test_state_durability.py`) reopen the app over the same data directory, because that is
  what a container restart is; they cover the pool, holds, capacity, mandate balance and the idempotency ledger.
- Markdown is autoformatted on commit by `pre-commit` (`.pre-commit-config.yaml`, `mdformat` +
  `mdformat-gfm`/`mdformat-tables`), installed once with `uv run pre-commit install`.

## Documentation rules

Practical, short: why it exists, how it works, failure cases, how to test it. Architectural decisions go in
`docs/decisions/ADR-NNN-title.md` (context, decision, consequences). No marketing tone, no emojis. Update docs in the
same commit as the behaviour change. Anything unverified is labelled as such, never stated as fact.

## How to run

```
uv sync
uv run pytest && uv run ruff check . && uv run black --check .
uv run pre-commit install           # one-time: wires the markdown-formatter commit hook
uv run pre-commit run --all-files
uv run uvicorn mock_server.app:app --port 8081      # or:
bash scripts/dev.sh                 # mock server on :8081 (GET /health)
```

The voice worker (optional; needs `GNANI_API_KEY`, `AGENTICORG_EMAIL`, `AGENTICORG_PASSWORD`,
`AGENTICORG_BASE_URL`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` — ADR-017). Against a
local room server (`livekit-server --dev` prints a dev key pair, `devkey`/`secret`):

```
uv run python -m voice_bridge.agent dev     # joins rooms and serves /health on :8082
```

The portal (optional; needs the mock running on :8081):

```
cd web && pnpm install && cp example.env .env.local   # fill in env once
cd web && pnpm dev                  # portal on :3000
cd web && pnpm type-check && pnpm lint && pnpm build
```

Fish shell is the user default; scripts are bash (`bash scripts/dev.sh`).

## Deploying

The cluster is GitOps. An ArgoCD Application named `kirro` watches **this repo's `k8s/` on `main`** and syncs it to
namespace `kirro` with `selfHeal` and `prune` enabled. So **merging to `main` is the deploy**, and there is no deploy
step in CI beyond the image build:

- `.github/workflows/docker.yml` builds and pushes `ghcr.io/cheetos-gif/kirro:latest` on every push to `main`.
- The Deployment pulls that tag with `imagePullPolicy: Always`, and ArgoCD reconciles `k8s/` from the same commit.
- `kubectl apply -k k8s/` **does not stick**: `selfHeal` reverts it within seconds (this cost real debugging time
  once — a manifest change was applied by hand, silently reverted, and the volume mount never took effect). Commit
  manifest changes instead.
- `kubectl rollout restart deploy/kirro-mock -n kirro` is still the way to force a pod onto a freshly pushed image
  without a manifest change.

## Working on this repo (for Claude sessions)

1. Read this file and `README.md`, then `docs/architecture.md`, then run `uv run pytest`.
1. Prefer editing existing files. No new top-level services, no new dependencies without an ADR.
1. Mock behaviour change -> update `tests/test_mock_server.py` and `docs/connectors.md` in the same change.
1. Before claiming something works, run it. Report real counts.
1. Never commit `.env`, keys, tokens, phone numbers or real user data. `logs/` is git-ignored.
1. Keep the mock's response shapes honest: label MOCK, never invent vendor fields or SDK method names.
1. Humans may set scenarios and simulate external events, but must not reason for the agent.

## Known open items

ADR-011 §7 lists what is genuinely open and unverified: field-parsing determinism once the LLM owns parsing,
non-MCP custom-connector tool discovery on AgenticOrg, declared-interest pool persistence, whether a Workflow can
message a user directly, static per-agent tool ACLs needing connector-side validation, and duplication between any
local decision log and AgenticOrg's Audit Log/Observatory (which is also what Q1.2 reconstruction now depends on). Do
not
assume any of those are resolved without live verification on `agenticorg.hackathon.pinelabs.com`.
