import type { ThreatCardData, ThreatCategory } from "./types";

export const categoryLabels: Record<ThreatCategory, string> = {
  cybersecurity: "Cybersecurity",
  natural_hazard: "Natural hazards",
  public_health: "Public health",
  space_planetary: "Space & planetary",
  geopolitical_infrastructure: "Infrastructure",
  ai_risk: "AI risk",
};

export function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function displayTitle(title: string) {
  return title.replace(/^\[DEMO\]\s*/i, "");
}

export function formatDate(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "2-digit", year: "numeric", timeZone: "UTC",
  }).format(date);
}

export function formatDateTime(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Date unavailable";
  return `${new Intl.DateTimeFormat("en-US", {
    month: "short", day: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  }).format(date)} UTC`;
}

export function displayText(value: string) {
  return value.replace(/\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b/g, (timestamp) => formatDateTime(timestamp));
}

export type DataMode = "demo" | "live" | "mixed" | "empty" | "unavailable";

export function dataMode(threats: ThreatCardData[] | null): DataMode {
  if (threats === null) return "unavailable";
  if (threats.length === 0) return "empty";
  if (threats.every((threat) => threat.is_demo)) return "demo";
  if (threats.every((threat) => !threat.is_demo)) return "live";
  return "mixed";
}

export function safeSourceUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}
