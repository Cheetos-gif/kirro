# ADR-013: Durable mock state on SQLite

Status: accepted (2026-10-02)

## Context

The mock is not stateless in the only way that matters. The Declare Agent writes a bid into the declare-interest
pool during one conversation; the Window Allocation Workflow reads that pool later and runs the draw. With the
state in process memory, any restart in between — a rollout, an eviction, a node drain — silently empties the pool,
the draw returns an empty result, and the demo fails with no error anywhere. Rollouts are routine here: the image is
`ghcr.io/cheetos-gif/kirro:latest` with `imagePullPolicy: Always`, so every deploy restarts the pod.

The pre-migration repo kept declarations on disk (JSON/JSONL under `KIRRO_DATA_DIR`, with a PVC); that code was
removed with the brain in issue #1, and the mock that replaced it inherited nothing durable.

Two constraints shape the choice:

1. `uv run pytest` must pass **offline, with no credentials** (`AGENTS.md` testing rules). A store that needs a
   running server would break that.
1. The service is a single-writer, single-replica mock: the k8s Deployment is `replicas: 1`, and the data is small
   (a handful of JSON documents per run).

Deploying the mock also surfaced the cost of ignoring the container's filesystem assumptions: every `serve()`-wrapped
route returned 500 in the cluster because the process runs as uid 10001 while `/app` is root-owned, so the
request-log write raised `PermissionError`. That is fixed here too, because it is the same class of problem.

## Decision

1. **SQLite via the standard library (`sqlite3`)** — no new dependency. One file at `MOCK_DB_PATH`; default
   `<log dir>/mock.db`, and in the cluster `/app/data/mock.db` on a PersistentVolumeClaim.

1. **Two tables, everything keyed by `run_id`:**

   ```sql
   objects (run_id, kind, key, payload)   -- one JSON document per entity; PK (run_id, kind, key)
   counters(run_id, name, key, value)     -- next_id() sequences and per-slot capacity in use
   ```

   `kind` is `holds`, `bookings`, `mandates`, `payments`, `shipments`, `declarations` or `idem`. Keeping the
   per-run key preserves the isolation the routes already had: two `X-Run-Id` values never see each other.

1. **Write-through on every mutation, behind a dict-like facade** (`Row`, `PTable`, `IntTable`, `Idem` in
   `mock_server/state.py`). The routes keep writing `run.holds[hid] = {...}`; the facade persists it. A row returned
   by `.get()` is a `Row` whose own `__setitem__` writes back, so nested mutation
   (`hold["released"] = True`, `m["balance"] -= amt`) persists too — the pattern the routes actually use, and the
   one a naive facade would silently drop.

1. **WAL journal mode, `synchronous=NORMAL`, one connection** (`check_same_thread=False` + a lock). Read-modify-write
   of the `next_id` counter goes through a single `INSERT … ON CONFLICT DO UPDATE` so it is atomic in SQL rather
   than relying on a single event-loop thread.

1. **`replicas: 1` becomes load-bearing**, and is documented as such in `k8s/deployments.yaml`. SQLite is a
   single-writer store; horizontal scaling is not supported.

1. **Request logging never fails a call.** `MockState.log` degrades to a one-time stderr warning on `OSError`, and
   the Dockerfile creates `/app/logs` owned by the runtime user, so the default path works. The mock's job is to
   answer like a vendor API; losing a diagnostic line must not turn a business call into a 500.

1. **Stored documents must be JSON-serializable.** Hold expiry is stored as an ISO string and parsed on read
   (`_parse_iso`), rather than persisting `datetime` objects.

Explicitly rejected:

- **Postgres.** Correct the moment the mock becomes multi-replica or multi-tenant; today it would add a second
  service, credentials and connection management to a one-replica mock, and would break the offline-test invariant
  (a test would need a live database). Moving to it later is a contained change: only `Store` in `state.py` speaks
  SQL.
- **Redis.** Persistence here is weaker than SQLite's committed transactions, and the mandate/idempotency data is
  exactly what must not be lost.
- **A single row holding the whole run as one JSON blob.** It is a database in name only; per-entity rows keep the
  schema meaningful and let a single entity be written without rewriting a run.

## Consequences

- `k8s/pvc.yaml` returns (this time for the mock): `kirro-mock-data`, `ReadWriteOnce`, `local-path`, 1Gi, mounted at
  `/app/data` with `fsGroup: 10001` so the non-root uid can write it. `MOCK_DB_PATH=/app/data/mock.db` and
  `MOCK_LOG_DIR=/app/data/logs` are set on the Deployment, so both the DB and the request log are durable.
- The Deployment also gains a restricted-profile `securityContext` (`runAsNonRoot`, `allowPrivilegeEscalation: false`, drop `ALL` capabilities, `RuntimeDefault` seccomp, `fsGroup: 10001`), which silences the PodSecurity
  warnings the namespace emits and is required for the non-root container to own the volume.
- State now survives restarts and redeploys; `POST /__admin/reset` is the explicit way to clear it.
- `tests/test_state_durability.py` proves restart survival by opening a second app over the same data directory:
  pool, holds, capacity, mandate balance and the idempotency ledger all survive, ids do not repeat, runs stay
  isolated, and an unwritable log dir no longer fails a call.
- WAL requires a filesystem that supports locking — fine for the single-node `local-path` provisioner in use, and
  worth remembering if the mock is ever moved to a shared/network filesystem.

## Open questions

- **Growth.** Nothing prunes old runs; the file grows with every distinct `X-Run-Id`. Acceptable at demo scale, and
  `reset` exists; a retention policy is not built.
- **Multi-replica.** If the mock ever needs to scale horizontally, `Store` moves to Postgres (or the state moves to
  a service that owns it). That is the trigger condition for revisiting this ADR, not a change to the current one.
