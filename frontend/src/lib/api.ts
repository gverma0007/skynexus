// Typed client for the SkyNexus API.

export type Severity = 'normal' | 'low' | 'medium' | 'high';
export type Status = 'Calm' | 'Watch' | 'Elevated' | 'Critical';

export interface RouteDeviationsInfo {
  count?: number;
  deviating_count?: number;
  minor_count?: number;
  significant_count?: number;
  max_km?: number;
  avg_km?: number;
  dev_score?: number;
}

export interface FlightComponent {
  score: number;
  warming_up: boolean;
  recent: number | null;
  expected: number | null;
  pct_change: number | null;
  z: number | null;
  direction: 'up' | 'down' | 'flat';
  baseline_days: number;
  week_mean?: number | null;
  week_pct_change?: number | null;
  week_z?: number | null;
  route_deviations?: RouteDeviationsInfo;
}

export interface SatelliteComponent {
  score: number;
  count: number;
  density: number;
  density_change_pct?: number | null;
  by_orbit: { leo: number; meo: number; geo: number };
  by_category: Record<string, number>;
  leo_earthobs: number;
  gnss_nav: number;
}

export interface EventBrief {
  id: string;
  magnitude: number;
  description: string | null;
  event_date: string;
  hours_ago: number;
  label: string;
}

export interface Region {
  region_id: string;
  region_name: string;
  lat: number;
  lon: number;
  composite_index: number;
  previous_index: number | null;
  change_24h: number | null;
  severity_label: Severity;
  status: Status;
  flight_anomaly_score: number;
  event_relevance_score: number;
  weather_score: number;
  satellite_score?: number;
  components: {
    flights: FlightComponent;
    events: { score: number; count_24h: number; max_magnitude: number | null; largest: EventBrief | null };
    weather: { score: number; storm_now: number | null; storm_week_avg: number | null };
    satellites?: SatelliteComponent;
  };
  explanation: string[];
  sparkline: (number | null)[];
}

export interface Outline {
  id: string;
  name: string;
  ring: [number, number][];
}

export interface HistoryPoint {
  time: string;
  aircraft: number | null;
  partial: boolean;
  storm: number | null;
  events: number;
  normal_range: [number, number] | null;
}

export interface History {
  region_id: string;
  region_name: string;
  points: HistoryPoint[];
  baseline_hours: number;
}

export interface Forecast {
  region_id: string;
  region_name: string;
  history: { time: string; value: number }[];
  points: { time: string; value: number; low: number; high: number }[];
  trend_per_hour?: number;
  method: string;
}

export interface Satellite {
  norad_id: number;
  name: string;
  category: string;
  category_label: string;
  lat: number;
  lon: number;
  altitude_km: number;
  speed_km_s: number;
  region_id: string | null;
  region_name: string | null;
  timestamp: string;
}

export interface Overhead {
  region_id: string;
  count: number;
  by_category: Record<string, number>;
  satellites: Satellite[];
}

export interface Orbit {
  inclination_deg: number;
  raan_deg: number;
  eccentricity: number;
  arg_perigee_deg: number;
  mean_anomaly_deg: number;
  mean_motion_revs_per_day: number;
  period_minutes: number;
  semi_major_axis_km: number;
  perigee_alt_km: number;
  apogee_alt_km: number;
  epoch: string | null;
  tle_line1: string;
  tle_line2: string;
}

export interface SatelliteDetail {
  norad_id: number;
  name: string;
  category: string;
  category_label: string;
  position: { time: string; lat: number; lon: number; alt_km: number; speed_km_s: number };
  region_name: string | null;
  orbit: Orbit;
  track: { time: string; lat: number; lon: number; alt_km: number; offset_min: number }[];
}

export interface FlightDeviation {
  cross_track_km: number;
  cross_track_nm: number;
  side: 'right' | 'left';
  heading_deviation_deg: number;
  progress_pct: number;
  total_route_km: number;
  status: 'on_route' | 'minor_deviation' | 'significant_deviation';
}

export interface FlightRouteSummary {
  origin_iata: string;
  origin_name: string;
  dest_iata: string;
  dest_name: string;
}

export interface Flight {
  icao24: string;
  callsign: string;
  lat: number;
  lon: number;
  altitude_ft: number;
  speed_kt: number;
  heading_deg: number;
  timestamp: string;
  source: string;
  region_id: string | null;
  region_name: string | null;
  route?: FlightRouteSummary | null;
  deviation?: FlightDeviation | null;
}

export interface FlightDetail extends Omit<Flight, 'route'> {
  summary?: string;
  route?: {
    origin: { iata: string; name: string; lat: number; lon: number };
    dest: { iata: string; name: string; lat: number; lon: number };
    waypoints: { lat: number; lon: number }[];
    total_route_km: number;
  } | null;
  trail: { lat: number; lon: number; altitude_ft: number; speed_kt: number; timestamp: string }[];
}

export interface EventItem {
  id: string;
  external_id: string | null;
  event_date: string;
  event_type: string;
  category: string;
  severity: string;
  description: string | null;
  region_id: string;
  region_name: string;
  lat: number;
  lon: number;
  source: string;
  magnitude: number;
}

export interface Anomaly {
  id: string;
  region_id: string;
  region_name: string;
  timestamp: string;
  feature_name: string;
  observed_value: number;
  z_score: number | null;
  isolation_forest_score: number | null;
  composite_score: number | null;
  severity_label: Severity;
  summary: string;
}

