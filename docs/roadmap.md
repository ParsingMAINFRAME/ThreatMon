# Roadmap

## Implemented portfolio release

- Typed event, source, claim, timeline, and score models.
- Deterministic scoring with transparent inputs and confidence labels.
- SQLAlchemy persistence, SQLite defaults, optional Postgres, and Alembic migrations.
- Four visibly labeled demo scenarios and offline ingestion fixtures.
- Read-only USGS earthquake and CISA KEV clients with provenance.
- Separate news map with unique-story hotspots, explicit event versus spatial grouping, article coverage, time filters, and synthetic multi-publisher examples.
- Bounded operator-only NASA news metadata ingestion with conditional caching and separate official/synthetic editions.
- Real Global Voices article metadata with author/license attribution and GDACS hazard bulletins with source reference locations, distinct official-report counts, independent cache health and retained-publisher filters.
- News-first routing, article-volume coverage-intensity bands, bounded GDELT metadata discovery and versioned conservative candidate associations; optional foreground polling with persisted state, not an activated service.
- Operator CLI ingestion, stable identities, and material-change timelines.
- Filtered/paginated read-only API and interactive Next.js console.
- Local vector world atlas with cited USGS points, explicit illustrative demo markers, and unlocated-record handling.
- Searchable event register and editorial evidence dossiers with keyboard-accessible map selection.
- Source citations, claim support, uncertainty, and next watch items.
- Locked dependencies, Docker Compose demo, CI, and contributor documentation.

## Next useful milestones

1. Evaluate the saved 250-article discovery sample for relevance, duplicate/syndicated reporting and grouping recall. Establish reviewed examples before loosening candidate rules or adding feeds.
2. Improve incident placement beyond approximate headline place mentions: a larger gazetteer, sub-city evidence and analyst review. Never substitute a capital or GEO mention point for a country-level mention.
3. Extend the one-hour refresh check to multi-day runs and choose a hosted deployment model. The poller and an optional Docker `poller` service exist; nothing starts them automatically.
4. Add watchlists and source-backed exposure inputs.
5. Add analyst notes and review states, followed by authentication and access controls.
6. Add alert delivery only after refresh, deduplication and stale-source behavior are defined.

## Reserved scaffolds

NASA near-Earth-object, ReliefWeb, generic RSS and the old `app/connectors/gdacs.py` module are placeholders. Working NASA, Global Voices and GDACS news ingestion is implemented under `app/news`. A reserved module's presence is not an
implemented capability. Geopolitical/infrastructure and AI incident categories are
schema options without corresponding official connectors.
