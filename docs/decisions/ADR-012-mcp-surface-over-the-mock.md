# ADR-012: An MCP surface over the mock server

Status: accepted (2026-10-02)

## Context

AgenticOrg's `Register Connector` form has an **MCP checkbox** whose tooltip says the connector's tool catalog is
discovered automatically from the Base URL at registration time (`docs/agenticorg/setup-runbook.md` §4–§5,
ADR-010's live inventory). `docs/agenticorg/setup-runbook.md` therefore registers all four mocked surfaces with that
checkbox **on**.

The mock server was plain REST: FastAPI routes under `/venue`, `/pinelabs`, `/allocator`, `/delhivery`. It had no MCP
endpoint and no MCP dependency. ADR-011 Risk 2 also recorded that the *non*-MCP path was unverified: registering
without the checkbox showed no visible way to declare individual operations, so it was unknown whether a plain
custom connector yields callable tools.

So the mocks could not be registered as specified. Two things were needed: an MCP surface, and a decision about how
much of the existing implementation it reuses.

## Decision

1. **Add the official `mcp` Python SDK** (v2, `mcp.server.mcpserver.MCPServer`) as a runtime dependency. It is the
   only new dependency; `httpx` (already present) carries the in-process calls.

1. **One MCP server per surface, mounted at `/<surface>/mcp`** — `/venue/mcp`, `/pinelabs/mcp`, `/allocator/mcp`,
   `/delhivery/mcp`. This matches the Base URLs the runbook already specifies (`/venue`, `/pinelabs`, `/allocator`,
   `/delhivery`) and keeps each surface's tool list separate, so a connector (and therefore an agent) never exposes
   another surface's operations. Transport: streamable HTTP, stateless (`stateless_http=True`) — no server-side
   session to lose between calls.

1. **Tools are thin adapters over the same ASGI app.** Each tool calls the corresponding REST route **in process**
   through `httpx.ASGITransport(app=app)`. Validation, idempotency replay, scenario handling, request logging and
   the state store are therefore literally the same code path the REST routes use — there is no second
   implementation of any contract to drift from `docs/connectors.md`.

1. **Tools take an optional `run_id`** (sent as `X-Run-Id`) and an optional `idempotency_key`. Both default to unset:
   `run_id` falls back to `"default"`, which is also what the REST routes use, so the Declare Agent and the Window
   Allocation Workflow share one pool whether or not the platform sets a run id.

1. **MCP session managers run in the FastAPI lifespan.** Mounting a Starlette sub-app does not propagate its
   lifespan, so `create_app`'s lifespan enters `session_manager.run()` for each surface; without it the endpoints
   404/500 at request time.

1. **The REST routes remain the primary contract.** `docs/connectors.md` still documents them; the MCP surface is an
   additional access path to the same behaviour, not a replacement.

Explicitly rejected:

- **Extracting a parallel pure-handler layer** for MCP to call. It duplicates the contract surface and risks the two
  paths diverging; the in-process call needs no such split.
- **Self-calling over the network** (`http://127.0.0.1:8081`). It introduces a port/URL dependency, breaks under a
  single-process test client, and adds latency for nothing.

## Consequences

- `pyproject.toml`/`uv.lock` gain `mcp` (and its transitive deps: `httpx2`, `sse-starlette`, `pyjwt`, …).
- Adding or changing a route now implies keeping its MCP tool in step; `tests/test_mcp_surface.py` asserts the tool
  catalogs per surface and that MCP and REST share one state store, so drift fails the suite.
- The platform registers each surface against `<public mock host>/<surface>/mcp` with the MCP checkbox on
  (runbook §4–§5).
- **Scenarios are not reachable from MCP.** `POST /__admin/scenario` stays a harness-only control; MCP tools always
  take the default `success` path. This is deliberate — the platform's agent must be exercised by its own behaviour,
  not by a scenario switch it can see. Realistic failure still exists on the wire (4xx/5xx from validation), and the
  HTTP routes keep the full scenario table for local tests.
- Idempotency is opt-in for MCP callers via the `idempotency_key` tool argument; when supplied it uses the same
  ledger as `Idempotency-Key` on the REST path, so a redelivered tool call cannot double-charge.

## Open questions

- Whether AgenticOrg's MCP client accepts **stateless streamable HTTP**. If at registration it turns out to need the
  older SSE transport, `MCPServer.sse_app()` covers it (a second mount), but that is not built until observed.
- Whether the non-MCP registration path (ADR-011 Risk 2) also yields callable tools. If it does, this surface is
  simply unused; the verification is still worth recording in the runbook.
