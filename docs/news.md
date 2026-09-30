# News events and source coverage

The default fetched view combines international journalism with clearly distinguished official hazard bulletins. A marker represents a source event with a supported reference location. Opening it shows retained coverage, publisher and author attribution, source clocks, and geographic evidence. News articles and official reports have separate counts. Coverage, severity, and geographic precision remain separate attributes.

## Event identity and coverage counts

- Deduplicate articles by a stable source identifier or normalized canonical article URL. Fetching the same article again updates retrieval metadata; it does not increase coverage.
- Group separate articles only when explicit event identifiers or reviewed event-specific evidence establish that they describe the same event. A shared country, keyword, publisher, or publication date is insufficient.
- Keep distinct nearby events separate. A spatial marker group opens an event picker; it does not combine their articles into one incident or add their severity values.
- Derive the displayed article count from the actual deduplicated article collection. Count unique publishers separately. Several articles from one publisher are not several independent sources, and syndicated copies are not independent corroboration.
- Every article retains its own URL and timestamps. A coverage count describes collected reporting, not casualties, affected people, completeness, or the probability that a claim is true.
- Fetched articles currently remain separate single-publication records. No headline-similarity or inferred candidate grouping is enabled. Multiple articles from one country do not become one incident. A publisher selector concerns retained records, not discarded syndicated copies.
- GDACS identities use event type plus source event ID. Episodes are revisions of that bulletin, not extra news stories or independent corroboration. Its map markers count official reports and use a distinct shape.

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

