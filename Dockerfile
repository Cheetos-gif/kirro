# One image, two entrypoints (KIRRO Core and the mock server) — k8s/deployments.yaml picks the
# command per Deployment. No LLM dependency on this path: agent/api.py drives the Engine directly
# and never calls Anthropic, so no API key is required to run either service.
FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install deps first so dependency layers cache across source-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

RUN useradd --create-home --uid 10001 kirro
USER kirro

EXPOSE 8080 8081
