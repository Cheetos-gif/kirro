"""Gunicorn settings for the KIRRO mock server (ADR-021).

The image runs `gunicorn --config gunicorn.conf.py mock_server.app:app`, so this file — not a long
CMD — is where the process model lives. Keeping it here also means the same command works outside
Docker for anyone who wants to reproduce a production-shaped process locally.
"""

import os

# The mock's port. The voice bridge is a separate process on 8082 (ADR-017); it runs the same image
# with its own command and does not use this file.
bind = "0.0.0.0:8081"

# The uvicorn worker, so the ASGI app is untouched. `uvicorn.workers` is deprecated upstream in
# favour of the separate `uvicorn-worker` distribution; it still ships inside uvicorn, and a second
# package is a dependency change this ADR did not buy. Migration is recorded as debt in ADR-021.
worker_class = "uvicorn.workers.UvicornWorker"

# Reproduces the old plain-uvicorn command's `--proxy-headers --forwarded-allow-ips *`: the uvicorn
# worker passes this straight to its own Config, which installs the proxy-header middleware. Trust
# the peer because the only thing in front of this process is the cluster ingress / compose bridge.
forwarded_allow_ips = "*"

# WORKERS DEFAULT TO 1, and it stays 1. Mock state is single-writer SQLite behind one connection
# and one in-process lock (ADR-013, docs/decisions/ADR-013-durable-mock-state-on-sqlite.md), so a
# second worker is a second writer against one file — and the cluster runs replicas: 1 for the same
# reason. This env var exists so the number is a deployment decision rather than a hard-coded fact,
# not because raising it today is safe. Raise it the day the store stops being single-writer.
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))

# No preload: preloading forks the app after import, which would hand every worker the same SQLite
# connection and lock (ADR-013). The mock imports cheaply, so nothing is gained by it.
preload_app = False

# Keep the previous command's logging behaviour: both streams to stdout/stderr, captured by the
# container runtime.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# A worker that ignores SIGTERM for longer than this has a real problem (a wedged SQLite lock);
# gunicorn's default is 30s, which is already the right answer. Stated rather than implied.
graceful_timeout = 30
