export type BBox = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type Hotspot = {
  id: string;
  lat: number;
  lon: number;
  brightness_k: number;
  confidence: number;
  satellite?: string | null;
  frp_mw?: number | null;
  observed_at?: string | null;
  source?: string | null;
  live: boolean;
  mode: string;
};

export type Brief = {
  id: string;
  run_id: string;
  artifact_type: string;
  generated_at: string;
  watch: { id: string; name: string; bbox: BBox; timezone?: string };
  skus_used: string[];
  cogs_usd: number;
  evidence_status: string;
  summary: string;
  drivers: string[];
  live_fire_detection_count: number;
  returned_detection_count: number;
  hotspots: Hotspot[];
  brightest?: Hotspot | null;
  weather?: {
    id?: string;
    place?: string;
    lat?: number;
    lon?: number;
    distance_km?: number;
    max_weather_km?: number;
    temperature_c?: number;
    humidity_pct?: number;
    pressure_hpa?: number;
    source?: string;
    live?: boolean;
  } | null;
  limitations: string[];
  badges: string[];
  receipt?: {
    digest?: string;
    signature_status?: string;
    capability_id?: string;
    ts?: string;
    algorithm?: string;
    public_key_b64?: string;
    emberline_verified?: boolean;
    verify_error?: string | null;
  } | null;
  attribution?: string;
  legal_strip: string;
  delta?: RunDelta | null;
};

export type DeltaPoint = {
  id?: string | null;
  lat?: number;
  lon?: number;
  brightness_k?: number;
  from_k?: number;
  to_k?: number;
  delta_k?: number;
};

export type RunDelta = {
  artifact_type: string;
  kind: "first_run" | "versus_prior" | string;
  versus_brief_id?: string | null;
  versus_generated_at?: string | null;
  summary: string;
  live_count?: { from: number; to: number; delta: number } | null;
  appeared?: DeltaPoint[];
  disappeared?: DeltaPoint[];
  brightened?: DeltaPoint[];
  dimmed?: DeltaPoint[];
  unchanged_count?: number;
  counts?: {
    appeared: number;
    disappeared: number;
    brightened: number;
    dimmed: number;
    unchanged: number;
  };
  match?: {
    primary: string;
    fallback: string;
    material_brightness_k: number;
  };
  material_brightness_k?: number;
  limitations?: string[];
};

export type Watch = {
  id: string;
  name: string;
  west: number;
  south: number;
  east: number;
  north: number;
  layers: string[];
  timezone: string;
  schedule: string;
  quiet_hours: string;
  status: string;
  policy: string;
  alert_live_hotspots: number;
  alert_brightness_k: number;
  slack_webhook?: string;
  https_webhook?: string;
  has_webhook_secret?: boolean;
  last_run_at: string | null;
  created_at: string;
};

export type ArchiveRow = {
  id: string;
  watch_id: string;
  watch_name: string;
  started_at: string;
  status: string;
  evidence_status: string;
  alerted: boolean;
  cogs_usd: number;
  skus_used: string[];
  brief_id: string | null;
};

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  role: string;
  workspace: { id: string; name: string; plan: string };
};

export function isBrief(value: unknown): value is Brief {
  if (!value || typeof value !== "object") return false;
  const brief = value as Brief;
  return (
    Array.isArray(brief.hotspots) &&
    Array.isArray(brief.badges) &&
    Array.isArray(brief.limitations) &&
    typeof brief.summary === "string" &&
    typeof brief.watch?.name === "string"
  );
}
