import type { ConnectorStatusResponse, ThreatDetailResponse, ThreatListResponse } from "./types";
import type { NewsResponse } from "./news-types";

const API_BASE_URL = (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`The data service returned HTTP ${status}.`);
    this.name = "ApiError";
  }
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(10_000),
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  return response.json() as Promise<T>;
}

export async function getThreats(): Promise<ThreatListResponse> {
  const firstPage = await requestJson<ThreatListResponse>("/threats?limit=100&offset=0");
  const items = [...firstPage.items];
  const ids = new Set(items.map((item) => item.id));
  const changed = () => new Error("Records changed during loading. Refresh to reload the register.");
  if (ids.size !== items.length || (firstPage.total !== undefined && items.length > firstPage.total)) throw changed();
  while (firstPage.total !== undefined && items.length < firstPage.total) {
    const page = await requestJson<ThreatListResponse>(`/threats?limit=100&offset=${items.length}`);
    if (page.items.length === 0 || page.total !== firstPage.total || page.data_mode !== firstPage.data_mode || page.snapshot_id !== firstPage.snapshot_id) throw changed();
    for (const item of page.items) {
      if (ids.has(item.id)) throw changed();
      ids.add(item.id);
    }
    items.push(...page.items);
    if (items.length > firstPage.total) throw changed();
  }
  return { ...firstPage, items };
}

export function getThreat(id: string): Promise<ThreatDetailResponse> {
  return requestJson<ThreatDetailResponse>(`/threats/${encodeURIComponent(id)}`);
}

export function getNews(edition: "demo" | "snapshot" = "snapshot", channel: "news" | "signals" | "all" = "news"): Promise<NewsResponse> {
  return requestJson<NewsResponse>(`/news?edition=${encodeURIComponent(edition)}&channel=${encodeURIComponent(channel)}`);
}

function isConnectorStatusResponse(value: unknown): value is ConnectorStatusResponse {
  if (!value || typeof value !== "object") return false;
  const data = value as Record<string, unknown>;
  const nullableText = (field: unknown) => field === null || typeof field === "string";
  return typeof data.live_ingestion_enabled === "boolean"
    && typeof data.automatic_refresh_enabled === "boolean"
    && typeof data.note === "string"
    && Array.isArray(data.connectors)
    && data.connectors.every((entry: unknown) => {
      if (!entry || typeof entry !== "object") return false;
      const item = entry as Record<string, unknown>;
      return typeof item.name === "string" && item.name.trim().length > 0
        && typeof item.feed_url === "string" && typeof item.description === "string"
        && (item.state === "never_run" || item.state === "ok" || item.state === "error")
        && nullableText(item.last_attempt_at) && nullableText(item.last_success_at) && nullableText(item.error)
        && typeof item.item_count === "number" && Number.isInteger(item.item_count) && item.item_count >= 0;
    });
}

/** Feed status is optional context: its failure must not prevent reading retained records. */
export async function getConnectorStatus(): Promise<ConnectorStatusResponse | null> {
  try {
    const data = await requestJson<unknown>("/ingest/connectors");
    return isConnectorStatusResponse(data) ? data : null;
  } catch {
    return null;
  }
}
