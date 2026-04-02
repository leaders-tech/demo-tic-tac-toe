# This file gives short root commands for local development, formatting, and tests.
# Edit this file when students need another common repo command from the project root.
# Copy an existing target pattern here when you add another simple root command.
.DEFAULT_GOAL := help

DOCKER_PROJECT_NAME := templatepwa_local
DOCKER_FRONTEND_PORT := 8088
DOCKER_BACKEND_PORT := 8089
DOCKER_APP_MODE := dev
DOCKER_COOKIE_SECRET := local-docker-secret
DOCKER_FRONTEND_ORIGIN := http://localhost:$(DOCKER_FRONTEND_PORT)
DOCKER_VITE_BACKEND_URL := http://localhost:$(DOCKER_BACKEND_PORT)
DOCKER_COMPOSE := ./scripts/docker-compose.sh -p $(DOCKER_PROJECT_NAME) -f docker-compose.yml
PY_RUNTIME_DEPS := $(shell python3 -c 'import re, tomllib, pathlib; data = tomllib.loads(pathlib.Path("pyproject.toml").read_text()); print(" ".join(re.match(r"[A-Za-z0-9._-]+", dep).group(0) for dep in data["project"]["dependencies"]))')
PY_DEV_DEPS := $(shell python3 -c 'import re, tomllib, pathlib; data = tomllib.loads(pathlib.Path("pyproject.toml").read_text()); print(" ".join(re.match(r"[A-Za-z0-9._-]+", dep).group(0) for dep in data["dependency-groups"]["dev"]))')

.PHONY: help setup back back-once front open back-docker front-docker open-docker stop-docker clean-docker format test test-e2e-docker deps-update-safe deps-update-latest

help:
	@printf "Available commands:\n"
	@printf "  make setup   Install deps and create local env files\n"
	@printf "  make back    Run the backend server with auto-reload\n"
	@printf "  make back-once Run the backend server without auto-reload\n"
	@printf "  make front   Run the frontend dev server\n"
	@printf "  make open    Open the frontend in a browser\n"
	@printf "  make back-docker Start the backend container for local Docker testing\n"
	@printf "  make front-docker Start the frontend container for local Docker testing\n"
	@printf "  make open-docker Open the Docker frontend in a browser\n"
	@printf "  make stop-docker Stop the local Docker test containers\n"
	@printf "  make clean-docker Stop the local Docker test containers and delete their images and data\n"
	@printf "  make deps-update-safe Update backend and frontend deps in the safe supported way\n"
	@printf "  make deps-update-latest Update backend deps to the newest available versions\n"
	@printf "  make format  Format backend and frontend code\n"
	@printf "  make test    Run backend, frontend unit, and e2e tests\n"
	@printf "  make test-e2e-docker Run e2e tests against Docker containers\n"

setup:
	uv sync --all-groups
	cd frontend && npm install && npx playwright install
	test -f .env || cp .env.example .env
	cd frontend && test -f .env.development.local || cp .env.example .env.development.local

back:
	APP_HOST=localhost FRONTEND_ORIGIN=http://localhost:5173 uv run python -m backend.dev

back-once:
	APP_HOST=localhost FRONTEND_ORIGIN=http://localhost:5173 uv run python -m backend.main

front:
	cd frontend && VITE_BACKEND_URL=http://localhost:8000 npm run dev -- --host localhost --port 5173

open:
	open http://localhost:5173

back-docker:
	DOCKER_APP_MODE=$(DOCKER_APP_MODE) DOCKER_COOKIE_SECRET=$(DOCKER_COOKIE_SECRET) DOCKER_FRONTEND_PORT=$(DOCKER_FRONTEND_PORT) DOCKER_BACKEND_PORT=$(DOCKER_BACKEND_PORT) DOCKER_FRONTEND_ORIGIN=$(DOCKER_FRONTEND_ORIGIN) DOCKER_VITE_BACKEND_URL=$(DOCKER_VITE_BACKEND_URL) $(DOCKER_COMPOSE) up -d --build backend

front-docker:
	DOCKER_APP_MODE=$(DOCKER_APP_MODE) DOCKER_COOKIE_SECRET=$(DOCKER_COOKIE_SECRET) DOCKER_FRONTEND_PORT=$(DOCKER_FRONTEND_PORT) DOCKER_BACKEND_PORT=$(DOCKER_BACKEND_PORT) DOCKER_FRONTEND_ORIGIN=$(DOCKER_FRONTEND_ORIGIN) DOCKER_VITE_BACKEND_URL=$(DOCKER_VITE_BACKEND_URL) $(DOCKER_COMPOSE) up -d --build frontend

open-docker:
	open http://localhost:$(DOCKER_FRONTEND_PORT)

stop-docker:
	DOCKER_APP_MODE=$(DOCKER_APP_MODE) DOCKER_COOKIE_SECRET=$(DOCKER_COOKIE_SECRET) DOCKER_FRONTEND_PORT=$(DOCKER_FRONTEND_PORT) DOCKER_BACKEND_PORT=$(DOCKER_BACKEND_PORT) DOCKER_FRONTEND_ORIGIN=$(DOCKER_FRONTEND_ORIGIN) DOCKER_VITE_BACKEND_URL=$(DOCKER_VITE_BACKEND_URL) $(DOCKER_COMPOSE) down --remove-orphans

clean-docker:
	DOCKER_APP_MODE=$(DOCKER_APP_MODE) DOCKER_COOKIE_SECRET=$(DOCKER_COOKIE_SECRET) DOCKER_FRONTEND_PORT=$(DOCKER_FRONTEND_PORT) DOCKER_BACKEND_PORT=$(DOCKER_BACKEND_PORT) DOCKER_FRONTEND_ORIGIN=$(DOCKER_FRONTEND_ORIGIN) DOCKER_VITE_BACKEND_URL=$(DOCKER_VITE_BACKEND_URL) $(DOCKER_COMPOSE) down -v --remove-orphans --rmi local

deps-update-safe:
	uv add --bounds major $(PY_RUNTIME_DEPS)
	uv add --dev --bounds major $(PY_DEV_DEPS)
	cd frontend && npm update

deps-update-latest:
	uv add --bounds lower $(PY_RUNTIME_DEPS)
	uv add --dev --bounds lower $(PY_DEV_DEPS)
	cd frontend && npm update

format:
	uv run ruff format .
	cd frontend && npm run format

test:
	uv run pytest
	cd frontend && npm run test
	cd frontend && npm run test:e2e

test-e2e-docker:
	cd frontend && npm run test:e2e:docker
