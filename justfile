# dutyy-api task runner — run `just` to list recipes

# List available recipes
default:
    @just --list

# Run the test suite (spins up the test database, tears it down after)
test *args:
    docker compose -f docker-compose.test.yml up -d --wait
    -uv run pytest {{args}}
    docker compose -f docker-compose.test.yml down

# Spin up the dev environment (app + db)
dev:
    docker compose -f docker-compose.dev.yml up

# Rebuild the app image and spin up the dev environment
dev-build:
    docker compose -f docker-compose.dev.yml up --build

# Open a PR for the current branch (auto-fills title/body from commits)
pr:
    gh pr create --fill
