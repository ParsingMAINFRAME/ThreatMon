# Roadmap

## Implemented portfolio release

- Typed event, source, claim, timeline, and score models.
- Deterministic scoring with transparent inputs and confidence labels.
- SQLAlchemy persistence, SQLite defaults, optional Postgres, and Alembic migrations.
- Four visibly labeled demo scenarios and offline ingestion fixtures.
- Read-only USGS earthquake and CISA KEV clients with provenance.
- Separate news map with unique-story hotspots, explicit event versus spatial grouping, article coverage, time filters, and synthetic multi-publisher examples.
- Bounded operator-only NASA news metadata ingestion with conditional caching and separate official/synthetic editions.
- Operator CLI ingestion, stable identities, and material-change timelines.
- Filtered/paginated read-only API and interactive Next.js console.
- Local vector world atlas with cited USGS points, explicit illustrative demo markers, and unlocated-record handling.
- Searchable event register and editorial evidence dossiers with keyboard-accessible map selection.
- Source citations, claim support, uncertainty, and next watch items.
- Locked dependencies, Docker Compose demo, CI, and contributor documentation.

## Next useful milestones

1. Add feed refresh schedules and fetch-health history. The overview already shows the latest fetch outcome, last successful retrieval, and an explicit 24-hour stale-data indicator.
2. Add permitted general-news coverage with reviewed event associations and defensible geographic evidence; NASA news currently supplies only space/science updates.
3. Add cross-source event grouping with explainable match rules and analyst overrides.
4. Add watchlists and source-backed exposure inputs.
5. Add analyst notes and review states, followed by authentication and access controls.
6. Add alert delivery only after refresh, deduplication, and stale-source behavior are defined.

## Reserved scaffolds

NASA near-Earth-object, GDACS, ReliefWeb, and generic RSS modules are placeholders. The separate NASA news feed is implemented under `app/news`. A reserved module's presence is not an
implemented capability. Geopolitical/infrastructure and AI incident categories are
schema options without corresponding official connectors.