An included official-news source is [NASA's public RSS feed](https://www.nasa.gov/feed/). Its coverage is NASA space, science, and agency updates. It does not supply worldwide incident coverage or automatic multi-publisher event matching.

Retain only headline, the normalized feed-provided article link, publisher `NASA`, publication time, retrieval time, and ingestion provenance. Stable article and event IDs derive from the normalized article URL; raw feed GUIDs are not retained. Summaries are app-authored source notices, not copied descriptions. Do not fetch article pages or store descriptions, article bodies, images, or logos. NASA updates have unknown severity and no map point; this connector does not extract geographic coordinates.

The connector boundary is a fixed HTTPS endpoint with redirects disabled, no credentials, manual operator ingestion, at most 10 items, and a response cap of 1 MiB. Requests have a 15-second timeout, at most three transient attempts, and a 45-second overall deadline. A persisted cache prevents operator attempts within five minutes of the previous attempt, including failures, and honors longer server backoff. Run one importer at a time: the local cache does not coordinate concurrent operators, and an unwritable cache cannot persist a cooldown. Successful responses retain `ETag` / `Last-Modified` validators for subsequent conditional requests. Page refreshes do not initiate network ingestion.

A bounded availability check on **2026-09-30 at 21:53 UTC** returned HTTP 200, 10 items, and 194,684 bytes. The response supplied `Cache-Control: max-age=300, must-revalidate`, an ETag, and Last-Modified. The two sampled items contained no coordinate fields. These observations establish availability at that time, not an uptime guarantee. The five-minute cache duration follows the observed response header; it is not a published request quota.

### Run an import

Use the native backend environment described in the repository README. From the repository root:

```sh
cd backend
uv run --frozen python -m app.cli news ingest --source all
uv run --frozen python -m app.cli news ingest --source globalvoices
uv run --frozen python -m app.cli news ingest --source gdacs
uv run --frozen python -m app.cli news ingest --source nasa
```

The importer stores separate JSON caches; it does not change the threat database schema. `NEWS_SNAPSHOT_PATH` defaults to `./.artifacts/news/nasa-snapshot.json`, relative to the backend working directory. That existing file remains NASA's cache; Global Voices and GDACS use adjacent `<stem>.globalvoices.json` and `<stem>.gdacs.json` files. The CLI also accepts `--cache-path`; configure the API to the same base file when overriding it. Run both from `backend` so relative paths agree. The default CLI source is `all`; individual sources can be selected explicitly.

The read-only endpoint is `GET /news?edition=demo` or `GET /news?edition=snapshot`. The default edition is snapshot. Requests read the existing caches; they do not initiate an import. A missing or failed snapshot never silently turns into demo records.

`as_of` anchors time filters, with a fixed clock for demo data. Aggregate `fetched_at` is the latest successful retrieval or revalidation of **any** source; it cannot establish that every source is current. Each entry in `sources[]` retains its own outcome, last attempt/success, retained count and next allowed attempt. Each article's `retrieved_at` remains unchanged after HTTP 304. A failed source preserves its last good snapshot; other sources can succeed, producing a partial state.

### Real journalism: Global Voices

[Global Voices' official RSS guidance](https://globalvoices.org/feeds/) welcomes feed embedding. Its [republication policy](https://globalvoices.org/about/global-voices-attribution-policy/) licenses its own content under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/), with author credit, original-source and license links, change attribution and no implied endorsement. Third-party media has separate rights. This integration retains only headline, source URL, publisher, `dc:creator`, publication/retrieval times and provenance. It discards descriptions, full text and media; the UI identifies this as a metadata-only presentation with an app-authored source notice.

The fixed endpoint is `https://globalvoices.org/feed/`. The app retains at most 20 articles and limits the response to 1 MiB. A check on **2026-09-30 at 22:31 UTC** returned HTTP 200, 252,117 bytes and 15 items, with publication dates and author fields. ETag and Last-Modified were present. These observations establish availability at that time only.

Coverage is international community journalism and analysis, not a comprehensive wire service or a validated threat feed. Articles remain unlocated and severity stays unknown. No incident point is inferred from a headline, country category, author location or publisher address.

### Real hazard bulletins: GDACS

[GDACS integration guidance](https://www.gdacs.org/About/overview.aspx) explicitly supports use of its data and estimated impacts in other websites through RSS and standard formats. Its [terms](https://www.gdacs.org/About/termofuse.aspx) describe model outputs and their limitations; they are not a substitute for official alerts. The linked [European Commission legal notice](https://commission.europa.eu/legal-notice_en) supplies the reuse framework for EU-owned content, with third-party exceptions. Attribute GDACS / European Commission, United Nations, retain report and terms links, and identify the app's metadata selection and approximate map presentation.

The fixed endpoint is `https://www.gdacs.org/xml/rss.xml`. The app retains up to 30 source events after deduplicating episodes; its 1 MiB response cap and bounded selection do not promise complete hazard coverage. A September 30, 2026 check returned HTTP 200, 618,894 bytes and 201 unique event identities across six hazard types, with ETag and Last-Modified. These are dated observations, not an ongoing availability claim.

GeoRSS reference positions remain `approximate_area` with unknown precision confidence and a supporting report URL. They do not establish an exact affected location, hazard extent or impact radius. Green, Orange and Red are displayed as **GDACS source alert levels**, describing modelled potential humanitarian impact; they are not mapped to a validated ThreatMon severity score. Status remains reported. Zero-valued impact fields are not translated into claims of no harm.

RSS `pubDate` describes publication of the feed record. `fromdate` and `todate` remain separately named source-window fields. A source window may lie in the future or contain inconsistent provider metadata; it is never silently presented as a confirmed occurrence time. The UI must preserve this distinction.

### Operation and failure behavior

New feeds use a minimum 15-minute application cooldown, honoring longer server cache/backoff instructions. NASA retains its five-minute minimum. Fetches are fixed-host, credential-free, redirect-disabled and bounded; they accept validated UTF-8 RSS and reject DTD/entity declarations. Each source retains conditional validators and its own last good cache.

Only an explicit operator CLI import contacts publishers. API reads, browser refreshes and an open tab do not run ingestion. No scheduler, daemon, alert delivery or deployed 24/7 monitoring service is installed or active. Run a single importer at a time. UI staleness means more than 24 hours since that source's successful retrieval under a stated display policy, not a provider SLA or proof about current conditions.

### Source use and attribution

NASA's [media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) permit factual informational use subject to their conditions, require source acknowledgement, and prohibit implied endorsement. Third-party copyrighted material is an exception; NASA branding has separate restrictions. This integration displays source headlines and links with publisher attribution and omits media assets. App-authored classifications or interpretations must remain distinguishable from NASA's supplied metadata.

### Other sources

- **NPR:** the [terms](https://www.npr.org/about-npr/179876898/terms-of-use#ContentFeeds) permit attributed personal feed use but include a non-promotional restriction. Portfolio use was not treated as cleared. Its public World feed responded successfully during research; no NPR connector is enabled.
- **BBC:** [official help](https://www.bbc.co.uk/news/10628494) permits attributed website headlines without logos, but the linked additional RSS terms returned 404 during review. Its World feed responded successfully; incomplete current-terms clearance kept it out of this integration.
- **GDELT:** its [terms](https://gdeltproject.org/about.html) permit dataset reuse with attribution, but a bounded DOC metadata probe returned HTTP 429 at 22:29:15 UTC on September 30, 2026. No working integration is claimed and no restriction was bypassed. [DOC](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) source-country describes the publisher; [GEO](https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/) can reflect place mentions rather than verified incident locations.
- **ReliefWeb:** its [API documentation](https://apidoc.reliefweb.int/) requires a pre-approved appname from November 1, 2025. No account or approval was obtained, so it is outside this no-registration integration.

Demonstration coverage stays separate from all fetched records. Synthetic multi-publisher examples demonstrate the interaction and data model; they do not establish live worldwide monitoring. The fetched edition improves real coverage while remaining limited in publisher breadth and event association.

## Integration evidence

On September 30, 2026 at 22:43 UTC, the implemented importer successfully stored 15 Global Voices articles, 30 GDACS official bulletins and 10 NASA articles. All 55 original URLs returned HTTP 200 to bounded HEAD-only checks at 22:45 UTC; no article bodies were requested. The fetched edition has 25 news articles and 30 official reports, not 55 news articles. The default 24-hour publication window narrows that stored collection. All article locations remain unassigned; the map shows only the 30 source-provided GDACS reference positions, with spatial navigation groups keeping distinct event identities.

The existing 1,762 USGS/CISA source records remained separate and unchanged during verification. This is a local, dated snapshot check. It does not establish continuous operation, independent corroboration, comprehensive world-news coverage, or ongoing source availability.
