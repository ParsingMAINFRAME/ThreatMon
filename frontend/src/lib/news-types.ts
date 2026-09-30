export type NewsSeverity = "unknown" | "low" | "moderate" | "high";
export type NewsScope = "located" | "global" | "unlocated";
export type NewsWindow = "1h" | "24h" | "7d" | "all";

export type NewsSourceStatus = {
  source_id: string;
  publisher_id: string;
  name: string;
  kind: "news" | "official";
  feed_url: string;
  terms_url: string;
  attribution: string;
  coverage_note: string;
  last_attempt_at: string | null;
  last_success_at: string | null;
  state: "never_fetched" | "ok" | "error";
  error: string | null;
  item_count: number;
  next_fetch_at: string | null;
};

export type NewsLocation = {
  lat: number;
  lon: number;
  label: string;
  precision: "source_point" | "approximate_area" | "illustrative";
  confidence: "high" | "medium" | "low" | "unknown";
  basis: string;
  source_url?: string | null;
};

export type NewsArticle = {
  id: string;
  canonical_url: string | null;
  headline: string;
  publisher: string;
  published_at: string;
  retrieved_at: string;
  summary: string;
  is_demo: boolean;
  syndication_key: string | null;
  duplicate_urls: string[];
  source_id?: string;
  publisher_id?: string;
  record_kind?: "article" | "official_report";
  author?: string | null;
  license_url?: string | null;
  source_window_start?: string | null;
  source_window_end?: string | null;
};

export type NewsEvent = {
  id: string;
  title: string;
  summary: string;
  category: string;
  status: "unconfirmed" | "developing" | "reported" | "resolved";
  severity: NewsSeverity;
  severity_basis: string;
  grouping_basis: string;
  location: NewsLocation | null;
  scope: NewsScope;
  is_demo: boolean;
  articles: NewsArticle[];
  source_event_id?: string | null;
  source_alert_level?: string | null;
};

export type NewsResponse = {
  edition: "demo" | "snapshot";
  as_of: string;
  fetched_at: string | null;
  last_attempt_at: string | null;
  fetch_state: "demo" | "never_fetched" | "ok" | "partial" | "error";
  error: string | null;
  events: NewsEvent[];
  duplicates_excluded: number;
  source_note: string;
  sources?: NewsSourceStatus[];
};

export type NewsEventView = NewsEvent & {
  story_count: number;
  official_report_count: number;
  publisher_count: number;
  news_publisher_count: number;
  official_source_count: number;
  freshest_published_at: string | null;
  last_retrieved_at: string | null;
};

export type NewsViewState = {
  window: NewsWindow;
  scope: "all" | NewsScope;
  query: string;
  selectedId: string | null;
  publisherId: string | null;
};

export type NewsMapGroup = {
  id: string;
  kind: "event" | "cluster";
  events: NewsEventView[];
  lat: number;
  lon: number;
  story_count: number;
  official_report_count: number;
};
