# KIRRO mock-server image: the mock external services the AgenticOrg-hosted agent calls
# (docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md). The same image also carries the
# voice bridge (ADR-016, ADR-017), which the cluster runs with its own command and its own
# credentials; the image bakes no credentials and reads them from the environment at runtime.
#
# Two stages: `builder` resolves the lock and installs the venv, `runtime` copies only the venv and
# the source. Nothing from the builder (uv, pip, build caches) reaches the published image.
#
# WORKERS DEFAULT TO 1. That is deliberate, not a default nobody got round to changing: mock state
# is single-writer SQLite with one connection and one lock (ADR-013), so a second worker is a
# second writer against one file. The scalability bought by gunicorn here is the *shape* — a real
# process manager that restarts a crashed worker and reloads gracefully — not concurrency. Raise
# `GUNICORN_WORKERS` the day the store stops being single-writer. See ADR-021 for the full
# reasoning and the trigger condition.
# See gunicorn.conf.py for the settings that make that statement true at runtime.

# ------------------------------------------------------------------------------------------------ builder
FROM python:3.13-slim AS builder

# uv in the builder only; the runtime stage never needs it.
RUN pip install --no-cache-dir uv

# Copy instead of hardlinking into the venv (hardlinks do not survive a layer copy), byte-compile
# at build time so the first request does not pay the import cost, and never let uv fetch its own
# interpreter — the base image's python is the interpreter.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Dependencies first, on their own layer, so a source-only change does not re-resolve the lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the source. The second sync is what an operator would run locally; with `package = false`
# there is no project to install, so it is cheap and keeps the two commands symmetric.
COPY . .
RUN uv sync --frozen --no-dev

# ------------------------------------------------------------------------------------------------ runtime
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# /app must be owned by the runtime user: the default log dir is relative to WORKDIR, and a
# root-owned /app made every request-log write raise PermissionError, 500ing every serve()-wrapped
# route (ADR-013). Same uid as the cluster's securityContext.
RUN useradd --create-home --uid 10001 kirro \
    && mkdir -p /app/logs /app/data \
    && chown -R kirro:kirro /app

# The venv is built at /opt/venv in the builder and lands at the same absolute path here, so the
# console-script shebangs (#!/opt/venv/bin/python) stay valid. It sits outside /app on purpose:
# the dev override bind-mounts the source over /app, and a venv under /app would be shadowed by it.
COPY --from=builder --chown=kirro:kirro /opt/venv /opt/venv
COPY --chown=kirro:kirro . /app

USER kirro

# Works for a bare `docker run`; the cluster and docker-compose override both to /app/data, which is
# the PVC/volume mount.
ENV MOCK_LOG_DIR=/app/logs \
    MOCK_DB_PATH=/app/logs/mock.db

# 8081 is the mock; the voice bridge runs the same image with its own command on 8082.
EXPOSE 8081 8082

# A python one-liner rather than curl: python:3.13-slim ships python and not curl, and installing
# curl for a probe is exactly the kind of dependency this image avoids. Non-200 or a refused
# connection both raise, both exit non-zero.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=3).status == 200 else 1)"]

# gunicorn around the same ASGI app, with the uvicorn worker class so nothing about the app
# changes. The bind and `forwarded-allow-ips '*'` reproduce the previous plain-uvicorn command:
# the uvicorn worker installs its proxy-header middleware from that setting, so X-Forwarded-* is
# still trusted from the ingress. All of it lives in gunicorn.conf.py, including the
# GUNICORN_WORKERS lookup that defaults to 1.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "mock_server.app:app"]
