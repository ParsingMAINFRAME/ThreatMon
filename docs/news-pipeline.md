# Incident-news pipeline

The primary product is collected incident reporting, separate from the hazard and agency bulletin view. It is a bounded metadata pipeline with explicit uncertainty, not a complete live picture of world events.

## Coverage intensity

| Collected unique articles in the current view | Marker band |
| --- | --- |
| 1–10 | Green / low coverage intensity |
| 11–30 | Amber / medium coverage intensity |
| 31+ | Red / high coverage intensity |
| 0 or official reports only | Neutral / no news-article band |

The policy is used by event cards. Map markers instead take their color from the reported event type (see below) and show the same article count as their number and size. The number must equal the retained article list for that event after filters. Global totals are a union of article identities, not a sum of overlapping groups. Spatial controls labeled “N events” group separate events for navigation and remain neutral. Neither color nor publisher breadth establishes physical severity or independent confirmation. Detail panels preserve separate severity, reporting status and grouping confidence.

## Map marker colors

Map marker color names the event type from the event's category, so the map reads at a glance:

| Color | Event type | Categories |
| --- | --- | --- |
| Red | Attacks, strikes and shootings | attack, explosion, shooting |
| Orange | Unrest and protests | unrest, protest |
| Blue | Natural hazards and fires | earthquake, flood, fire, wildfire, tropical_cyclone, drought, volcano, natural_hazard |
| Purple | Accidents and outages | collision, outage |
| Gray | Other news | anything else |

The mapping lives in `newsEventTypeGroup` in `frontend/src/lib/news-view.ts` and is tested. Color describes what the headlines report, not severity, certainty or verified impact; a red marker can be one unverified headline.

The illustrative Iran/35-article scenario remains explicitly fictional. No specific contemporary attack, casualty count or city location is invented to fill the map.

## Discovery and rights

