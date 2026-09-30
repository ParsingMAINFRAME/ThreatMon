"use client";

import Link from "next/link";
import { useCallback, useMemo, useRef, useSyncExternalStore } from "react";
import { CoveragePanel } from "./CoveragePanel";
import { NewsMap } from "./NewsMap";
import type { NewsResponse, NewsViewState, NewsWindow } from "@/lib/news-types";
import { assessConnectorFreshness } from "@/lib/freshness";
import { buildNewsEvents, coverageIntensity, formatNewsTime, humanizeNewsLabel, newsCoverage, newsHref, newsPublisherId, newsSources, parseNewsState, selectNewsEvents } from "@/lib/news-view";
import "@/app/news.css";

const STATE_EVENT = "threatmon-news-state";
const WINDOWS: Array<{ value: NewsWindow; label: string }> = [
  { value: "1h", label: "1 hour" }, { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" }, { value: "all", label: "All stored" },
];
const SCOPES: Array<{ value: NewsViewState["scope"]; label: string }> = [
  { value: "all", label: "Worldwide" }, { value: "located", label: "Located" },
  { value: "global", label: "Global" }, { value: "unlocated", label: "Unlocated" },
];

function subscribeLocation(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener(STATE_EVENT, callback);
  return () => { window.removeEventListener("popstate", callback); window.removeEventListener(STATE_EVENT, callback); };
}
function locationSearch() { return window.location.search; }
function serverSearch() { return ""; }

function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function NewsMonitor({ data }: { data: NewsResponse }) {
  const channel = data.channel ?? "news";
  const isSignals = channel === "signals";
  const search = useSyncExternalStore(subscribeLocation, locationSearch, serverSearch);
  const state = useMemo(() => parseNewsState(new URLSearchParams(search)), [search]);
  const events = useMemo(() => buildNewsEvents(data.events, data.as_of, state.window, state.publisherId), [data.events, data.as_of, state.window, state.publisherId]);
  const queriedEvents = useMemo(() => selectNewsEvents(events, { scope: "all", query: state.query }), [events, state.query]);
  const visibleEvents = useMemo(() => selectNewsEvents(queriedEvents, { scope: state.scope, query: "" })
    .sort((a, b) => (b.story_count + b.official_report_count) - (a.story_count + a.official_report_count) || a.id.localeCompare(b.id)), [queriedEvents, state.scope]);
  const selected = visibleEvents.find((event) => event.id === state.selectedId) ?? visibleEvents[0] ?? null;
  const counts = useMemo(() => newsCoverage(visibleEvents), [visibleEvents]);
  const coverageFocus = useRef<HTMLDivElement>(null);
  const isDemo = data.edition === "demo";
  const isFiltered = state.scope !== "all" || Boolean(state.query) || state.window !== "24h" || Boolean(state.publisherId);
  const sources = useMemo(() => newsSources(data), [data]);
  const sourceHealth = useMemo(() => sources.map((source) => ({ source, freshness: assessConnectorFreshness({
    name: source.source_id, feed_url: source.feed_url, description: source.name,
    state: source.state === "never_fetched" ? "never_run" : source.state,
    last_attempt_at: source.last_attempt_at, last_success_at: source.last_success_at,
    item_count: source.item_count, error: source.error,
  }, Date.parse(data.as_of)) })), [sources, data.as_of]);
  const publisherOptions = useMemo(() => {
    const publishers = new Map(sources.filter((source) => source.kind !== "discovery").map((source) => [source.publisher_id, source.name]));
    for (const event of data.events) for (const article of event.articles) {
      const id = newsPublisherId(article);
      if (!publishers.has(id)) publishers.set(id, article.publisher);
    }
    return Array.from(publishers, ([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
  }, [sources, data.events]);
  const recentSources = sourceHealth.filter(({ freshness }) => freshness.ageState === "within_threshold").length;
  const failedSources = sourceHealth.filter(({ source }) => source.state === "error").length;
  const staleSources = sourceHealth.filter(({ freshness }) => freshness.ageState === "stale").length;
  const unfetchedSources = sourceHealth.filter(({ freshness }) => freshness.ageState === "never_fetched").length;
  const cappedSources = sources.filter((source) => source.possibly_truncated).length;

  const updateState = useCallback((patch: Partial<NewsViewState>, replace = false) => {
    const next = { ...state, ...patch };
    const available = selectNewsEvents(buildNewsEvents(data.events, data.as_of, next.window, next.publisherId), next);
    if (next.selectedId && !available.some((event) => event.id === next.selectedId)) next.selectedId = null;
    const href = newsHref(next, data.edition, channel);
    if (replace) window.history.replaceState(window.history.state, "", href);
    else window.history.pushState(window.history.state, "", href);
    window.dispatchEvent(new Event(STATE_EVENT));
  }, [state, data.events, data.as_of, data.edition, channel]);

  function selectEvent(id: string) {
    updateState({ selectedId: id });
    requestAnimationFrame(() => {
      coverageFocus.current?.focus({ preventScroll: true });
      coverageFocus.current?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }

  return <div className="news-monitor">
    <header className="news-heading">
      <div><p className="news-eyebrow">{isSignals ? "Secondary source records" : "Collected journalism / Incident coverage"}</p><h1>{isSignals ? "Source bulletins" : "Incident news"}</h1><p className="news-heading-note">{isSignals ? "Official hazard reports and space updates, separate from the news collection." : "Explore collected articles, candidate associations and publisher coverage."}</p></div>
      <nav className="news-edition-switch" aria-label="News edition">
        <Link href={newsHref({ ...state, selectedId: isDemo ? state.selectedId : null, publisherId: isDemo ? state.publisherId : null }, "demo", "news")} aria-current={isDemo ? "page" : undefined}>Demo scenarios</Link>
        <Link href={newsHref({ ...state, selectedId: isDemo ? null : state.selectedId, publisherId: isDemo ? null : state.publisherId }, "snapshot", channel)} aria-current={!isDemo ? "page" : undefined}>{isSignals ? "Fetched bulletins" : "Fetched news"}</Link>
      </nav>
    </header>

    {isDemo ? <aside className="news-edition-notice" aria-label="Synthetic demonstration notice">
      <strong>DEMO SCENARIOS — FICTIONAL NEWS</strong>
      <p>Fictional events, publishers and stories. Iran and all map positions are illustrative; this edition reports no real incidents.</p>
      <p className="news-demo-clock">Fixed demo clock: <time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time></p>
    </aside> : <aside className="news-edition-notice news-edition-snapshot" aria-label="Snapshot source note">
      <strong>{isSignals ? "OFFICIAL BULLETINS — SECONDARY SOURCE VIEW" : "FETCHED NEWS — COLLECTED ARTICLE SAMPLE"}</strong>
      <p>{isSignals ? "Official hazard reports and space updates. Source-model alerts are not confirmed impact." : "Publisher articles and discovery-provider results. Candidate associations are unverified; collected counts are not total worldwide coverage."} Imports are manual; page refresh reads stored records.</p>
      <p className="news-demo-clock">Edition as of: <time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time>. {isSignals ? "Publication" : "Publication or first-collection"} windows end at this clock.</p>
    </aside>}

    <details className="news-sources" open={Boolean(state.publisherId)}>
      <summary><span>{isDemo ? "Demo publishers" : "Sources and freshness"}{state.publisherId ? " · publisher filter active" : ""}</span>{!isDemo ? <span>{recentSources}/{sources.length} fetched within 24h{failedSources ? ` · ${failedSources} failed` : ""}{staleSources ? ` · ${staleSources} stale` : ""}{unfetchedSources ? ` · ${unfetchedSources} never fetched` : ""}{cappedSources ? ` · ${cappedSources} possibly capped` : ""}</span> : null}</summary>
      <div className="news-source-selection">
        <label htmlFor="news-publisher"><span>{isSignals ? "Retained publisher or issuing agency" : "Article publisher"}</span><select id="news-publisher" value={state.publisherId ?? ""} onChange={(event) => updateState({ publisherId: event.target.value || null })}>
          <option value="">{isSignals ? "All retained publishers and agencies" : "All retained article publishers"}</option>
          {state.publisherId && !publisherOptions.some((option) => option.id === state.publisherId) ? <option value={state.publisherId}>Unavailable publisher selection</option> : null}
          {publisherOptions.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
        </select></label>
        <p>Counts reflect retained records from this selection. Discovery providers are not publishers. Excluded syndicated copies do not add publishers or articles.</p>
      </div>
      {!isDemo ? <details className="news-source-provenance">
        <summary>Fetch history and source attribution</summary>
        <p className="news-source-policy">Each feed keeps its own fetch history. The 24-hour threshold is a display policy, not a guarantee of current conditions. Article retrieval times can predate a successful unchanged-feed check.</p>
        <ul className="news-source-list">{sourceHealth.map(({ source, freshness }) => {
          const feedUrl = safeSourceUrl(source.feed_url);
          const termsUrl = safeSourceUrl(source.terms_url);
          const age = freshness.ageState === "stale" ? "Stale — over 24 hours" : freshness.ageState === "within_threshold" ? "Fetched within 24 hours" : freshness.ageState === "never_fetched" ? "Never fetched" : "Fetch age unknown";
          return <li key={source.source_id}>
            <div className="news-source-heading"><strong>{source.name}</strong><span>{source.kind === "official" ? "Official reports" : source.kind === "discovery" ? "Discovery provider, not a publisher" : "Publisher articles"} · {source.item_count} retained records</span></div>
            <p className={source.state === "error" || freshness.ageState === "stale" ? "news-source-warning" : undefined}>{source.state === "error" ? "Latest fetch failed. " : ""}{age}{freshness.ageLabel ? ` (${freshness.ageLabel} at edition clock)` : ""}.</p>
            <dl><div><dt>Last successful fetch</dt><dd>{formatNewsTime(source.last_success_at)}</dd></div><div><dt>Last attempt</dt><dd>{formatNewsTime(source.last_attempt_at)}</dd></div>{source.next_fetch_at ? <div><dt>Next permitted import</dt><dd>{formatNewsTime(source.next_fetch_at)}; not an automatic schedule</dd></div> : null}</dl>
            {source.error ? <p className="news-source-warning">{source.error}</p> : null}
            {source.query_window_start || source.query_window_end || source.result_limit ? <dl><div><dt>Latest provider query window</dt><dd>{formatNewsTime(source.query_window_start ?? null)} to {formatNewsTime(source.query_window_end ?? null)}</dd></div>{source.result_limit ? <div><dt>Provider result limit per query</dt><dd>{source.result_limit} records; not a total-coverage count</dd></div> : null}</dl> : null}
            {source.query ? <dl><div><dt>Discovery query</dt><dd><code>{source.query}</code></dd></div></dl> : null}
            {source.possibly_truncated ? <p className="news-source-warning">Collection limits or query-window gaps may omit coverage. This retained sample is incomplete.</p> : null}
            <p>{source.coverage_note}</p><p>{source.attribution}</p>
            <div className="news-source-links">{feedUrl ? <a href={feedUrl} target="_blank" rel="noopener noreferrer">Source feed<span className="sr-only">: {source.name} (opens in a new tab)</span></a> : null}{termsUrl ? <a href={termsUrl} target="_blank" rel="noopener noreferrer">Source terms<span className="sr-only">: {source.name} (opens in a new tab)</span></a> : null}</div>
          </li>;
        })}</ul>
      </details> : <p className="news-source-policy">All publisher labels and records in this edition are fictional. The fixed demo clock controls the publication window.</p>}
    </details>
    {!isDemo && data.fetch_state === "never_fetched" ? <p className="news-fetch-notice" role="status">No source snapshot has been fetched yet. This edition has no coverage records to display.</p> : null}
    {!isDemo && (data.fetch_state === "error" || data.fetch_state === "partial") ? <p className="news-fetch-notice" role="status">{data.fetch_state === "partial" ? "Some sources are unavailable or have not been fetched." : "The latest source import failed."} {data.events.length ? "Available stored records remain visible with their original retrieval times." : "No stored coverage is available."} Open Sources and freshness for each feed’s status.</p> : null}

    <div className="news-controls" id="news-map-top">
      <label className="news-search"><span>Find an event or publisher</span><input type="search" value={state.query} onChange={(event) => updateState({ query: event.target.value }, true)} placeholder="Search topics, places or publishers" /></label>
      <fieldset className="news-window"><legend>{isSignals ? "Published within" : "Published / first collected within"}</legend><div>{WINDOWS.map((option) => <button key={option.value} type="button" aria-pressed={state.window === option.value} onClick={() => updateState({ window: option.value })}>{option.label}</button>)}</div></fieldset>
    </div>
    <div className="news-scope-bar">
      <div className="news-scopes" role="group" aria-label="Geographic scope">{SCOPES.map((scope) => <button key={scope.value} type="button" aria-pressed={state.scope === scope.value} onClick={() => updateState({ scope: scope.value })}>{scope.label}<span>{scope.value === "all" ? queriedEvents.length : queriedEvents.filter((event) => event.scope === scope.value).length}</span></button>)}</div>
      {isFiltered ? <button className="news-clear" type="button" onClick={() => updateState({ window: "24h", scope: "all", query: "", selectedId: null, publisherId: null })}>Reset view</button> : null}
    </div>
    <p className="news-results" role="status"><strong>{counts.event_count}</strong> {counts.event_count === 1 ? "event or report group" : "events and report groups"} · <strong>{counts.story_count}</strong> collected {counts.story_count === 1 ? "article" : "articles"} from <strong>{counts.news_publisher_count}</strong> {counts.news_publisher_count === 1 ? "publisher" : "publishers"}{isSignals ? <> · <strong>{counts.official_report_count}</strong> official {counts.official_report_count === 1 ? "report" : "reports"} from <strong>{counts.official_source_count}</strong> {counts.official_source_count === 1 ? "agency" : "agencies"}</> : null}. {isSignals ? "Counts reflect this view." : "A filtered, potentially capped sample—not all reporting worldwide."}</p>

    <div className="news-workspace">
      <div className="news-overview">
        <NewsMap events={visibleEvents} selectedId={selected?.id ?? null} onSelect={selectEvent} />
        <section className="news-event-register" aria-labelledby="news-event-register-title">
          <header><h2 id="news-event-register-title">Events in this view</h2><span>Ordered by retained records, not severity</span></header>
          {visibleEvents.length ? <ol className="news-event-list">{visibleEvents.map((event) => <li key={event.id}>
            <button type="button" className={`news-event-card${event.id === selected?.id ? " is-selected" : ""}`} aria-pressed={event.id === selected?.id} onClick={() => selectEvent(event.id)}>
              <span className={`news-event-count coverage-${coverageIntensity(event.story_count)}${!event.story_count && event.official_report_count ? " is-official-report" : ""}`}><strong>{event.story_count || event.official_report_count}</strong><span>{event.story_count ? event.story_count === 1 ? "article" : "articles" : event.official_report_count === 1 ? "report" : "reports"}</span></span>
              <span className="news-event-content"><span className="news-eyebrow">{event.is_demo ? "DEMO / " : ""}{!event.story_count && event.official_report_count ? "Official report / " : ""}{humanizeNewsLabel(event.category)} · {event.scope === "global" ? "Global coverage" : event.scope === "unlocated" ? "Unlocated" : event.location?.label}</span>{event.grouping_status === "candidate" ? <span className="news-candidate-label">Candidate association · unverified</span> : null}<strong>{event.title}</strong><span className="news-event-assessment">{event.story_count ? `${event.news_publisher_count} article ${event.news_publisher_count === 1 ? "publisher" : "publishers"}` : ""}{event.official_report_count ? `${event.story_count ? " · " : ""}${event.official_report_count} official ${event.official_report_count === 1 ? "report" : "reports"} / ${event.official_source_count} ${event.official_source_count === 1 ? "agency" : "agencies"}` : ""}</span></span>
            </button>
          </li>)}</ol> : <p className="news-empty-list">No coverage records match these filters. Try a wider publication window or reset the view.</p>}
        </section>
      </div>
      <div ref={coverageFocus} tabIndex={-1} className="news-coverage-focus" aria-label="Selected news coverage"><a className="news-return-map" href="#news-map-top">Back to map and filters</a><CoveragePanel event={selected} asOf={data.as_of} edition={data.edition} /><a className="news-return-map" href="#news-map-top">Back to map and filters</a></div>
    </div>

    <section id="news-method" className="news-method" aria-labelledby="news-method-title">
      <h2 id="news-method-title">How to read this monitor</h2>
      <div><p><strong>Color measures collected coverage.</strong> Green means 1–10 unique collected articles, amber 11–30, and red 31+. Official report counts stay neutral. These are filtered, potentially capped collections, not worldwide totals. Coverage does not establish severity or certainty; those assessments remain separate in the detail panel.</p><p><strong>Keep associations provisional.</strong> A candidate grouping is an unverified association of reports, not a confirmed shared incident. Textual place hints are unverified and receive no invented map point. Neutral “N events” markers only group separate nearby events for navigation.</p><p><strong>Keep clocks and origins distinct.</strong> Known publication time controls the filter; missing publication falls back to ThreatMon’s first collection time. Provider timestamps retain their supplied meaning and are not publication times. GDELT is a discovery provider; article publishers remain separately attributed. Manual imports keep per-source fetch status.</p></div>
      <p className="news-method-note">{data.duplicates_excluded.toLocaleString()} duplicate {data.duplicates_excluded === 1 ? "record excluded" : "records excluded"} during this edition’s ingestion (before the selected time window). Publisher breadth is not independent corroboration.</p>
    </section>
  </div>;
}
