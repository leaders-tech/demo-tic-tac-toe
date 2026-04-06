# This file gives short root commands for local development, formatting, and tests.
# Edit this file when common project commands or local run defaults change.
# Copy an existing target pattern here when you add another simple root command.
.DEFAULT_GOAL := help

DOCKER_PROJECT_NAME := templatepwa_local
DOCKER_ENV_FILE := .env.docker
DOCKER_COMPOSE := ./scripts/docker-compose.sh --env-file $(DOCKER_ENV_FILE) -p $(DOCKER_PROJECT_NAME) -f docker-compose.yml
WIFI_IP := $(shell ipconfig getifaddr en0 2>/dev/null)
LAN_FRONTEND_PORT := 4173
LAN_BACKEND_PORT := 4174
LAN_FRONTEND_URL := http://$(WIFI_IP):$(LAN_FRONTEND_PORT)
LAN_BACKEND_URL := http://$(WIFI_IP):$(LAN_BACKEND_PORT)
PY_RUNTIME_DEPS := $(shell python3 -c 'import re, tomllib, pathlib; data = tomllib.loads(pathlib.Path("pyproject.toml").read_text()); print(" ".join(re.match(r"[A-Za-z0-9._-]+", dep).group(0) for dep in data["project"]["dependencies"]))')
PY_DEV_DEPS := $(shell python3 -c 'import re, tomllib, pathlib; data = tomllib.loads(pathlib.Path("pyproject.toml").read_text()); print(" ".join(re.match(r"[A-Za-z0-9._-]+", dep).group(0) for dep in data["dependency-groups"]["dev"]))')
CHECK_WIFI_IP = @test -n "$(WIFI_IP)" || (echo "Wi-Fi IP was not found on en0. Connect to Wi-Fi or use normal make back / make front."; exit 1)
CHECK_DOTENV = @test -f .env || (echo ".env is missing. Run make install or create .env first."; exit 1)
CHECK_DOCKER_ENV = @test -f $(DOCKER_ENV_FILE) || (echo "$(DOCKER_ENV_FILE) is missing. Copy .env.docker.example to $(DOCKER_ENV_FILE) and update it first."; exit 1)
LOAD_DOTENV = set -a; . ./.env; set +a
LOAD_DOCKER_ENV = set -a; . ./$(DOCKER_ENV_FILE); set +a
CHECK_FRONTEND_ORIGIN = test -n "$$FRONTEND_ORIGIN" || (echo "FRONTEND_ORIGIN is missing in .env."; exit 1); case "$$FRONTEND_ORIGIN" in http://localhost:*|http://127.0.0.1:*) ;; *) echo "FRONTEND_ORIGIN must look like http://localhost:5173 or http://127.0.0.1:5173 for local make commands."; exit 1 ;; esac
CHECK_PUBLIC_BASE_URL = test -n "$$PUBLIC_BASE_URL" || (echo "PUBLIC_BASE_URL is missing in .env."; exit 1)
CHECK_DOCKER_FRONTEND_ORIGIN = test -n "$$FRONTEND_ORIGIN" || (echo "FRONTEND_ORIGIN is missing in $(DOCKER_ENV_FILE)."; exit 1)

.PHONY: help install setup back back-once front open back-lan front-lan open-lan back-docker front-docker open-docker stop-docker clean-docker format test test-e2e-docker deps-update-safe deps-update-latest

help:
	@printf "Available commands:\n"
	@printf "  make install Install deps and create local env files\n"
	@printf "  make setup   Same as make install\n"
	@printf "  make back    Run the backend server with auto-reload using .env\n"
	@printf "  make back-once Run the backend server without auto-reload using .env\n"
	@printf "  make front   Run the frontend dev server using .env\n"
	@printf "  make open    Open the frontend URL from .env in a browser\n"
	@printf "  make back-lan Run the backend for testing on the same Wi-Fi\n"
	@printf "  make front-lan Run the frontend for testing on the same Wi-Fi\n"
	@printf "  make open-lan Open the Wi-Fi frontend URL in a browser\n"
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

install setup:
	uv sync --all-groups
	cd frontend && npm install && npx playwright install
	test -f .env || cp .env.example .env
	test -f $(DOCKER_ENV_FILE) || cp .env.docker.example $(DOCKER_ENV_FILE)
	cd frontend && test -f .env.development.local || cp .env.example .env.development.local

back:
	$(CHECK_DOTENV)
	@$(LOAD_DOTENV); \
	$(CHECK_FRONTEND_ORIGIN); \
	uv run python -m backend.dev

back-once:
	$(CHECK_DOTENV)
	@$(LOAD_DOTENV); \
	$(CHECK_FRONTEND_ORIGIN); \
	uv run python -m backend.main

front:
	$(CHECK_DOTENV)
	@$(LOAD_DOTENV); \
	$(CHECK_FRONTEND_ORIGIN); \
	$(CHECK_PUBLIC_BASE_URL); \
	frontend_host_port=$${FRONTEND_ORIGIN#http://}; \
	frontend_host=$${frontend_host_port%%:*}; \
	frontend_port=$${frontend_host_port##*:}; \
	cd frontend && VITE_BACKEND_URL="$$PUBLIC_BASE_URL" npm run dev -- --host "$$frontend_host" --port "$$frontend_port"

open:
	$(CHECK_DOTENV)
	@$(LOAD_DOTENV); \
	$(CHECK_FRONTEND_ORIGIN); \
	open "$$FRONTEND_ORIGIN"

back-lan:
	$(CHECK_WIFI_IP)
	APP_HOST=0.0.0.0 APP_PORT=$(LAN_BACKEND_PORT) FRONTEND_ORIGIN=$(LAN_FRONTEND_URL) uv run python -m backend.dev

front-lan:
	$(CHECK_WIFI_IP)
	cd frontend && VITE_BACKEND_URL=$(LAN_BACKEND_URL) npm run dev -- --host 0.0.0.0 --port $(LAN_FRONTEND_PORT)

open-lan:
	$(CHECK_WIFI_IP)
	@echo "Open $(LAN_FRONTEND_URL)"
	open $(LAN_FRONTEND_URL)

back-docker:
	$(CHECK_DOCKER_ENV)
	$(DOCKER_COMPOSE) up -d --build backend

front-docker:
	$(CHECK_DOCKER_ENV)
	$(DOCKER_COMPOSE) up -d --build frontend

open-docker:
	$(CHECK_DOCKER_ENV)
	@$(LOAD_DOCKER_ENV); \
	$(CHECK_DOCKER_FRONTEND_ORIGIN); \
	open "$$FRONTEND_ORIGIN"

stop-docker:
	$(CHECK_DOCKER_ENV)
	$(DOCKER_COMPOSE) down --remove-orphans

clean-docker:
	$(CHECK_DOCKER_ENV)
	$(DOCKER_COMPOSE) down -v --remove-orphans --rmi local

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
