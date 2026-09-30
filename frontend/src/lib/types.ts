export type ThreatStatus =
  | "routine"
  | "watchlist"
  | "developing"
  | "confirmed"
  | "resolved"
  | "contradicted"
  | "false";

export type ThreatCategory =
  | "cybersecurity"
  | "natural_hazard"
  | "public_health"
  | "space_planetary"
  | "geopolitical_infrastructure"
  | "ai_risk";

export type ConfidenceLabel = "high" | "medium" | "low";

export type ThreatScore = {
  severity: number;
  credibility: number;
  velocity: number;
  exposure: number;
  uncertainty_penalty: number;
  priority: number;
  confidence: ConfidenceLabel;
  rationale: string[];
};

export type SourceItem = {
  id: string;
  title: string;
  source_name: string;
  source_type: string;
  reliability_tier: string;
  citation: string;
  url: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  is_official: boolean;
  is_demo: boolean;
  notes: string | null;
};

export type ExtractedClaim = {
  id: string;
  source_id: string;
  text: string;
  support_level: string;
  confidence: number;
  is_material: boolean;
  contradicts_claim_ids: string[];
};

export type ThreatTimelineEntry = {
  id: string;
  occurred_at: string;
  title: string;
  description: string;
  source_ids: string[];
  material_change: boolean;
};

export type MapLocation = {
  lon: number;
  lat: number;
  label: string;
  precision: "reported_point" | "illustrative";
  origin: "source_reported" | "synthetic_demo";
  source_id: string;
};

export type ThreatCardData = {
  id: string;
  title: string;
  category: ThreatCategory;
  geography: string[];
  status: ThreatStatus;
  summary: string;
  score: ThreatScore;
  updated_at: string;
  is_demo: boolean;
  map_location?: MapLocation | null;
  source_count?: number;
};

export type ThreatEvent = ThreatCardData & {
  sources: SourceItem[];
  extracted_claims: ExtractedClaim[];
  timeline: ThreatTimelineEntry[];
  key_uncertainties: string[];
  contradictory_evidence: string[];
  next_watch_items: string[];
  implications: string[];
};

export type ThreatListResponse = {
  demo_data: boolean;
  items: ThreatCardData[];
  data_mode?: "empty" | "demo" | "live" | "mixed";
  total?: number;
  limit?: number;
  offset?: number;
  snapshot_id?: string | null;
};

export type ThreatDetailResponse = {
  demo_data: boolean;
  item: ThreatEvent;
  data_mode?: "demo" | "live";
};

export type ConnectorStatus = {
  name: string;
  feed_url: string;
  description: string;
  state: "never_run" | "ok" | "error";
  last_attempt_at: string | null;
  last_success_at: string | null;
  item_count: number;
  error: string | null;
};

export type ConnectorStatusResponse = {
  live_ingestion_enabled: boolean;
  automatic_refresh_enabled: boolean;
  connectors: ConnectorStatus[];
  note: string;
};