[GDELT's terms](https://gdeltproject.org/about.html) permit dataset use and redistribution without a fee, with a GDELT citation and link. This does not license linked publisher bodies or images. The adapter retains headline, original URL, publisher domain, language/provider metadata and timestamps only. It does not fetch full articles, images, mobile-page alternatives or GEO popup HTML.

[DOC ArtList](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) caps a response at 250 articles. Our results are a collected, query-limited sample; reaching a response or retention cap indicates incomplete coverage. Absence from this sample proves nothing about an incident. English-language discovery and a small English headline vocabulary limit recall. Publisher domain is not the same as publisher organization, and several domains can share reporting or ownership.

Global Voices remains an independently fetched, attributed source under its existing policy. GDACS and NASA remain available in the secondary bulletin view. No new paid service, account or API key is required. Restricted BBC/Le Monde RSS feeds are not enabled.

## GDELT bulk files (default)

The DOC search API answered this project with HTTP 429 for every request over many hours, including a single small query. GDELT's rate-limit message directs such users to its published datasets, so the default `NEWS_GDELT_MODE=bulk` reads the [GDELT 2.0](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/) Global Knowledge Graph files instead. GDELT publishes one file every 15 minutes listing the articles it monitored. No search API call is made in this mode.

An import reads `lastupdate.txt` for the newest file time, builds file URLs locally on the fixed `data.gdeltproject.org` host, and downloads at most four unread files (one hour), oldest first. Downloads are capped at 16 MiB zipped and 96 MiB unzipped, with a single archive member. A persisted watermark means a later import reads only newer files; skipped older files mark the source as possibly incomplete. The 15-minute minimum interval and failure handling are unchanged.

From each record only the page title, URL, publisher domain and file time are kept. A record is retained only when the headline rules can place it and GDELT's own location list for the article names the same country. A headline that also names a US state or Canadian province is not placed at a foreign city. Same-name towns remain a known error: GDELT itself geocoded a shooting in Athens, Alabama to Greece, and that headline was placed at Athens, Greece. GDELT coordinates are never used. The 250-article, seven-day retention still applies. Expect a handful of placed headlines per file, so regular polling is what builds coverage.

Set `NEWS_GDELT_MODE=doc` to use the DOC search API described below.

## Wikipedia Current events

The [Current events portal](https://en.wikipedia.org/wiki/Portal:Current_events) is an editor-curated daily list of one-sentence entries, each citing sources. One bounded MediaWiki API request reads the pages for today and the two previous UTC days, with a descriptive User-Agent and the same 15-minute minimum interval. Only the incident-related sections are kept (armed conflicts and attacks, disasters and accidents, law and crime, politics and elections, health and environment, international relations), at most 120 entries.

Entry text is written by Wikipedia contributors and reused under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) with attribution and a link to the portal page. It is not the linked publisher's headline. Each entry is stored against the first source URL it cites, so the reader can open the original report. The portal day is an editor-chosen event day and is kept as a provider timestamp, never as a publication time. Entries are placed and grouped by the same headline rules as every other article, with two additions from the portal's own structure (see Placement below). Each entry also keeps its section, the topic headings it is nested under (such as `Gaza war`) and the titles of the articles it links to. Coverage depends on what volunteers have added and is incomplete.

Al Jazeera and UN News feeds were reviewed and not enabled: their terms limit use to personal, non-commercial access.

## Articles versus provider observations

A publisher article has a canonical URL identity. Preserve semantic query parameters such as article IDs; remove only known tracking parameters and fragments. Repeated observations do not create new articles. Retain richer publisher/author/license metadata and provider observations when the same canonical article appears through multiple sources.

GDELT is a discovery provider, not the publisher of every result. Each provider observation retains its origin, retrieval time and original provider timestamp. `SourceCountry` describes the outlet, not the event. `seendate` is stored as a GDELT timestamp with unverified semantics; it never populates publisher publication time. ThreatMon's first collection time is recorded independently and preserved on refresh.

Publication filters use actual publisher publication where supplied, otherwise explicitly labeled first-collection time. These are coverage windows, not occurrence windows. Same-title stories may be syndicated or derivative; they do not establish independent confirmation. Official bulletin revisions are never news articles.

## Candidate associations and geography

Rule version `headline-place-v4` reads each English headline for two things: an incident word (attack, strike, bombing, missile, drone, explosion, shooting, riot, coup, protest, fire, flood, earthquake, storm, cyclone, landslide, eruption, outage, crash, derailment, capsizing, collapse, stampede) and a place from the built-in gazetteer in `app/news/gazetteer.py`. The gazetteer is a hand-curated table of about 150 conflict-relevant cities and 95 countries, extended with Natural Earth 1:50m populated places and country centroids (`app/news/gazetteer_natural_earth.py`, generated by `backend/scripts/build_gazetteer.py`). Curated entries always win. Generated names are dropped when they repeat, are part of a longer place name, sit within 25 km of a curated city (spelling variants such as "Kiev"), or are also common words, personal names or US state names (`Mary`, `Washington`, `Georgia`).

**Placement.** A headline that reports an incident and names one clear place is put on the map at that place's reference point:

- One recognized city: the city centre. `Ukraine bombs Moscow` is placed at Moscow.
- Several places: only the one introduced by a targeting word (`in`, `on`, `near`, `hits`, `strikes`, `bombs` and similar). `Russia strikes Ukraine` is placed at Ukraine; `Iran and Israel trade attacks` stays unlocated.
- A country alone: the country's rough geographic centre, never its capital, and only when the country is targeted or leads the headline. `Bomb blast kills three in Saudi Arabia` is placed at the centre of Saudi Arabia. `Flight to Israel diverted after attack` stays unlocated.
- Wikipedia Current events only: an entry filed under *Armed conflicts and attacks* counts as an attack report even without an incident word (`Militants kill nine villagers`). An entry whose own text names no place at all is placed at the country its topic headings name (`Myanmar civil war`), labeled `(country named in topic heading)`. A heading that pairs parties (`Israel–Hezbollah conflict`) or names several countries places nothing, and the entry's own text always wins over its heading.
- Wikipedia linked places: after reading the portal, one more bounded request (at most two, 50 titles each) asks the MediaWiki API for the primary coordinates of the articles entries link to. Only coordinates typed as an event, town, landmark, airport, station, campus, island or administrative area count; countries, rivers, mountains and untyped coordinates do not. An entry is placed at its single finest linked place (`event` before towns before districts before regions) when every other linked place, and any city its text names, lies within 400 km. Two peer towns in one entry leave the headline rules in charge. These positions are labeled `(linked Wikipedia place)`, link to the place article and keep `confidence: low`. If the lookup fails, entries are kept without coordinates and the source shows the reason.

Every such position carries `precision: approximate_area`, `confidence: low`, a label ending in `(place named in headline)`, `(country named in headline)` `(country named in topic heading)` or `(linked Wikipedia place)`, and a basis sentence saying it is not a verified incident site. The map and detail panel show that wording. Headlines that are historical, speculative, ambiguous (`Tripoli` without its country, `Paris, Texas`), or that use an incident word figuratively (`heart attack`, `rail strike`, `under fire`, `landslide victory`, `talks collapsed`, `stocks sank`, sport) stay unlocated. Publication names such as `New York Times` and a trailing `| Publisher` are not read as places. Publisher country, GDELT `SourceCountry` and [GEO](https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/) results are never used for placement.

**Analyst review.** An operator can correct an automatic position from the command line; the HTTP API stays read-only. Reviews are stored per article URL in `<snapshot>.placement-reviews.json` beside the news snapshots, so the poller never overwrites them and they survive regrouping. The event that currently contains the article takes its newest review.

```bash
uv run --frozen python -m app.cli news review --url <article-url> --confirm --note "Matches the cited report" --reviewer Ryan
uv run --frozen python -m app.cli news review --url <article-url> --move 31.53 34.48 --label "Jabalia, Gaza Strip" --note "Report names Jabalia" --reviewer Ryan
uv run --frozen python -m app.cli news review --url <article-url> --remove --note "No single place is supported" --reviewer Ryan
uv run --frozen python -m app.cli news review --url <article-url> --clear
uv run --frozen python -m app.cli news review --list
```

A confirmation raises the position's confidence to medium and applies only while the automatic position is the one the analyst saw. A moved position is labeled `(analyst-set position)` with medium confidence. A removal unlocates the event. The detail panel shows each review with its reviewer, time and note. A review is an analyst judgement, not an official incident location.

**Association.** Articles from two or more publishers form one candidate event when they name the same place and incident type and every pair falls within 24 hours without conflicting explicit dates. Country-level matches must also share two content words, because a whole country is too broad to assume one incident. Every pair in a group must satisfy the rule; a chain of weak links cannot merge. The group retains the rule version, assignment revision and explanation. Article count per event drives the coverage-intensity color.

**Known limits.** This is keyword matching, not verification. Separate incidents in one city on one day can be combined. A figurative or unrelated use of an incident word can slip through and produce a wrong marker. The gazetteer covers about 1,100 cities and 200 countries; smaller towns, other places, demonyms (`Syrian`, `Russian`) and non-English headlines are not placed. A candidate group is an unverified association, not an asserted incident. Unknown severity remains unknown. Article URLs remain individually inspectable.

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
