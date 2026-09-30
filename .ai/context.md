# CONTEXT.md — SkyNexus Global System Context

## 1. System Mission & Pipeline
SkyNexus ingests aviation (ADS-B synthetic), satellite orbits (CelesTrak TLE), weather (Open-Meteo), and global events (GDELT 2.0), detects deviations against 30-day trailing baselines, correlates regional deviations against detected events, and produces a Regional Disruption Index (0–100) alongside explainable "What Changed?" reports[cite: 1].

Pipeline flow:
L1: Raw Sources -> L2: Ingestion & Features -> L3: Baseline & Anomaly -> L4: Correlation & Disruption Index -> L5: UI Dashboard & Explanations[cite: 1]

---

## 2. Repository Layout Target
skynexus/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (regions, flights, satellites, etc.)
│   │   ├── core/         # config.py, db.py
│   │   ├── data/         # connectors (TLE, weather, GDELT), pipeline.py, demo_dataset.py
│   │   ├── ml/           # baseline, zscore, isolation_forest, composite, correlation, weather_filter, disruption_index
│   │   ├── models/       # SQLAlchemy PostGIS ORM entities
│   │   ├── schemas/      # Pydantic v2 validation models
│   │   ├── services/     # what_changed, ai_explainer, forecast, playback
│   │   └── scripts/      # bootstrap_demo.py
│   ├── notebooks/        # validation.ipynb
│   ├── tests/
│   └── alembic/
├── frontend/
│   └── src/
│       ├── api/          # Typed Axios client & interfaces
│       ├── components/   # UI panels, modal, gauges
│       ├── hooks/        # SWR/Polling hooks
│       ├── theme/        # Color & typography tokens
│       └── three/        # Globe, FlightArcs, SatelliteTracks, AnomalyZones
├── docker-compose.yml
└── README.md

---

## 3. Database Schema Blueprint
Every observational/event table carries source: Text and ingested_at: TIMESTAMPTZ (default=now()) with GiST indexes on geometries[cite: 1, 2]:

- Reference Tables:
  * regions: id, name, geom GEOMETRY(POLYGON,4326), centroid GEOMETRY(POINT,4326)[cite: 2]
  * airports: id, iata_code, name, geom GEOMETRY(POINT,4326), region_id FK[cite: 2]
  * flight_routes: id, origin_airport_id FK, dest_airport_id FK, region_id FK[cite: 2]
  * satellites: id, norad_id, name[cite: 2]

- Observation Tables:
  * flight_observations: id, route_id FK, callsign, icao24, timestamp, position GEOMETRY(POINT,4326), altitude_ft, speed_kt, heading_deg, source, ingested_at[cite: 2]
  * satellite_observations: id, satellite_id FK, timestamp, position GEOMETRY(POINTZ,4326), altitude_km, source, ingested_at[cite: 2]
  * weather_observations: id, region_id FK, timestamp, position GEOMETRY(POINT,4326), wind_speed_kt, precipitation_mm, storm_index, source, ingested_at[cite: 2]
  * events: id, external_id, event_date, event_type, category, severity, position GEOMETRY(POINT,4326), region_id FK, description, source, ingested_at[cite: 2]

- Engine Tables:
  * baselines: id, entity_type, entity_id, feature_name, window_start, window_end, mean_value, std_value, sample_count, computed_at[cite: 2]
  * anomaly_scores: id, entity_type, entity_id, region_id FK, timestamp, feature_name, observed_value, z_score, isolation_forest_score, composite_score, severity_label, computed_at[cite: 2]
  * event_correlations: id, anomaly_id FK, event_id FK, temporal_proximity_score, geographic_overlap_score, confidence_score, computed_at[cite: 2]

- Output Tables:
  * disruption_index: id, region_id FK, window_start, window_end, flight_anomaly_score, event_relevance_score, airspace_score, airport_activity_score, satellite_score, weather_score, composite_index, severity_label, confidence_pct, computed_at[cite: 2]
  * what_changed_reports: id, region_id FK, event_id FK, before_start, before_end, after_start, after_end, metrics_json JSONB, ai_explanation, confidence_pct, generated_at[cite: 2]
  * forecasts: id, region_id FK, generated_at, horizon_hours, metric_name, predicted_values JSONB[cite: 2]

---

## 4. Key Formulas & Mathematical Weights

### A. Anomaly Detection (L3)
- Z-score formula: (observed - mean) / max(std, 1e-5)[cite: 1]
- Isolation Forest: Fitted on multi-variate features; inverted decision function rescaled to 0–100[cite: 1, 2].
- composite_score = (Z_WEIGHT * z_scaled) + (IFOREST_WEIGHT * iforest_scaled) (Default weights: 0.5 / 0.5)[cite: 1, 2]

### B. Correlation Confidence (L4)
- temporal_proximity_score: Linear/exponential decay to 0 at |delta_t| >= 72 hours[cite: 1, 2].
- geographic_overlap_score: PostGIS ST_Distance decaying to 0 at max_distance_km[cite: 1, 2].

### C. Regional Disruption Index (0–100)
Composite Index is the weighted sum of components[cite: 1, 2]:
- Flight anomaly: weight = 0.25[cite: 1, 2]
- Event relevance: weight = 0.20[cite: 1, 2]
- Airspace deviation: weight = 0.20[cite: 1, 2]
- Airport volume change: weight = 0.15[cite: 1, 2]
- Satellite anomaly: weight = 0.10[cite: 1, 2]
- Weather explanation: weight = 0.10 (inverse-weighted)[cite: 1, 2]
- Severity Tiers: Normal (< 40), Low (40–54), Medium (55–69), High (>= 70)[cite: 1, 2]