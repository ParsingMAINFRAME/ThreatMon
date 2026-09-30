# News events and source coverage

The news view organizes reports about individual events and keeps their evidence inspectable. A marker represents an event with a supported location. Opening it shows its articles, publishers, publication times, and retrieval times. Coverage, severity, and geographic precision are separate attributes.

## Event identity and coverage counts

- Deduplicate articles by a stable source identifier or normalized canonical article URL. Fetching the same article again updates retrieval metadata; it does not increase coverage.
- Group separate articles only when explicit event identifiers or reviewed event-specific evidence establish that they describe the same event. A shared country, keyword, publisher, or publication date is insufficient.
- Keep distinct nearby events separate. A spatial marker group opens an event picker; it does not combine their articles into one incident or add their severity values.
- Derive the displayed article count from the actual deduplicated article collection. Count unique publishers separately. Several articles from one publisher are not several independent sources, and syndicated copies are not independent corroboration.
- Every article retains its own URL and timestamps. A coverage count describes collected reporting, not casualties, affected people, completeness, or the probability that a claim is true.

The illustrative **Iran explosion / 35 articles** scenario is fictional demonstration data, not current news or evidence of an actual incident. Demo publishers and locations must remain visibly synthetic. A displayed count of 35 is valid only when the fixture contains 35 distinct article records; the UI must use the actual collection count.

## Severity, geography, and time

Severity describes supported event impact. It does not rise because an event has more articles, more publishers, or a larger map marker. Retain an explicit unknown value when impact evidence is absent. Publication by an official organization confirms the origin of that publication; it does not by itself establish a severe threat.

Locate events only from attached geographic evidence. Publisher headquarters, a country mentioned in a headline, and a story's source country do not establish an incident point. Preserve location precision and provenance; a regional label must not masquerade as an exact coordinate. Unlocated records remain accessible in the register. Synthetic demo points are explicitly illustrative.

Keep the following times distinct and display them in UTC:

- **Published:** the publication time supplied for the article.
- **Retrieved:** when this application successfully obtained its metadata.
- **Occurred:** the event time, only when supported by the source; otherwise unknown.

Refreshing the page reads stored records. It does not fetch publishers. A failed import preserves earlier records, whose retrieval age remains visible. A successful conditional check can confirm an unchanged feed without creating new articles or making their publication dates more recent.

## Bounded NASA metadata feed

The initial official-news source is [NASA's public RSS feed](https://www.nasa.gov/feed/). Its coverage is NASA space, science, and agency updates. General worldwide news ingestion and automatic multi-publisher event matching are not implemented by this connector.

Retain only headline, the normalized feed-provided article link, publisher `NASA`, publication time, retrieval time, and ingestion provenance. Stable article and event IDs derive from the normalized article URL; raw feed GUIDs are not retained. Summaries are app-authored source notices, not copied descriptions. Do not fetch article pages or store descriptions, article bodies, images, or logos. NASA updates have unknown severity and no map point; this connector does not extract geographic coordinates.

The connector boundary is a fixed HTTPS endpoint with redirects disabled, no credentials, manual operator ingestion, at most 10 items, and a response cap of 1 MiB. Requests have a 15-second timeout, at most three transient attempts, and a 45-second overall deadline. A persisted cache prevents operator attempts within five minutes of the previous attempt, including failures, and honors longer server backoff. Run one importer at a time: the local cache does not coordinate concurrent operators, and an unwritable cache cannot persist a cooldown. Successful responses retain `ETag` / `Last-Modified` validators for subsequent conditional requests. Page refreshes do not initiate network ingestion.

A bounded availability check on **2026-09-30 at 21:53 UTC** returned HTTP 200, 10 items, and 194,684 bytes. The response supplied `Cache-Control: max-age=300, must-revalidate`, an ETag, and Last-Modified. The two sampled items contained no coordinate fields. These observations establish availability at that time, not an uptime guarantee. The five-minute cache duration follows the observed response header; it is not a published request quota.

### Run an import

Use the native backend environment described in the repository README. From the repository root:

```sh
cd backend
uv run --frozen python -m app.cli news ingest
```

The news connector stores its snapshot in a separate JSON cache; it does not change the threat database schema. `NEWS_SNAPSHOT_PATH` defaults to `./.artifacts/news/nasa-snapshot.json`, relative to the backend working directory. The CLI also accepts `--cache-path`; when overriding it, configure the API's `NEWS_SNAPSHOT_PATH` to the same file. Run the API and the default CLI command from `backend` so their relative paths agree.

The read-only endpoint is `GET /news?edition=demo` or `GET /news?edition=snapshot`. The default edition is demo. Snapshot requests read the existing cache; they do not initiate an import. A missing or failed snapshot must not silently turn into demo records.

`as_of` anchors the response's time filters, with a fixed clock for reproducible demo data. `fetched_at` records the last successful retrieval or revalidation; `last_attempt_at` records the most recent operator attempt. Each article's `retrieved_at` records when its metadata body was retrieved and remains unchanged after an HTTP 304 response. A failed attempt retains the last good snapshot and exposes the failure separately.

### Source use and attribution

NASA's [media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) permit factual informational use subject to their conditions, require source acknowledgement, and prohibit implied endorsement. Third-party copyrighted material is an exception; NASA branding has separate restrictions. This integration displays source headlines and links with publisher attribution and omits media assets. App-authored classifications or interpretations must remain distinguishable from NASA's supplied metadata.

### Other sources

- **BBC:** reuse terms and a permitted integration have not been verified for this release; no BBC connector is enabled.
- **GDELT:** [DOC](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and [GEO](https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/) are possible future discovery sources, with no verified integration here. DOC source-country metadata describes the publisher. GEO locations can represent nearby place mentions and contain geocoding errors; neither establishes an incident location or a shared event.
- **ReliefWeb:** its [API documentation](https://apidoc.reliefweb.int/) requires a pre-approved appname from November 1, 2025. No account or approval was obtained, so it is outside this no-registration integration.

Demonstration coverage stays separate from retrieved NASA records. Synthetic multi-publisher examples demonstrate the interaction and data model; they do not establish live worldwide monitoring.
