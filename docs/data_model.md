# Data Model

The application uses Pydantic models for API/domain contracts and SQLAlchemy records for persistence. Startup can seed local demo records into SQLite or Postgres. Alembic manages the schema. An operator CLI ingests official feed records or clearly labeled offline fixtures.

## ThreatEvent

Represents one monitored event. Official connector records use stable feed identities; automated cross-source clustering is planned.

Fields include:

- `id`
- `title`
- `category`
- `geography`
- `map_location` (nullable)
- `status`
- `summary`
- `score`
- `sources`
- `extracted_claims`
- `timeline`
- `key_uncertainties`
- `contradictory_evidence`
- `next_watch_items`
- `implications`
- `updated_at`
- `is_demo`

## SourceItem

Represents a source record or citation.

Fields include:

- `id`
- `title`
- `source_name`
- `source_type`
- `reliability_tier`
- `citation`
- `url`
- `published_at`
- `retrieved_at`
- `is_official`
- `is_demo`
- `notes`
- `provenance`

## MapLocation

An optional geographic point attached to a source citation. `geography` remains a list of descriptive labels; it is not geocoded into a point.

| Field | Contract |
| --- | --- |
| `lon` | Finite numeric longitude, −180 to 180 degrees |
| `lat` | Finite numeric latitude, −90 to 90 degrees |
| `label` | Human-readable location; demo labels explicitly say illustrative |
| `precision` | `reported_point` or `illustrative` |
| `origin` | `source_reported` or `synthetic_demo` |
| `source_id` | ID of a source attached to the event |

`source_reported` pairs with `reported_point`. `synthetic_demo` pairs with `illustrative` and requires both a demo event and a demo source. The event model validates the attached citation and origin consistency.

Live USGS records copy longitude and latitude from the feed's GeoJSON Point. Their source provenance retains `location_geometry` and `location_origin`. CISA KEV records and the nonterrestrial asteroid scenario have `map_location=null`; the console does not invent coordinates for them. The fresh seed set contains two illustrative demo points.

A point locates the event record; it does not encode a damage radius, affected population, organization exposure, or location uncertainty ellipse. See [map semantics](map.md).

## ExtractedClaim

Represents a claim extracted from a source.

Fields include:

- `id`
- `source_id`
- `text`
- `support_level`
- `confidence`
- `is_material`
- `contradicts_claim_ids`

## ThreatScore

Represents deterministic scoring output.

Fields include:

- `severity`
- `credibility`
- `velocity`
- `exposure`
- `uncertainty_penalty`
- `priority`
- `confidence`
- `rationale`

## ThreatTimelineEntry

Represents a material change in the event timeline.

Fields include:

- `id`
- `occurred_at`
- `title`
- `description`
- `source_ids`
- `material_change`

## Persistent Tables

- `threat_events`: event identity, category, geography, nullable point location, status, summary, uncertainty lists, implication lists, update time, and demo flag.
- `threat_scores`: one score row per threat with deterministic score inputs and rationale.
- `source_items`: citation records and source reliability metadata.
- `threat_sources`: many-to-many relationship between threats and sources.
- `extracted_claims`: source-backed claims, support level, confidence, materiality, and contradiction references.
- `threat_timeline_entries`: material timeline entries and source references.
- `ingestion_runs`: connector, origin mode, timestamps, result counts, and a sanitized failure message.

The database stores enum values as explicit strings. List fields are JSON so the schema remains portable across SQLite and Postgres.

## Origin and updates

`is_demo` distinguishes seeded/fixture records from fetched official records. API list metadata distinguishes empty, demo, live, and mixed results. Source retrieval timestamps describe ingestion; event update timestamps describe the source's event revision where available. A material-change timeline records revisions without creating a duplicate event on each import.

Content fingerprints include the normalized point geometry and label, excluding its derived `source_id`. A changed reported point can therefore create a new revision even when the place text is unchanged. Timestamp-only USGS updates refresh metadata without adding material history. A return to previously seen content creates a new revision occurrence with a distinct citation ID.

Application timestamps are UTC. SQLite drops timezone information on storage, so repository readback restores UTC before returning domain/API records. `0003_map_locations` adds the nullable JSON point column; existing records can remain unlocated after migration.
