# dutyy-api

A task management API that powers a web UI and a `gh`-style CLI so you can manage projects and tasks without ever leaving your terminal.

## Getting started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.14+

### Setup

1. Clone the repo and copy the environment file:

```bash
git clone git@github.com:Oatmeal4Breakfast/dutyy-api.git
cd dutyy-api
cp .env.example .env
```

2. Start the database and API:

```bash
docker compose -f docker-compose.dev.yml up --build
```

The API will be available at `http://localhost:8000` and the auto-generated docs at `http://localhost:8000/docs`.

### Running without Docker

```bash
uv sync
uvicorn src.dutyy_api.main:app --reload
```
