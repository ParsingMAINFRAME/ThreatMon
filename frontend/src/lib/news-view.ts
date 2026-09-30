import type { NewsArticle, NewsEvent, NewsEventView, NewsMapGroup, NewsViewState, NewsWindow } from "./news-types";

const WINDOW_HOURS: Record<NewsWindow, number> = { "1h": 1, "24h": 24, "7d": 168, all: Infinity };

function timestamp(value: string | null): number | null {
  if (!value || !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function canonicalKey(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    url.hash = "";
    return url.href;
  } catch { return null; }
}

/** Source IDs, canonical URLs and declared syndication aliases identify one story. */
export function deduplicateNewsArticles(articles: NewsArticle[]): NewsArticle[] {
  const parents = articles.map((_, index) => index);
  const aliases = new Map<string, number>();
  const root = (index: number): number => {
    while (parents[index] !== index) {
      parents[index] = parents[parents[index]];
      index = parents[index];
    }
    return index;
  };
  articles.forEach((article, index) => {
    const keys = article.id ? [`id:${article.id}`] : [];
    const url = canonicalKey(article.canonical_url);
    if (url) keys.push(`url:${url}`);
    for (const alias of article.duplicate_urls ?? []) {
      const duplicate = canonicalKey(alias);
      if (duplicate) keys.push(`url:${duplicate}`);
    }
    if (article.syndication_key?.trim()) keys.push(`syndication:${article.syndication_key.trim()}`);
    keys.forEach((key) => {
      const previous = aliases.get(key);
      if (previous !== undefined) {
        const left = root(previous);
        const right = root(index);
        parents[Math.max(left, right)] = Math.min(left, right);
      } else aliases.set(key, index);
    });
  });
  // Keep the first source-provided representative, matching the backend's retained-story contract.
  return articles.filter((_, index) => root(index) === index);
}

function publisherCount(articles: NewsArticle[]): number {
  return new Set(articles.map((article) => article.publisher.trim().toLowerCase()).filter(Boolean)).size;
}

function latest(articles: NewsArticle[], key: "published_at" | "retrieved_at"): string | null {
  return articles.reduce<string | null>((value, article) => {
    const next = timestamp(article[key]);
    return next !== null && (value === null || next > (timestamp(value) ?? -Infinity)) ? article[key] : value;
  }, null);
}

/** Publication windows are anchored to the supplied edition clock, never the browser clock. */
export function buildNewsEvents(events: NewsEvent[], asOf: string, window: NewsWindow): NewsEventView[] {
  const end = timestamp(asOf);
  if (end === null) return [];
  const start = end - WINDOW_HOURS[window] * 3_600_000;
  return events.flatMap((event) => {
    const articles = deduplicateNewsArticles(event.articles.filter((article) => {
      const published = timestamp(article.published_at);
      return published !== null && published >= start && published <= end;
    })).sort((a, b) => (timestamp(b.published_at) ?? 0) - (timestamp(a.published_at) ?? 0) || a.id.localeCompare(b.id));
    if (!articles.length) return [];
    return [{ ...event, articles, story_count: articles.length, publisher_count: publisherCount(articles), freshest_published_at: latest(articles, "published_at"), last_retrieved_at: latest(articles, "retrieved_at") }];
  });
}

export function selectNewsEvents(events: NewsEventView[], state: Pick<NewsViewState, "scope" | "query">): NewsEventView[] {
  const query = state.query.trim().toLowerCase();
  return events.filter((event) => (state.scope === "all" || event.scope === state.scope)
    && (!query || `${event.title} ${event.summary} ${event.category} ${event.location?.label ?? ""} ${event.articles.map((article) => `${article.headline} ${article.publisher}`).join(" ")}`.toLowerCase().includes(query)));
}

export function newsCoverage(events: NewsEventView[]): { event_count: number; story_count: number; publisher_count: number } {
  const articles = deduplicateNewsArticles(events.flatMap((event) => event.articles));
  return { event_count: events.length, story_count: articles.length, publisher_count: publisherCount(articles) };
}

export function hasNewsLocation(event: NewsEvent): boolean {
  const location = event.location;
  return event.scope === "located" && Boolean(location && Number.isFinite(location.lat) && Number.isFinite(location.lon)
    && location.lat >= -90 && location.lat <= 90 && location.lon >= -180 && location.lon <= 180);
}

/** Screen-space proximity groups events for navigation; it never merges incident evidence. */
export function clusterNewsEvents(events: NewsEventView[], zoom: number): NewsMapGroup[] {
  const located = events.filter(hasNewsLocation);
  const parents = located.map((_, index) => index);
  const root = (index: number): number => {
    while (parents[index] !== index) { parents[index] = parents[parents[index]]; index = parents[index]; }
    return index;
  };
  if (zoom < 3) {
    const distance = 42 / Math.max(1, zoom);
    for (let a = 0; a < located.length; a++) {
      const first = located[a].location!;
      for (let b = a + 1; b < located.length; b++) {
        const second = located[b].location!;
        const longitude = Math.abs(first.lon - second.lon);
        const x = Math.min(longitude, 360 - longitude) / 360 * 1000;
        const y = (first.lat - second.lat) / 180 * 500;
        if (Math.hypot(x, y) <= distance) parents[root(b)] = root(a);
      }
    }
  }
  const members = new Map<number, NewsEventView[]>();
  located.forEach((event, index) => { const group = root(index); members.set(group, [...(members.get(group) ?? []), event]); });
  return Array.from(members.values()).map((group) => {
    const ordered = [...group].sort((a, b) => a.id.localeCompare(b.id));
    const angles = ordered.map((event) => event.location!.lon * Math.PI / 180);
    const lon = Math.atan2(angles.reduce((sum, angle) => sum + Math.sin(angle), 0), angles.reduce((sum, angle) => sum + Math.cos(angle), 0)) * 180 / Math.PI;
    return {
      id: ordered.length === 1 ? ordered[0].id : `cluster:${ordered.map((event) => event.id).join("|")}`,
      kind: ordered.length === 1 ? "event" : "cluster",
      events: ordered,
      lat: ordered.reduce((sum, event) => sum + event.location!.lat, 0) / ordered.length,
      lon,
      story_count: newsCoverage(ordered).story_count,
    };
  });
}

export function parseNewsState(params: Pick<URLSearchParams, "get">): NewsViewState {
  const window = params.get("window") ?? "24h";
  const scope = params.get("scope") ?? "all";
  return {
    window: ["1h", "24h", "7d", "all"].includes(window) ? window as NewsWindow : "24h",
    scope: ["all", "located", "global", "unlocated"].includes(scope) ? scope as NewsViewState["scope"] : "all",
    query: (params.get("q") ?? "").slice(0, 200),
    selectedId: params.get("selected")?.slice(0, 256) || null,
  };
}

export function newsHref(state: NewsViewState, edition: "demo" | "snapshot"): string {
  const params = new URLSearchParams({ edition });
  if (state.window !== "24h") params.set("window", state.window);
  if (state.scope !== "all") params.set("scope", state.scope);
  if (state.query) params.set("q", state.query);
  if (state.selectedId) params.set("selected", state.selectedId);
  return `/?${params.toString()}`;
}

export function humanizeNewsLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function formatNewsTime(value: string | null): string {
  const time = timestamp(value);
  if (time === null) return "Not recorded";
  return `${new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(time)} UTC`;
}
