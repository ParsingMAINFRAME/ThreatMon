import type { SortOption } from "@/components/Filters";

export const PAGE_SIZE = 25;
const CATEGORIES = ["natural_hazard", "cybersecurity", "public_health", "space_planetary", "geopolitical_infrastructure", "ai_risk"];
const STATUSES = ["routine", "watchlist", "developing", "confirmed", "resolved", "contradicted", "false"];
const SORTS = ["priority", "severity", "updated", "title"];

export type RegisterState = {
  selectedCategory: string;
  selectedStatus: string;
  minSeverity: number;
  query: string;
  geography: string;
  mode: string;
  sort: SortOption;
  page: number;
  selectedId: string | null;
};

export function parseRegisterState(params: Pick<URLSearchParams, "get">): RegisterState {
  const category = params.get("category") ?? "all";
  const status = params.get("status") ?? "all";
  const severity = Number(params.get("severity") ?? 0);
  const origin = params.get("origin");
  const sort = params.get("sort") ?? "priority";
  const page = params.get("page") ?? "1";
  return {
    selectedCategory: CATEGORIES.includes(category) ? category : "all",
    selectedStatus: STATUSES.includes(status) ? status : "all",
    minSeverity: Number.isFinite(severity) ? Math.min(100, Math.max(0, severity)) : 0,
    query: (params.get("q") ?? "").slice(0, 200),
    geography: (params.get("geography") ?? "").slice(0, 120),
    mode: origin === "live" || origin === "demo" ? origin : "all",
    sort: SORTS.includes(sort) ? sort as SortOption : "priority",
    page: /^[1-9]\d*$/.test(page) && Number.isSafeInteger(Number(page)) ? Number(page) : 1,
    selectedId: params.get("selected")?.slice(0, 256) || null,
  };
}

function stateQuery(state: RegisterState): string {
  const params = new URLSearchParams();
  if (state.selectedCategory !== "all") params.set("category", state.selectedCategory);
  if (state.selectedStatus !== "all") params.set("status", state.selectedStatus);
  if (state.minSeverity > 0) params.set("severity", String(state.minSeverity));
  if (state.query) params.set("q", state.query);
  if (state.geography) params.set("geography", state.geography);
  if (state.mode !== "all") params.set("origin", state.mode);
  if (state.sort !== "priority") params.set("sort", state.sort);
  if (state.page > 1) params.set("page", String(state.page));
  if (state.selectedId) params.set("selected", state.selectedId);
  const query = params.toString();
  return query ? "?" + query : "";
}

export function registerHref(state: RegisterState, returnToRegister = false): string {
  return "/signals" + stateQuery(state) + (returnToRegister ? "#event-register" : "");
}

export function evidenceHref(id: string, state: RegisterState): string {
  return "/threats/" + encodeURIComponent(id) + stateQuery({ ...state, selectedId: id });
}

export function recordOrdinals(records: { id: string }[]): Map<string, number> {
  return new Map(records.map((record, index) => [record.id, index + 1]));
}

export function registerPage(page: number, recordCount: number): number {
  return Math.min(page, Math.max(1, Math.ceil(recordCount / PAGE_SIZE)));
}

export function selectRegisterRecord(state: RegisterState, id: string, records: { id: string }[]): RegisterState {
  const index = records.findIndex((record) => record.id === id);
  return index < 0 ? state : { ...state, selectedId: id, page: Math.floor(index / PAGE_SIZE) + 1 };
}
