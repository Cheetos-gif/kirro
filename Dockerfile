# One image, two services: the mock server (mock external services the AgenticOrg-hosted KIRRO
# agent calls) and the voice bridge (the browser call channel, ADR-016). No LLM and no
# decision-making in either: the brain lives on the AgenticOrg platform
# (docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md). Only the voice bridge needs
# credentials, and it takes them from the environment at runtime, never from this image.
FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install deps first so dependency layers cache across source-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

# The runtime user must own /app: the default log dir is relative to WORKDIR, and a root-owned /app
# made every request-log write raise PermissionError, 500ing every serve()-wrapped route (ADR-013).
RUN useradd --create-home --uid 10001 kirro \
    && mkdir -p /app/logs /app/data \
    && chown -R kirro:kirro /app

USER kirro

# Works for a bare `docker run`; the cluster overrides both to the PVC-mounted /app/data.
ENV MOCK_LOG_DIR=/app/logs \
    MOCK_DB_PATH=/app/logs/mock.db

# 8081 is the mock; the voice bridge runs the same image with its own command on 8082.
EXPOSE 8081 8082
CMD ["uvicorn", "mock_server.app:app", "--host", "0.0.0.0", "--port", "8081", "--proxy-headers", "--forwarded-allow-ips", "*"]
