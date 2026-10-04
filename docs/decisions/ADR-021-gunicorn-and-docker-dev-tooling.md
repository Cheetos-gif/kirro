# ADR-021: gunicorn runs the mock, and the container/dev tooling becomes multi-stage, compose and make

Status: accepted (2026-10-04)

## Context

Issue #36. The runtime side of this repo had grown one image, one command and no developer story
around either. Concretely, before this ADR:

- `Dockerfile` was single-stage: `pip install uv`, `uv sync` twice, and `uv sync`'s venv, uv itself
  and the wheel cache all ended up in the published image.
- `CMD` was bare `uvicorn mock_server.app:app`. That is one process with no supervisor: if the
  worker dies, nothing restarts it; a reload means a redeploy. There was no healthcheck, so a
  container that answered nothing still counted as healthy to anything that only checked the
  process was up.
- There was no way to run the mock *and* the portal together, and no `Dockerfile.dev`: the only
  container path was to build the production image and hope.
- `web/` had no image at all, and `next.config.ts` was not `output: 'standalone'`, so it could not
  have produced a small one.
- Nothing wrapped the commands everyone types (`uv run pytest`, `ruff`, `black`, `pnpm`), and
  `scripts/dev.sh` was the single documented entry point even though the portal needs a second
  terminal.

Two constraints shape every choice below. The mock is a **single-writer** store (`ADR-013`,
`docs/decisions/ADR-013-durable-mock-state-on-sqlite.md`): one SQLite file, one connection, one
in-process lock, and the cluster runs it as `replicas: 1` for exactly that reason. And the repo's
own rule is that a new dependency needs an ADR — gunicorn is a new dependency.

## Decision

**1. `gunicorn` is the process manager, with the uvicorn worker class.** One new dependency, granted
here for one reason: a master process that restarts a crashed worker, handles `SIGTERM`/`SIGHUP`
gracefully, and can reload without a redeploy. It wraps the same ASGI app through
`uvicorn.workers.UvicornWorker`, so nothing about `mock_server.app:app` changes. The previous
command's `--proxy-headers --forwarded-allow-ips *` behaviour is preserved by gunicorn's
`forwarded_allow_ips = "*"`, which the uvicorn worker hands to uvicorn's own `Config` (and uvicorn's
`proxy_headers` default is `True`).

