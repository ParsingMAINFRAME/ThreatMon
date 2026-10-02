# Incident-news pipeline

The primary product is collected incident reporting, separate from the hazard and agency bulletin view. It is a bounded metadata pipeline with explicit uncertainty, not a complete live picture of world events.

## Coverage intensity

| Collected unique articles in the current view | Marker band |
| --- | --- |
| 1–10 | Green / low coverage intensity |
| 11–30 | Amber / medium coverage intensity |
| 31+ | Red / high coverage intensity |
| 0 or official reports only | Neutral / no news-article band |

The policy is shared by map markers, event cards and the legend. The number must equal the retained article list for that event after filters. Global totals are a union of article identities, not a sum of overlapping groups. Spatial controls labeled “N events” group separate events for navigation and remain neutral. Neither color nor publisher breadth establishes physical severity or independent confirmation. Detail panels preserve separate severity, reporting status and grouping confidence.

The illustrative Iran/35-article scenario remains explicitly fictional. No specific contemporary attack, casualty count or city location is invented to fill the map.

## Discovery and rights

[GDELT's terms](https://gdeltproject.org/about.html) permit dataset use and redistribution without a fee, with a GDELT citation and link. This does not license linked publisher bodies or images. The adapter retains headline, original URL, publisher domain, language/provider metadata and timestamps only. It does not fetch full articles, images, mobile-page alternatives or GEO popup HTML.

[DOC ArtList](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) caps a response at 250 articles. Our results are a collected, query-limited sample; reaching a response or retention cap indicates incomplete coverage. Absence from this sample proves nothing about an incident. English-language discovery and a small English headline vocabulary limit recall. Publisher domain is not the same as publisher organization, and several domains can share reporting or ownership.

Global Voices remains an independently fetched, attributed source under its existing policy. GDACS and NASA remain available in the secondary bulletin view. No new paid service, account or API key is required. Restricted BBC/Le Monde RSS feeds are not enabled.

## Articles versus provider observations

A publisher article has a canonical URL identity. Preserve semantic query parameters such as article IDs; remove only known tracking parameters and fragments. Repeated observations do not create new articles. Retain richer publisher/author/license metadata and provider observations when the same canonical article appears through multiple sources.

GDELT is a discovery provider, not the publisher of every result. Each provider observation retains its origin, retrieval time and original provider timestamp. `SourceCountry` describes the outlet, not the event. `seendate` is stored as a GDELT timestamp with unverified semantics; it never populates publisher publication time. ThreatMon's first collection time is recorded independently and preserved on refresh.

Publication filters use actual publisher publication where supplied, otherwise explicitly labeled first-collection time. These are coverage windows, not occurrence windows. Same-title stories may be syndicated or derivative; they do not establish independent confirmation. Official bulletin revisions are never news articles.

## Candidate associations and geography

Candidate matching requires compatible local-place, narrow incident-type and distinctive named/content clues, plus a bounded time interval. Every pair in a group must satisfy the rule; a chain of weak links cannot merge unrelated incidents. Country-only references, ambiguous places, conflicting dates/locations and unsupported headline types stay separate. The group retains the rule version, assignment revision and explanation.

This is intentionally conservative and limited to the documented recognition vocabulary. A candidate group is an unverified association, not an asserted incident. Unknown severity remains unknown. Article URLs remain individually inspectable.

No headline mention becomes a coordinate. [GEO](https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/) maps mentions near search terms and can contain contextual or geocoding errors; the adapter does not use it to pin incidents. DOC alone cannot supply defensible city incident points. Candidate place hints stay textual and unlocated until supported by an authoritative event identity/location or reviewed incident evidence. A country mention is not replaced by its capital. This remains the principal gap between the implemented discovery pipeline and a populated real incident-dot map.

## Refresh and failure contract

An operator import performs a bounded DOC request against a fixed HTTPS endpoint. There are no immediate GDELT retries, endpoint rotation or attempts to evade rate limits. The application uses a minimum 15-minute interval and honors longer server `Retry-After` values. This is an application policy, not a published GDELT quota. [GDELT's rate-limit notice](https://blog.gdeltproject.org/ukraine-api-rate-limiting-web-ngrams-3-0/) confirms that availability can be constrained.

Successful imports advance a persisted query watermark and overlap the previous window by 15 minutes. The initial window is 24 hours. Canonical deduplication handles overlap. Retention is bounded to 250 canonical GDELT articles within seven days; caps and coverage gaps remain visible. Failure preserves prior records, their timestamps, the previous successful watermark and the next permitted attempt.

The optional foreground polling command uses the same persisted state and importer lock. It is a single polling queue, not a deployed service. Its cadence cannot be shorter than 15 minutes. No background worker, startup task, scheduled service, alerting or deployment is activated by installing or opening the app. API requests and browser refresh read storage only.

Actual automatic operation must be demonstrated by starting an authorized worker and observing repeated successful retrievals. This milestone makes no claim of 24/7 operation.

### Operator commands

From `backend`, using the existing project environment:

```sh
uv run --frozen python -m app.cli news ingest --source gdelt
# Optional foreground process; this command has not been started for the milestone:
uv run --frozen python -m app.cli news poll --source gdelt --interval-seconds 900
```

`NEWS_GDELT_QUERY` controls bounded query text; `NEWS_POLL_INTERVAL_SECONDS` defaults to 900 and permits 900–86400. Configure API and CLI with the same `NEWS_SNAPSHOT_PATH`. Stop a foreground poller with Ctrl+C. The same cache lock protects both CLI commands; a lock left after abrupt termination requires checking that its owner is no longer running before removing that exact lock file. No automatic stale-lock deletion is performed.

### Observed availability

The first live adapter request on **September 30, 2026 at 23:24:10 UTC** returned **HTTP 429**, retained zero GDELT articles, and persisted a next permitted attempt of **23:39:10 UTC**. Its raw error headers and body were not retained, so that deadline documents application state rather than a quoted server instruction.

One request after that deadline, at **23:40:22 UTC**, returned **HTTP 200**, with `Cache-Control: public, max-age=900` and no `Retry-After` header. The adapter saved **250 canonical articles across 185 publisher domains** and advanced the watermark. Reaching the result cap made `possibly_truncated` true. There were **zero candidate event groups and zero supported incident points**. No immediate retry, endpoint substitution or background poller was used.

This establishes one successful bounded discovery sample, not dependable availability, independent corroboration or a working real incident-dot map. Broad query terms can match business, sport, commentary or unrelated uses of an incident word. Relevance evaluation and supported event geography remain unfinished. The cheapest next step is to evaluate the saved sample before adding feeds or loosening grouping rules. Local sample caches are not distributed with the code.
