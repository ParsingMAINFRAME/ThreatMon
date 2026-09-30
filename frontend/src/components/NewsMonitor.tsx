"use client";

import Link from "next/link";
import { useCallback, useMemo, useRef, useSyncExternalStore } from "react";
import { CoveragePanel } from "./CoveragePanel";
import { NewsMap } from "./NewsMap";
import type { NewsResponse, NewsViewState, NewsWindow } from "@/lib/news-types";
import { assessConnectorFreshness } from "@/lib/freshness";
import { buildNewsEvents, formatNewsTime, humanizeNewsLabel, newsCoverage, newsHref, parseNewsState, selectNewsEvents } from "@/lib/news-view";
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

export function NewsMonitor({ data }: { data: NewsResponse }) {
  const search = useSyncExternalStore(subscribeLocation, locationSearch, serverSearch);
  const state = useMemo(() => parseNewsState(new URLSearchParams(search)), [search]);
  const events = useMemo(() => buildNewsEvents(data.events, data.as_of, state.window), [data.events, data.as_of, state.window]);
  const queriedEvents = useMemo(() => selectNewsEvents(events, { scope: "all", query: state.query }), [events, state.query]);
  const visibleEvents = useMemo(() => selectNewsEvents(queriedEvents, { scope: state.scope, query: "" })
    .sort((a, b) => b.story_count - a.story_count || a.id.localeCompare(b.id)), [queriedEvents, state.scope]);
  const selected = visibleEvents.find((event) => event.id === state.selectedId) ?? visibleEvents[0] ?? null;
  const counts = useMemo(() => newsCoverage(visibleEvents), [visibleEvents]);
  const coverageFocus = useRef<HTMLDivElement>(null);
  const isDemo = data.edition === "demo";
  const isFiltered = state.scope !== "all" || Boolean(state.query) || state.window !== "24h";
  const freshness = assessConnectorFreshness({
    name: "nasa_news", feed_url: "", description: "NASA news snapshot",
    state: data.fetch_state === "ok" ? "ok" : data.fetch_state === "error" ? "error" : "never_run",
    last_attempt_at: data.last_attempt_at, last_success_at: data.fetched_at,
    item_count: data.events.length, error: data.error,
  }, Date.parse(data.as_of));
  const freshnessLabel = freshness.ageState === "stale" ? "Stale — over 24 hours"
    : freshness.ageState === "within_threshold" ? "Within 24-hour display policy"
    : freshness.ageState === "never_fetched" ? "Never fetched" : "Retrieval age unknown";

  const updateState = useCallback((patch: Partial<NewsViewState>, replace = false) => {
    const next = { ...state, ...patch };
    const available = selectNewsEvents(buildNewsEvents(data.events, data.as_of, next.window), next);
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
        <Link href={newsHref({ ...state, selectedId: isDemo ? state.selectedId : null }, "demo")} aria-current={isDemo ? "page" : undefined}>Demo scenarios</Link>
        <Link href={newsHref({ ...state, selectedId: isDemo ? null : state.selectedId }, "snapshot")} aria-current={!isDemo ? "page" : undefined}>Fetched NASA news</Link>
      </nav>
    </header>

    {isDemo ? <aside className="news-edition-notice" aria-label="Synthetic demonstration notice">
      <strong>DEMO SCENARIOS — FICTIONAL NEWS</strong>
      <p>Fictional events, publishers and stories. Iran and all map positions are illustrative; this edition reports no real incidents.</p>
      <p className="news-demo-clock">Fixed demo clock: <time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time></p>
    </aside> : <aside className="news-edition-notice news-edition-snapshot" aria-label="Snapshot source note">
      <strong>FETCHED NASA NEWS — STORED SNAPSHOT</strong>
      <p>Stored NASA space and science headlines. This is not continuous or worldwide incident coverage. Severity and incident locations remain unknown. Source: NASA; no endorsement implied.</p>
    </aside>}

    {!isDemo ? <section className="news-clock" aria-label="Edition clock and retrieval status">
      <div><span>EDITION AS OF</span><time dateTime={data.as_of}>{formatNewsTime(data.as_of)}</time></div>
      <div><span>LAST SUCCESSFUL FETCH</span><time dateTime={data.fetched_at ?? undefined}>{formatNewsTime(data.fetched_at)}</time></div>
      <div className={`news-freshness news-freshness-${freshness.ageState}`}><span>SNAPSHOT AGE</span><strong>{freshnessLabel}</strong>{freshness.ageLabel ? <small>{freshness.ageLabel}, measured at edition as-of</small> : null}</div>
      <p>Publication windows end at this edition’s clock. Refresh reads the stored snapshot.</p>
    </section> : null}
    {!isDemo && data.fetch_state === "never_fetched" ? <p className="news-fetch-notice" role="status">No NASA news snapshot has been fetched yet. This edition has no stories to display.</p> : null}
    {!isDemo && data.fetch_state === "error" ? <p className="news-fetch-notice" role="status">The latest fetch failed{data.last_attempt_at ? ` (${formatNewsTime(data.last_attempt_at)})` : ""}. {data.events.length ? "The last stored stories remain available; their retrieval times have not been refreshed." : "No stored stories are available."}{data.error ? ` ${data.error}` : ""}</p> : null}

    <div className="news-controls" id="news-map-top">
      <label className="news-search"><span>Find an event or publisher</span><input type="search" value={state.query} onChange={(event) => updateState({ query: event.target.value }, true)} placeholder="Search topics, places or publishers" /></label>
      <fieldset className="news-window"><legend>Published within</legend><div>{WINDOWS.map((option) => <button key={option.value} type="button" aria-pressed={state.window === option.value} onClick={() => updateState({ window: option.value })}>{option.label}</button>)}</div></fieldset>
    </div>
    <div className="news-scope-bar">
      <div className="news-scopes" role="group" aria-label="Geographic scope">{SCOPES.map((scope) => <button key={scope.value} type="button" aria-pressed={state.scope === scope.value} onClick={() => updateState({ scope: scope.value })}>{scope.label}<span>{scope.value === "all" ? queriedEvents.length : queriedEvents.filter((event) => event.scope === scope.value).length}</span></button>)}</div>
      {isFiltered ? <button className="news-clear" type="button" onClick={() => updateState({ window: "24h", scope: "all", query: "", selectedId: null })}>Reset view</button> : null}
    </div>
    <p className="news-results" role="status"><strong>{counts.event_count}</strong> {counts.event_count === 1 ? "event" : "events"} · <strong>{counts.story_count}</strong> unique {counts.story_count === 1 ? "story" : "stories"} · <strong>{counts.publisher_count}</strong> {counts.publisher_count === 1 ? "publisher" : "publishers"} in this view. Numbers on event circles are story counts.</p>

    <div className="news-workspace">
      <div className="news-overview">
        <NewsMap events={visibleEvents} selectedId={selected?.id ?? null} onSelect={selectEvent} />
        <section className="news-event-register" aria-labelledby="news-event-register-title">
          <header><h2 id="news-event-register-title">Events in this view</h2><span>Ordered by coverage, not severity</span></header>
          {visibleEvents.length ? <ol className="news-event-list">{visibleEvents.map((event) => <li key={event.id}>
            <button type="button" className={`news-event-card${event.id === selected?.id ? " is-selected" : ""}`} aria-pressed={event.id === selected?.id} onClick={() => selectEvent(event.id)}>
              <span className={`news-event-count severity-${event.severity}`}><strong>{event.story_count}</strong><span>{event.story_count === 1 ? "story" : "stories"}</span></span>
              <span className="news-event-content"><span className="news-eyebrow">{event.is_demo ? "DEMO / " : ""}{humanizeNewsLabel(event.category)} · {event.scope === "global" ? "Global coverage" : event.scope === "unlocated" ? "Unlocated" : event.location?.label}</span><strong>{event.title}</strong><span className="news-event-assessment">{humanizeNewsLabel(event.severity)} severity · {humanizeNewsLabel(event.status)} · {event.publisher_count} {event.publisher_count === 1 ? "publisher" : "publishers"}</span></span>
            </button>
          </li>)}</ol> : <p className="news-empty-list">No stories match this publication window and scope. Try a wider window or clear the search.</p>}
        </section>
      </div>
      <div ref={coverageFocus} tabIndex={-1} className="news-coverage-focus" aria-label="Selected news coverage"><a className="news-return-map" href="#news-map-top">Back to map and filters</a><CoveragePanel event={selected} asOf={data.as_of} edition={data.edition} /><a className="news-return-map" href="#news-map-top">Back to map and filters</a></div>
    </div>

    <section id="news-method" className="news-method" aria-labelledby="news-method-title">
      <h2 id="news-method-title">How to read this monitor</h2>
      <div><p><strong>Count stories, not alarm.</strong> Event circles show unique retained stories published within the chosen window. Canonical URL aliases and declared syndication relationships are deduplicated. Severity is a separate stated assessment; publication volume never raises it.</p><p><strong>Group places, preserve incidents.</strong> A marker labeled “N events” is a navigation group of nearby events. Open it to choose an incident; its stories and evidence remain separate. Global and unlocated events stay in their own scope lists.</p><p><strong>Read the source clock.</strong> Publication is when a story appeared; retrieval is when it was collected. Demo clocks are fixed and synthetic. Fetched NASA coverage is a stored source snapshot, with unknown incident severity and location unless supported by source evidence.</p></div>
      <p className="news-method-note">{data.duplicates_excluded.toLocaleString()} duplicate {data.duplicates_excluded === 1 ? "record excluded" : "records excluded"} during this edition’s ingestion (before the selected time window). Publisher breadth is not independent corroboration.</p>
    </section>
  </div>;
}
