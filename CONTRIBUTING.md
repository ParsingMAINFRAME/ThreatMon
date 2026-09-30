# Contributing

Threat Situation Room prioritizes traceable evidence and clear uncertainty. Read
[AGENTS.md](AGENTS.md) and the [source policy](docs/source_policy.md) before changing
connectors, scoring, or evidence handling.

## Development

Follow the native setup in the [README](README.md). Backend domain models and
services live separately from HTTP routes; connector tests use local fixtures and
HTTP mocks. No network access is required to run tests.

Before submitting a change:

```sh
cd backend
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
cd ../frontend
npm ci
npm run lint
npm run build
```

Add meaningful tests for normalization, scoring, status, reliability, persistence,
or API changes. Keep feed endpoints fixed to reviewed official sources. Distinguish
fixture records from live fetched records, and avoid credentials in fixtures or logs.

For dependency changes, update `backend/uv.lock` or `frontend/package-lock.json`.
Document schema changes with an Alembic migration. Describe the visible behavior,
source assumptions, limitations, and validation in your pull request.
