import type { ConnectorStatus } from "./types";

// A visible UI policy for stored fetches, not a feed SLA or a current-conditions claim.
export const STALE_AFTER_HOURS = 24;

export type ConnectorFreshnessAssessment = {
  attemptState: ConnectorStatus["state"];
  ageState: "within_threshold" | "stale" | "never_fetched" | "unknown";
  lastSuccessAt: string | null;
  lastAttemptAt: string | null;
  ageLabel: string | null;
};

function timestamp(value: string | null): string | null {
  // Reject timezone-free dates rather than silently using the server's local zone.
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/);
  if (!value || !match) return null;
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth[month - 1] || hour > 23 || minute > 59 || second > 59) return null;
  const parsed = new Date(value);
  return Number.isFinite(parsed.valueOf()) ? parsed.toISOString() : null;
}

function ageLabel(milliseconds: number): string {
  const minutes = Math.floor(milliseconds / 60_000);
  if (minutes === 0) return "Less than 1m ago";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m ago`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h ago`;
}

export function assessConnectorFreshness(connector: ConnectorStatus, nowMs: number): ConnectorFreshnessAssessment {
  const lastSuccessAt = timestamp(connector.last_success_at);
  const assessment: ConnectorFreshnessAssessment = {
    attemptState: connector.state,
    ageState: "unknown",
    lastSuccessAt,
    lastAttemptAt: timestamp(connector.last_attempt_at),
    ageLabel: null,
  };
  if (connector.last_success_at === null && connector.state !== "ok") {
    return { ...assessment, ageState: "never_fetched" };
  }
  if (lastSuccessAt === null || !Number.isFinite(nowMs)) return assessment;
  const elapsed = nowMs - Date.parse(lastSuccessAt);
  // Clock skew or a malformed future timestamp cannot make a record appear recent.
  if (elapsed < 0) return assessment;
  return {
    ...assessment,
    ageState: elapsed > STALE_AFTER_HOURS * 3_600_000 ? "stale" : "within_threshold",
    ageLabel: ageLabel(elapsed),
  };
}
