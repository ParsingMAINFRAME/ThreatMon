# Portfolio release implementation

## Objective

Make Threat Situation Room a runnable public portfolio project with a polished
console, genuine official-feed ingestion, inspectable evidence, and documented
verification.

## Boundaries

- Clearly label seeded and fixture records as demo.
- Treat fetched feed records as stored snapshots.
- Keep the HTTP API read-only and source endpoints fixed.
- Keep deterministic scoring explicit and tested.
- Do not claim automated clustering, alerting, authentication, or impact prediction.

## Architecture

USGS and CISA clients emit typed source signals. Normalization attaches provenance
and policy-based scoring assumptions. Persistence uses stable identities and
material-change timelines. FastAPI exposes filtered records to the Next.js console.
SQLite is the default local database; Postgres remains an optional configuration.

## Validation

- Unit and integration tests run offline with isolated databases and HTTP mocks.
- Frontend lint and production build verify contracts and dynamic routes.
- Browser review exercises dashboard search/filtering and event evidence views.
- GitHub Actions repeats tests/build and adds a Docker Compose smoke check.

## Delivery

Local Git repository, source/score documentation, locked dependencies, MIT license,
contribution guidance, full Compose demo, and screenshots. Public GitHub publication
is a separate user-directed action.