**2. Workers default to 1 and stay 1.** `GUNICORN_WORKERS` exists so the number is a deployment
decision rather than a hard-coded fact — it does **not** exist because raising it is safe today.
`ADR-013` makes SQLite single-writer; a second worker is a second writer against one file, and the
mock's own deployment is already pinned to one replica for the same reason. That is not an
assumption: running this config with `GUNICORN_WORKERS=2` against a fresh database, the second worker
exits during startup with `sqlite3.OperationalError: database is locked` while issuing
`PRAGMA journal_mode=WAL` (`Store.__init__` in `mock_server/state.py`), and gunicorn's master
restarts it — a crash loop whose only fix is the number.
The scalability purchased by this ADR is the *shape* of a real process manager, not concurrency.
**The trigger to revisit is named**: the day the store stops being single-writer (the `Store` class
in `mock_server/state.py` moves to Postgres, per ADR-013's "Multi-replica" open question), the number
becomes a capacity decision and nothing else here has to change.

**3. The settings live in `gunicorn.conf.py`, not in a long `CMD`.** gunicorn does not read a
`GUNICORN_WORKERS` environment variable itself (its `workers` setting is `WEB_CONCURRENCY`, default
1), so the env lookup has to live somewhere. A config file keeps it in one testable place, keeps the
Dockerfile `CMD` to one line, and makes the worker comment sit next to the line it explains.

**4. The image becomes multi-stage.** A `builder` stage resolves the lock and installs the venv at
`/opt/venv`; the `runtime` stage copies the venv and the source and nothing else, so uv, pip and the
build caches never reach a published layer. Same base (`python:3.13-slim`), same non-root `kirro`
uid 10001 owning `/app`, same default `ENV`s. `/opt/venv` rather than `/app/.venv` specifically
because the dev override bind-mounts the source over `/app`; a venv under `/app` would be shadowed
by the mount.

**5. A `HEALTHCHECK` that uses python, not curl.** `python:3.13-slim` does not ship curl, and
installing it for one probe is the kind of runtime dependency this image deliberately avoids. A
one-line `python -c` urllib probe against `/health` is the whole check.

**6. `Dockerfile.dev` plus `docker-compose.override.yml` for the reload loop, and
`docker-compose.yml` for the prod-like stack.** The override is what makes `docker compose up` (no
`-f`) the dev command — dev images, source bind-mounted, `uvicorn --reload` / `next dev` — and
`docker compose -f docker-compose.yml up` the prod-like one. Compose merges the override
automatically, so the difference is one file, not one long flag.

**7. `web/Dockerfile` + `output: 'standalone'`, with no credential in the image.** The portal's image
is a pnpm deps stage, a build stage and a non-root runtime that runs the standalone bundle's
`server.js` (the same server `next start` uses) and copies only `.next/standalone`, `.next/static`
and `public`. The app reads every variable at runtime, server-side
(`web/src/env.ts`), so there is no `ARG` for any credential and `web/.dockerignore` excludes `.env*`
so `COPY . .` cannot bake one either. This is **not** the deploy path: the portal still deploys to
Vercel from the fork.

**8. A `Makefile` that is a wrapper, not a reimplementation.** `dev`, `dev-native`, `build`, `down`,
`logs`, `test`, `lint`, `fmt` — each one line, each the command you would have typed. `dev-native`
keeps the pre-Docker path (`bash scripts/dev.sh` plus `pnpm dev`) alive on purpose: it is faster day
to day, and the Docker path exists so nobody has to install Node and uv to see the thing run.

## Consequences

- **Production runs the image's gunicorn; development runs uvicorn. (Amended 2026-10-04, same day:
  this originally left `k8s/deployments.yaml` overriding the command with bare `uvicorn`, and the
  override has been removed.)** The rule is now one process model per environment, with exactly one
  definition of each: production is the image's own CMD
  (`gunicorn --config gunicorn.conf.py`, workers 1 — ADR-013), used by the cluster, by
  `docker compose -f docker-compose.yml up` and by a bare `docker run`; development is `uvicorn --reload`, used by `Dockerfile.dev` (compose dev override) and by `scripts/dev.sh`, which now
  passes `--reload` too so the two dev paths behave identically. The k8s Deployment no longer sets
  `command:` at all — a manifest that overrides the image's process model is how the cluster ran
  bare uvicorn for an hour while the image, compose and this ADR all said gunicorn. Changing the
  process model now means editing `gunicorn.conf.py`, which is the point.
- **docker-compose is a local dev/eval convenience, not a second deployment path.** It exists so
  `docker compose up` can show the mock and the portal together on a laptop. Nothing in
  `docker-compose.yml` is a source of truth for the cluster, and the two will diverge on purpose
  (compose runs one gunicorn worker with no PVC; the cluster runs one gunicorn worker with a PVC).
- **New dependency: gunicorn** (recorded in `pyproject.toml` and `uv.lock`). No other dependency was
  added. `uvicorn.workers` emits an upstream `DeprecationWarning` in favour of the separate
  `uvicorn-worker` distribution; migrating is deferred rather than done, because it would add a
  second dependency this ADR did not buy. **Trigger to migrate**: the next time the uvicorn worker
  class has to be touched anyway, or before uvicorn removes `uvicorn.workers`.
- **New files**: `Dockerfile.dev`, `gunicorn.conf.py`, `docker-compose.yml`,
  `docker-compose.override.yml`, `web/Dockerfile`, `web/.dockerignore`, `Makefile`. `web/package.json`
  gains `packageManager: pnpm@11.28.2` so corepack inside the image and Vercel resolve the same pnpm
  the lockfile was generated with — the repo previously pinned nothing.
- **`.dockerignore` shrinks the mock image's context**: `web/`, the compose/Make files and
  `Dockerfile.dev` are excluded, since the portal has its own image and none of that is runtime
  content for the mock. `gunicorn.conf.py` is deliberately *not* excluded — the `CMD` reads it. The
  root `.gitignore` gains `data/`, the (empty, shadowed) mount target the dev override's `.:/app`
  bind mount leaves behind.
- **`web/next.config.ts` gains `output: 'standalone'`.** Vercel ignores it; the compose image needs
  it. `docker compose run --rm mock python -m pytest` works because the dev override's image
  (`Dockerfile.dev`) installs the dev group — `pytest`, `ruff` and `black` are all importable there,
  and not in the image `-f docker-compose.yml` builds.
- The mock's compose state lives on a named volume (`mock-data` at `/app/data`), matching the
  cluster's layout, so `docker compose down` does not silently wipe a demo's declarations.
