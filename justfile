# dutyy-api task runner — run `just` to list recipes

# List available recipes
default:
    @just --list

sync:
  uv sync

# First-time (or fresh-clone) project setup: deps + git hooks
setup:
  uv sync
  uvx pre-commit install

test *args:
    docker compose -f docker-compose.test.yml down --remove-orphans
    docker compose -f docker-compose.test.yml up -d --wait
    -uv run pytest {{args}}
    docker compose -f docker-compose.test.yml down

dev:
    docker compose -f docker-compose.dev.yml up -d

dev-build:
    docker compose -f docker-compose.dev.yml up --build -d

dev-down:
  docker compose -f docker-compose.dev.yml down

migrate message:
  docker compose -f docker-compose.dev.yml up -d --wait
  uv run alembic revision --autogenerate -m "{{message}}"
  uv run alembic upgrade head

pr:
    gh pr create --fill

lint:
  uv run ruff format
  uv run ruff check --fix .
