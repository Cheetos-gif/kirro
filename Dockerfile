# Single service: the mock server (mock external services the AgenticOrg-hosted KIRRO agent calls).
# No LLM and no API key on this path — the decision-making brain lives on the AgenticOrg platform
# (docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md), not in this image.
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

EXPOSE 8081
CMD ["uvicorn", "mock_server.app:app", "--host", "0.0.0.0", "--port", "8081"]
