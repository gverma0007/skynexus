// Typed API client matching the SkyNexus backend endpoints.

export interface RegionOutline {
  id: string;
  name: string;
  /** Outer boundary ring as [lat, lon] pairs. */
  ring: [number, number][];
  severity_label: string;
  composite_index: number;
}

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
  category: string;
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

export interface SatelliteOrbit {
  inclination_deg: number;
  raan_deg: number;
  eccentricity: number;
  arg_perigee_deg: number;
  mean_anomaly_deg: number;
  mean_motion_revs_per_day: number;
  period_minutes: number;
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
  position: { time: string; lat: number; lon: number; alt_km: number } | null;
  observations: number;
  orbit: SatelliteOrbit | null;
  track: { time: string; lat: number; lon: number; alt_km: number }[];
}

export interface PressureZone {
  region_id: string;
  region_name: string;
  lat: number;
  lon: number;
  pressure_index: number;
  classification: 'CALM' | 'WATCH' | 'ELEVATED' | 'CRITICAL';
  description: string;
  drivers: string[];
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
  getRegionOutlines: () => request<RegionOutline[]>('/regions/outline'),
  getLiveFlights: () => request<FlightArc[]>('/flights/live'),
  getLiveSatellites: () => request<SatelliteTrack[]>('/satellites/live'),
  getSatelliteDetail: (noradId: number) =>
    request<SatelliteDetail>(`/satellites/${noradId}`),
  getAnomalies: (regionId?: string) =>
    request<Anomaly[]>(`/anomalies${regionId ? `?region_id=${regionId}` : ''}`),
  getEvents: (regionId?: string) =>
    request<EventItem[]>(`/events${regionId ? `?region_id=${regionId}` : ''}`),
  getDisruptionIndex: () => request<RegionDisruption[]>('/disruption-index'),
  getStats: () => request<StatsSummary>('/stats'),
  getPressureZones: () => request<PressureZone[]>('/pressure-zones'),
  getWhatChanged: (regionId: string, hours = 24) =>
    request<WhatChangedReport>(`/what-changed/${regionId}?hours=${hours}`),
  getForecast: (regionId: string) => request<ForecastResponse>(`/what-changed/${regionId}/forecast`),
};
