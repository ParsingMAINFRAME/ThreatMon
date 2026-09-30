"use client";

import Link from "next/link";
import { useCallback, useMemo, useRef, useSyncExternalStore } from "react";
import { CoveragePanel } from "./CoveragePanel";
import { NewsMap } from "./NewsMap";
import type { NewsResponse, NewsViewState, NewsWindow } from "@/lib/news-types";
import { assessConnectorFreshness } from "@/lib/freshness";
import { buildNewsEvents, formatNewsTime, humanizeNewsLabel, newsCoverage, newsHref, newsPublisherId, newsSources, parseNewsState, selectNewsEvents } from "@/lib/news-view";
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
    const publishers = new Map(sources.map((source) => [source.publisher_id, source.name]));
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

  const updateState = useCallback((patch: Partial<NewsViewState>, replace = false) => {
    const next = { ...state, ...patch };
    const available = selectNewsEvents(buildNewsEvents(data.events, data.as_of, next.window, next.publisherId), next);
    if (next.selectedId && !available.some((event) => event.id === next.selectedId)) next.selectedId = null;
    const href = newsHref(next, data.edition);
    if (replace) window.history.replaceState(window.history.state, "", href);
    else window.history.pushState(window.history.state, "", href);
    window.dispatchEvent(new Event(STATE_EVENT));
  }, [state, data.events, data.as_of, data.edition]);

  function selectEvent(id: string) {
    updateState({ selectedId: id });
    requestAnimationFrame(() => {
      coverageFocus.current?.focus({ preventScroll: true });
      coverageFocus.current?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }

  return <div className="news-monitor">
    <header className="news-heading">
      <div><p className="news-eyebrow">Public reporting / Geographic coverage</p><h1>World news monitor</h1><p className="news-heading-note">Explore event coverage, sources and uncertainty.</p></div>
      <nav className="news-edition-switch" aria-label="News edition">
        <Link href={newsHref({ ...state, selectedId: isDemo ? state.selectedId : null, publisherId: isDemo ? state.publisherId : null }, "demo")} aria-current={isDemo ? "page" : undefined}>Demo scenarios</Link>
        <Link href={newsHref({ ...state, selectedId: isDemo ? null : state.selectedId, publisherId: isDemo ? null : state.publisherId }, "snapshot")} aria-current={!isDemo ? "page" : undefined}>Fetched coverage</Link>
      </nav>
    </header>

    {isDemo ? <aside className="news-edition-notice" aria-label="Synthetic demonstration notice">
      <strong>DEMO SCENARIOS — FICTIONAL NEWS</strong>
      <p>Fictional events, publishers and stories. Iran and all map positions are illustrative; this edition reports no real incidents.</p>
      <p className="news-demo-clock">Fixed demo clock: <time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time></p>
    </aside> : <aside className="news-edition-notice news-edition-snapshot" aria-label="Snapshot source note">
      <strong>FETCHED COVERAGE — REAL SOURCE RECORDS</strong>
      <p>Publisher articles and official hazard reports, kept distinct. Imports are manual; page refresh reads stored coverage. Source attribution does not imply endorsement or confirmed impact.</p>
      <p className="news-demo-clock">Edition as of: <time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time>. Publication windows end at this clock.</p>
    </aside>}

    <details className="news-sources" open={Boolean(state.publisherId)}>
      <summary><span>{isDemo ? "Demo publishers" : "Sources and freshness"}{state.publisherId ? " · publisher filter active" : ""}</span>{!isDemo ? <span>{recentSources}/{sources.length} fetched within 24h{failedSources ? ` · ${failedSources} failed` : ""}{staleSources ? ` · ${staleSources} stale` : ""}{unfetchedSources ? ` · ${unfetchedSources} never fetched` : ""}</span> : null}</summary>
      <div className="news-source-selection">
        <label htmlFor="news-publisher"><span>Retained publisher or issuing agency</span><select id="news-publisher" value={state.publisherId ?? ""} onChange={(event) => updateState({ publisherId: event.target.value || null })}>
          <option value="">All retained publishers and agencies</option>
          {state.publisherId && !publisherOptions.some((option) => option.id === state.publisherId) ? <option value={state.publisherId}>Unavailable publisher selection</option> : null}
          {publisherOptions.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
        </select></label>
        <p>Counts reflect retained records from this selection. Syndicated copies excluded during import do not add publishers or articles.</p>
      </div>
      {!isDemo ? <details className="news-source-provenance">
        <summary>Fetch history and source attribution</summary>
        <p className="news-source-policy">Each feed keeps its own fetch history. The 24-hour threshold is a display policy, not a guarantee of current conditions. Article retrieval times can predate a successful unchanged-feed check.</p>
        <ul className="news-source-list">{sourceHealth.map(({ source, freshness }) => {
          const feedUrl = safeSourceUrl(source.feed_url);
          const termsUrl = safeSourceUrl(source.terms_url);
          const age = freshness.ageState === "stale" ? "Stale — over 24 hours" : freshness.ageState === "within_threshold" ? "Fetched within 24 hours" : freshness.ageState === "never_fetched" ? "Never fetched" : "Fetch age unknown";
          return <li key={source.source_id}>
            <div className="news-source-heading"><strong>{source.name}</strong><span>{source.kind === "official" ? "Official reports" : "Publisher articles"} · {source.item_count} retained records</span></div>
            <p className={source.state === "error" || freshness.ageState === "stale" ? "news-source-warning" : undefined}>{source.state === "error" ? "Latest fetch failed. " : ""}{age}{freshness.ageLabel ? ` (${freshness.ageLabel} at edition clock)` : ""}.</p>
            <dl><div><dt>Last successful fetch</dt><dd>{formatNewsTime(source.last_success_at)}</dd></div><div><dt>Last attempt</dt><dd>{formatNewsTime(source.last_attempt_at)}</dd></div>{source.next_fetch_at ? <div><dt>Next permitted import</dt><dd>{formatNewsTime(source.next_fetch_at)}; not an automatic schedule</dd></div> : null}</dl>
            {source.error ? <p className="news-source-warning">{source.error}</p> : null}
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
      <fieldset className="news-window"><legend>Published within</legend><div>{WINDOWS.map((option) => <button key={option.value} type="button" aria-pressed={state.window === option.value} onClick={() => updateState({ window: option.value })}>{option.label}</button>)}</div></fieldset>
    </div>
    <div className="news-scope-bar">
      <div className="news-scopes" role="group" aria-label="Geographic scope">{SCOPES.map((scope) => <button key={scope.value} type="button" aria-pressed={state.scope === scope.value} onClick={() => updateState({ scope: scope.value })}>{scope.label}<span>{scope.value === "all" ? queriedEvents.length : queriedEvents.filter((event) => event.scope === scope.value).length}</span></button>)}</div>
      {isFiltered ? <button className="news-clear" type="button" onClick={() => updateState({ window: "24h", scope: "all", query: "", selectedId: null, publisherId: null })}>Reset view</button> : null}
    </div>
    <p className="news-results" role="status"><strong>{counts.event_count}</strong> {counts.event_count === 1 ? "event" : "events"} · <strong>{counts.story_count}</strong> {counts.story_count === 1 ? "article" : "articles"} from <strong>{counts.news_publisher_count}</strong> news {counts.news_publisher_count === 1 ? "publisher" : "publishers"} · <strong>{counts.official_report_count}</strong> official {counts.official_report_count === 1 ? "report" : "reports"} from <strong>{counts.official_source_count}</strong> {counts.official_source_count === 1 ? "agency" : "agencies"}. Counts reflect this view.</p>

    <div className="news-workspace">
      <div className="news-overview">
        <NewsMap events={visibleEvents} selectedId={selected?.id ?? null} onSelect={selectEvent} />
        <section className="news-event-register" aria-labelledby="news-event-register-title">
          <header><h2 id="news-event-register-title">Events in this view</h2><span>Ordered by retained records, not severity</span></header>
          {visibleEvents.length ? <ol className="news-event-list">{visibleEvents.map((event) => <li key={event.id}>
            <button type="button" className={`news-event-card${event.id === selected?.id ? " is-selected" : ""}`} aria-pressed={event.id === selected?.id} onClick={() => selectEvent(event.id)}>
              <span className={`news-event-count severity-${event.severity}${!event.story_count && event.official_report_count ? " is-official-report" : ""}`}><strong>{event.story_count || event.official_report_count}</strong><span>{event.story_count ? event.story_count === 1 ? "article" : "articles" : event.official_report_count === 1 ? "report" : "reports"}</span></span>
              <span className="news-event-content"><span className="news-eyebrow">{event.is_demo ? "DEMO / " : ""}{!event.story_count && event.official_report_count ? "Official report / " : ""}{humanizeNewsLabel(event.category)} · {event.scope === "global" ? "Global coverage" : event.scope === "unlocated" ? "Unlocated" : event.location?.label}</span><strong>{event.title}</strong><span className="news-event-assessment">{humanizeNewsLabel(event.severity)} severity · {humanizeNewsLabel(event.status)}{event.story_count ? ` · ${event.news_publisher_count} news ${event.news_publisher_count === 1 ? "publisher" : "publishers"}` : ""}{event.official_report_count ? ` · ${event.official_report_count} official ${event.official_report_count === 1 ? "report" : "reports"} / ${event.official_source_count} ${event.official_source_count === 1 ? "agency" : "agencies"}` : ""}</span></span>
            </button>
          </li>)}</ol> : <p className="news-empty-list">No coverage records match these filters. Try a wider publication window or reset the view.</p>}
        </section>
      </div>
      <div ref={coverageFocus} tabIndex={-1} className="news-coverage-focus" aria-label="Selected news coverage"><a className="news-return-map" href="#news-map-top">Back to map and filters</a><CoveragePanel event={selected} asOf={data.as_of} edition={data.edition} /><a className="news-return-map" href="#news-map-top">Back to map and filters</a></div>
    </div>

    <section id="news-method" className="news-method" aria-labelledby="news-method-title">
      <h2 id="news-method-title">How to read this monitor</h2>
      <div><p><strong>Keep record types distinct.</strong> Circles count retained news articles; square markers count official reports. Neither count establishes severity or corroboration. Canonical aliases and declared syndication relationships are deduplicated; publisher breadth reflects only retained records.</p><p><strong>Group places, preserve incidents.</strong> A marker labeled “N separate events” opens a navigation group, not a merged incident. Publisher stories remain separate unless source evidence establishes event identity. Global and unlocated records receive no invented point; source-reported hazard coordinates link to their geographic evidence.</p><p><strong>Read the source clock.</strong> The window uses each RSS record’s publication time. Retrieval records collection; source coverage windows do not confirm occurrence times. Imports are manual and each source retains its own fetch status. Raw source-model alerts do not establish confirmed impact or our severity assessment.</p></div>
      <p className="news-method-note">{data.duplicates_excluded.toLocaleString()} duplicate {data.duplicates_excluded === 1 ? "record excluded" : "records excluded"} during this edition’s ingestion (before the selected time window). Publisher breadth is not independent corroboration.</p>
    </section>
  </div>;
}
