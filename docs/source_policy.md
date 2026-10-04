# Source Policy

Threat Situation Room is citation-first. Every summary, status, and score input should be traceable to source records or explicit analyst assumptions.

## Source Classes

- Official: government agencies, emergency-management authorities, public-health agencies, space agencies, and official security catalogs.
- Vendor: official vendor advisories and product security notices.
- Public dataset: structured public feeds and reputable open datasets.
- Reputable news: established outlets with editorial process and named sourcing.
- Local report: local media, local agency notes, or community reporting that needs corroboration.
- Social or community: public attention signals only, never confirmation by themselves.
- Unknown: insufficient provenance.

## Reliability Rules

- Official sources receive high default weight, but can still be incomplete or delayed.
- Official silence does not automatically make an event false.
- Single local or social signals must remain watchlist or unconfirmed until corroborated.
- Contradictory evidence must stay visible.
- Source records must include citation text. URLs are optional in demo records and required for live public-source ingestion where available.

## Demo Data

Seeded demo records use local citation labels such as `DEMO-CISA-KEV-001`. They are not live source claims and must be labeled as demo data in API and UI.

Offline connector fixtures pass through the same normalization and persistence path as official-feed records. Fixture imports always retain the demo flag and use distinct identities so they cannot overwrite fetched official records.

## Implemented Feeds

- USGS earthquake GeoJSON: source URLs and publication/update/retrieval timestamps are retained. A published earthquake entry does not by itself establish damage, casualties, or infrastructure disruption.
- CISA Known Exploited Vulnerabilities: read from the agency-maintained `cisagov/kev-data` mirror with that feed origin retained. Catalog inclusion establishes CISA's published exploitation classification; it does not establish that any particular organization is affected.

- Global Voices RSS: international community journalism, retained as headline/link/author metadata under the publisher's attribution policy and CC BY 3.0. Severity stays unknown; a record is placed only by the approximate headline placement rules. Author, publisher, original link and license attribution remain visible.
- GDELT DOC: free attributed discovery metadata, capped at 250 results per query. Provider observations remain separate from publisher articles. The provider's timestamp and outlet country are not publisher publication time or incident location. Candidate grouping is explicitly unverified; no full bodies, images or GEO mention pins are imported. See [pipeline limits](news-pipeline.md).
- GDACS RSS: official hazard bulletins identified by source event type and ID. Episode updates do not inflate story counts. Source GeoRSS points are approximate reference locations, with supporting report URLs. GDACS alert levels describe modelled potential humanitarian impact, not verified damage or a ThreatMon severity score. Source time windows remain separate from publication and retrieval clocks.
- NASA news RSS: bounded headline/link metadata ingestion into a separate cache. These single-publisher space/science updates have unknown severity and remain unlocated. News deduplication and explicit event associations are documented in [news coverage](news.md); synthetic fixtures never appear in the fetched snapshot edition.

Imports are stored snapshots. Retrieval time and event update time have different meanings. Refreshing the dashboard does not fetch a feed; the operator runs ingestion separately. Each news feed has independent success/failure clocks and preserves its own last good records. The NASA near-Earth-object, ReliefWeb and generic RSS clients remain reserved placeholders; the old `app/connectors/gdacs.py` placeholder is separate from the implemented GDACS news-bulletin importer in `app/news`.

## Geographic Evidence

The atlas plots points only when an event supplies `map_location` with an attached source citation. Descriptive geography labels, vendor names, and the word "Global" are not converted into guessed coordinates.

- Live USGS longitude/latitude comes directly from the GeoJSON Point and is retained in source provenance. Missing, non-point, nonnumeric, nonfinite, or out-of-range geometry fails validation. USGS automatic estimates remain visibly preliminary.
- CISA KEV supplies no incident point. Catalog records stay unlocated, even when the product has worldwide applicability. Vendor headquarters would not establish where exploitation occurred.
- Seed and fixture points use `synthetic_demo` / `illustrative`, cite demo sources, and carry explicit illustrative labels. They are not agency observations.
- Near-Earth space is nonterrestrial context; the asteroid demo is not placed on the world map.

The geographic layer is [Natural Earth public-domain data](https://www.naturalearthdata.com/about/terms-of-use/), bundled locally from a pinned source. It supplies cartographic context rather than incident evidence. Map selection guides, marker size, and styling do not assert impact areas or risk distributions. [Map coverage and attribution](map.md) records the source and projection.

## Revisions and Corroboration

Repeated retrieval of unchanged normalized content refreshes retrieval metadata without adding a material timeline entry. Changed content, including point geometry, produces a retained source revision. A return to earlier content records a new occurrence instead of leaving the intervening version active.

Multiple snapshots from the same agency are revision history, not independent corroboration. Source-record counts must not be interpreted as the number of independent reporting organizations. A failed fetch or validation leaves the previous records available; the connector's latest attempt and last successful retrieval are distinct.
