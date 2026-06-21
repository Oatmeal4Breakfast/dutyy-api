# dutyy-api task runner — run `just` to list recipes

# List available recipes
default:
    @just --list

sync:
  uv sync

test *args:
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
