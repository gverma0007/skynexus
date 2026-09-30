// Typed API client matching the SkyNexus backend endpoints.

export interface RegionMapPoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  composite_index: number;
  severity_label: 'normal' | 'low' | 'medium' | 'high';
  flight_anomaly_score: number;
  event_relevance_score: number;
  weather_score: number;
}

export interface FlightArc {
  id: string;
  callsign: string;
  icao24?: string;
  /** Aircraft's actual current position (live ADS-B). */
  position?: { lat: number; lon: number };
  origin: { name: string; lat: number; lon: number };
  destination: { name: string; lat: number; lon: number };
  progress: number;
  altitude_ft: number;
  speed_kt: number;
  heading_deg?: number;
  timestamp: string;
  source?: string;
  region_name: string | null;
}

export interface SatelliteTrack {
  id: string;
  norad_id: number;
  name: string;
  lat: number;
  lon: number;
  altitude_km: number;
  timestamp: string;
}

export interface Anomaly {
  id: string;
  region_id: string;
  entity_type: string;
  feature_name: string;
  timestamp: string;
  observed_value: number;
  z_score: number | null;
  composite_score: number | null;
  severity_label: string | null;
}

export interface EventItem {
  id: string;
  external_id: string | null;
  event_date: string;
  event_type: string;
  category: string;
  severity: string;
  description: string | null;
  region_name: string;
  lat: number;
  lon: number;
}

export interface RegionDisruption {
  region_id: string;
  region_name: string;
  flight_anomaly_score: number;
  event_relevance_score: number;
  weather_score: number;
  composite_index: number;
  severity_label: string;
}

export interface StatsSummary {
  flights_24h: number;
  satellites_tracked: number;
  active_events: number;
  regions_monitored: number;
  global_disruption_index: number;
  most_disrupted_region: string | null;
  most_disrupted_index: number;
  severity_bands?: { low: number; medium: number; high: number };
}

export interface WhatChangedReport {
  region: { id: string; name: string };
  window_hours: number;
  aviation_metrics: MetricDelta;
  satellite_metrics: MetricDelta;
  weather_metrics: MetricDelta;
  events_metrics: MetricDelta;
  overall_assessment: string;
}

export interface MetricDelta {
  before: number;
  after: number;
  delta_pct: number;
  summary: string;
}

export interface ForecastResponse {
  region_id: string;
  region_name: string;
  horizon_hours: number;
  history: { time: string; value: number }[];
  points: { time: string; value: number }[];
}

const BASE = import.meta.env.VITE_API_URL ?? '';
const API = `${BASE}/api`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  getRegionsMap: () => request<RegionMapPoint[]>('/regions/map'),
  getLiveFlights: () => request<FlightArc[]>('/flights/live'),
  getLiveSatellites: () => request<SatelliteTrack[]>('/satellites/live'),
  getAnomalies: (regionId?: string) =>
    request<Anomaly[]>(`/anomalies${regionId ? `?region_id=${regionId}` : ''}`),
  getEvents: (regionId?: string) =>
    request<EventItem[]>(`/events${regionId ? `?region_id=${regionId}` : ''}`),
  getDisruptionIndex: () => request<RegionDisruption[]>('/disruption-index'),
  getStats: () => request<StatsSummary>('/stats'),
  getWhatChanged: (regionId: string, hours = 24) =>
    request<WhatChangedReport>(`/what-changed/${regionId}?hours=${hours}`),
  getForecast: (regionId: string) => request<ForecastResponse>(`/what-changed/${regionId}/forecast`),
};
