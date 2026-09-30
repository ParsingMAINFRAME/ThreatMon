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

1. Validate an explicitly authorized deployed refresh worker over repeated successful fetches. The optional foreground GDELT poller exists; no automatic service is active. Preserve fetch-health history and stale-data indicators.
2. Broaden permitted world-news publisher coverage beyond Global Voices, with reviewed event associations and defensible article geography. GDACS provides official hazard bulletins; NASA remains space/science coverage.
3. Add analyst review and defensible incident-location evidence to the conservative candidate groups. DOC headline place references remain unlocated; never replace missing evidence with a capital or GEO mention point.
4. Add watchlists and source-backed exposure inputs.
5. Add analyst notes and review states, followed by authentication and access controls.
6. Add alert delivery only after refresh, deduplication, and stale-source behavior are defined.

## Reserved scaffolds

NASA near-Earth-object, ReliefWeb, generic RSS and the old `app/connectors/gdacs.py` module are placeholders. Working NASA, Global Voices and GDACS news ingestion is implemented under `app/news`. A reserved module's presence is not an
implemented capability. Geopolitical/infrastructure and AI incident categories are
schema options without corresponding official connectors.
