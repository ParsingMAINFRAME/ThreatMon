# Data Model

The application uses Pydantic models for API/domain contracts. Official-signal records persist through SQLAlchemy in SQLite or Postgres; Alembic manages that schema. News metadata uses separate atomic JSON caches. Startup can seed local official-signal demo records; news demo fixtures are an explicitly selected edition.

## News contracts

| Model | Purpose |
| --- | --- |
| `NewsArticle` | Canonical URL identity, original link, headline, publisher identity, nullable publication date, first collection, retrieval, attribution and optional duplicate aliases. |
| `NewsObservation` | Discovery provider, provider URL, supplied timestamp and raw value, retrieval, language and publisher-country metadata. It does not establish incident location. |
| `NewsEvent` | Retained articles and a source event, single-source item or unverified candidate association; assignment version/revision, textual place hints, reporting status, separate severity and optional supported location. |
| `NewsSourceStatus` | Last attempt and successful fetch, error, next permitted attempt, query window and result limits. |
| `NewsResponse` | Explicit snapshot/demo edition, news/signals channel, response clock, source health and retained events. |

News article totals are unions of canonical identities. Official-bulletin revisions are distinct from news articles. Coverage intensity is a display of filtered retained article volume, not a severity model. See [news contracts and limitations](news-pipeline.md).

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
