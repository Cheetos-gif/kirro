# Thin wrapper over the three tools this repo already uses: uv, pnpm, docker compose (ADR-021).
# Every target is one command you would otherwise have typed by hand -- there is no logic here that
# does not live in those tools. `make` with no target lists them.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help dev dev-native build down logs test lint fmt

help: ## list the targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

dev: ## docker compose up: dev override auto-merged, hot reload (mock :8081, portal :3000)
	docker compose up --build

dev-native: ## no-Docker flow: bash scripts/dev.sh (mock :8081) + pnpm dev in web/ (portal :3000)
	@set -e; \
	bash scripts/dev.sh & mock=$$!; \
	trap 'kill $$mock 2>/dev/null || true' EXIT INT TERM; \
	cd web && pnpm dev

build: ## prod-like images via compose, dev override excluded
	docker compose -f docker-compose.yml build

down: ## stop the compose stack (keeps the mock-data volume)
	docker compose down

logs: ## follow the compose stack's logs
	docker compose logs -f

test: ## mock suite (offline) + portal unit tests
	uv run pytest && cd web && pnpm test

lint: ## ruff + black --check + eslint
	uv run ruff check . && uv run black --check . && cd web && pnpm lint

fmt: ## ruff --fix + black + prettier
	uv run ruff check --fix . && uv run black . && cd web && pnpm format