export interface Alert {
  id: string;
  level: 'critical' | 'warning' | 'info';
  title: string;
  detail: string;
  region_id: string | null;
  time: string;
  kind: 'region' | 'event' | 'anomaly' | 'system';
}

export interface Stats {
  aircraft_now: number;
  satellites_tracked: number;
  events_24h: number;
  regions_monitored: number;
  status_counts: Record<Status, number>;
  needs_attention: number;
  global_disruption_index: number;
  most_disrupted_region: string | null;
  most_disrupted_index: number;
  last_update: string | null;
  data_mode: 'live' | 'demo';
  ingest_interval_s: number | null;
  severity_bands: { low: number; medium: number; high: number };
}

export interface MetricDelta {
  label: string;
  unit: string;
  before: number | null;
  after: number | null;
  delta_pct: number | null;
}

export interface Report {
  id?: string;
  generated_at?: string;
  region: { id: string; name: string };
  window_hours: number;
  windows: { before_start: string; before_end: string; after_start: string; after_end: string };
  disruption_index: { before: number | null; after: number; delta: number | null };
  aviation_metrics: MetricDelta;
  flight_deviations?: {
    label: string;
    active_routes: number;
    deviating_flights: number;
    significant_deviations: number;
    max_deviation_km: number;
    avg_deviation_km: number;
    deviation_score: number;
  };
  events_metrics: MetricDelta & {
    largest: string | null;
    list: { description: string | null; magnitude: number; event_date: string }[];
  };
  weather_metrics: MetricDelta;
  satellite_metrics: MetricDelta;
  historical_data?: {
    baseline_hours: number;
    points: HistoryPoint[];
  };
  confidence_pct: number;
  overall_assessment: string;
  ai_source: 'claude' | 'template';
}

export interface ReportSummary {
  id: string;
  region_id: string;
  region_name: string | null;
  window_hours: number;
  generated_at: string;
  ai_source: string;
  index: number | null;
}

export interface SourceHealth {
  domain: string;
  source: string;
  name: string;
  description: string;
  url: string | null;
  rows_24h: number;
  rows_total: number;
  last_seen: string | null;
  status: 'ok' | 'stale' | 'demo';
}

export interface IngestState {
  running: boolean;
  last_started: string | null;
  last_finished: string | null;
  last_summary: Record<string, number> | null;
  last_error: string | null;
  duration_s: number | null;
  cycles: number;
}

export interface SystemHealth {
  data_mode: 'live' | 'demo';
  live_ingest: boolean;
  ingest_interval_s: number;
  retention_days: number;
  ai_mode: 'claude' | 'template';
  ai_model: string | null;
  ingest: IngestState;
  sources: SourceHealth[];
  counts: Record<string, number>;
  server_time: string;
}

export interface SearchResult {
  regions: { id: string; name: string }[];
  satellites: { norad_id: number; name: string; category: string; category_label: string }[];
}

const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'Cannot reach the SkyNexus API. Check that the backend container is running.');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, `${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const q = (params: Record<string, string | number | undefined | null>) => {
  const s = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&');
  return s ? `?${s}` : '';
};

export const api = {
  stats: () => request<Stats>('/stats'),
  regions: () => request<Region[]>('/regions'),
  outlines: () => request<Outline[]>('/regions/outline'),
  history: (id: string, hours = 48) => request<History>(`/regions/${id}/history${q({ hours })}`),
  overhead: (id: string) => request<Overhead>(`/regions/${id}/overhead`),
  forecast: (id: string) => request<Forecast>(`/regions/${id}/forecast`),
  flights: (limit = 3000) => request<Flight[]>(`/flights/live${q({ limit })}`),
  flightDetail: (icao24: string) => request<FlightDetail>(`/flights/${icao24}/route`),
  flightDeviations: (minKm = 300) => request<Flight[]>(`/flights/deviations?min_km=${minKm}`),
  satellites: () => request<Satellite[]>('/satellites/live'),
  satellite: (norad: number) => request<SatelliteDetail>(`/satellites/${norad}`),
  events: (p: { region_id?: string; days?: number; min_magnitude?: number } = {}) =>
    request<EventItem[]>(`/events${q(p)}`),
  anomalies: (p: { region_id?: string; hours?: number } = {}) => request<Anomaly[]>(`/anomalies${q(p)}`),
  alerts: () => request<Alert[]>('/alerts'),
  search: (text: string) => request<SearchResult>(`/search${q({ q: text })}`),
  system: () => request<SystemHealth>('/system/health'),
  getMode: () => request<{ data_mode: string }>('/system/mode'),
  setMode: (mode: 'live' | 'demo') =>
    request<{ data_mode: string; status: string }>('/system/mode', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ mode }),
    }),
  runIngest: () => request<{ status: string; state: IngestState }>('/ingest/live', { method: 'POST' }),
  reports: () => request<ReportSummary[]>('/reports'),
  report: (id: string) => request<Report>(`/reports/${id}`),
  createReport: (region_id: string, hours: number) =>
    request<Report>('/reports', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ region_id, hours }),
    }),
  deleteReport: (id: string) => request<void>(`/reports/${id}`, { method: 'DELETE' }),
};
