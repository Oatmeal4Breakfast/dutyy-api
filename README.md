# dutyy-api

The backend for Dutyy, a project and task manager designed for a web application and a `gh`-style CLI.

Browser clients authenticate with server-side sessions and CSRF protection. CLI and direct API clients use revocable API keys.

## Getting started

Requirements:

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [just](https://github.com/casey/just)
- Python 3.14+

Clone the repository and create the local environment file:

```bash
git clone git@github.com:Oatmeal4Breakfast/dutyy-api.git
cd dutyy-api
cp .env.example .env
```

Set `FRONTEND_URL` in `.env` to the browser origin served by Caddy:

```dotenv
FRONTEND_URL=http://localhost:8080
```

Keep the default production-style session cookie (`__Host-dutyy-session`, `SECURE=true`). Browsers treat `localhost` as a secure context, so it is stored over local HTTP.

Install dependencies and Git hooks, then start the development stack:

```bash
just setup
just dev-build
```

In the separate frontend repo, start Vite so Caddy can reach it:

```bash
npm run dev
```

Vite must listen on all interfaces (`host: "0.0.0.0"`, port `5173`, `strictPort: true`).

Open the app through Caddy, not Vite or the API directly:

- App: <http://localhost:8080>
- API: <http://localhost:8000>
- OpenAPI documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## Development

```bash
just dev             # Start the existing development containers
just dev-build       # Build and start the development containers
just dev-down        # Stop the development containers
just lint            # Format and lint the codebase
just migrate "name" # Generate and apply a migration
```

## Tests

`just test` starts the test database, runs pytest, and removes the database container afterward:

```bash
just test
```

Additional pytest arguments are forwarded:

```bash
just test tests/domain
just test -k login
just test -m "not integration"
```

## Container image

Pushes to `main` publish `ghcr.io/oatmeal4breakfast/dutyy-api` with `latest` and commit-SHA tags.
