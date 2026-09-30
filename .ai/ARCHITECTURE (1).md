# SkyNexus — System Architecture

**Global Activity Anomaly & Impact Intelligence System**

SkyNexus fuses aviation (ADS-B), satellite (TLE), weather (Open-Meteo) and global-event (GDELT) data, detects anomalies against 30-day baselines, correlates them with real-world events, scores a Regional Disruption Index (0–100), and explains the result in plain language **without ever asserting causation**.

---

## 1. Design Principles

| Principle | How the architecture enforces it |
|---|---|
| **Correlation, not causation** | The AI explainer receives only computed statistics (never raw rows), is prompted never to assert a cause, and every output ends with a causation disclaimer. The UI footer disclaimer is always visible. |
| **Baseline before anomaly** | An anomaly is only meaningful relative to a normal pattern, so the baseline builder (L3) is a hard prerequisite for scoring, correlation and the index. |
| **Rule out the obvious first** | A weather-explanation filter runs before escalation, removing the most common false alarm (storm-driven diversions). |
| **Provenance on every record** | Every observation/event table carries `source` and `ingested_at`. |
| **Explainable over clever** | Z-score + Isolation Forest, weighted-average index, and a simple statistical forecast — each defensible in a viva. Tunable weights are named constants, not magic numbers. |
| **Demo-first, live-ready** | A synthetic dataset drives the end-to-end demo; real connectors plug into the same ingestion interface. |

---

## 2. System Context

```mermaid
flowchart LR
    subgraph External["External Data Sources (no API key)"]
        CT[CelesTrak<br/>TLE sets]
        OM[Open-Meteo<br/>archive API]
        GD[GDELT 2.0<br/>Event CSV export]
    end
    LLM[Anthropic API<br/>optional]
    DEMO[Demo dataset<br/>generator]

    subgraph SkyNexus
        BE[FastAPI Backend<br/>+ ML engine]
        DB[(PostgreSQL<br/>+ PostGIS)]
        FE[React + three.js<br/>Dashboard]
    end

    User([Analyst / Examiner])

    CT --> BE
    OM --> BE
    GD --> BE
    DEMO --> BE
    BE <--> DB
    BE -.explain statistics only.-> LLM
    FE <-->|REST /api| BE
    User --> FE
```

---

## 3. Five-Layer Pipeline

```mermaid
flowchart TB
    L1["<b>L1 — Data Sources</b><br/>ADS-B (demo) · TLE · Open-Meteo · GDELT"]
    L2["<b>L2 — Ingestion & Processing</b><br/>connectors → cleaning → feature engineering"]
    L3["<b>L3 — Baseline + Anomaly Engine</b><br/>30-day baselines → Z-score + Isolation Forest → composite score"]
    L4["<b>L4 — Correlation + Impact Engine</b><br/>event correlation → weather filter → Regional Disruption Index"]
    L5["<b>L5 — Output</b><br/>3D globe · What Changed? · AI explanation · 6-hour forecast"]
    L1 --> L2 --> L3 --> L4 --> L5
```

| Layer | Responsibility | Key modules |
|---|---|---|
| **L1** | Raw inputs | CelesTrak, Open-Meteo, GDELT, `demo_dataset.py` |
| **L2** | Normalize into the schema | `tle_connector.py`, `weather_connector.py`, `gdelt_connector.py`, `pipeline.py` |
| **L3** | Decide what is "unusual" | `baseline.py`, `zscore.py`, `isolation_forest.py`, `composite.py` |
| **L4** | Decide what it might relate to, and how severe | `correlation.py`, `weather_filter.py`, `disruption_index.py` |
| **L5** | Present and explain | FastAPI routers, `what_changed.py`, `ai_explainer.py`, `forecast.py`, React UI |

---

## 4. Technology Stack

| Concern | Choice |
|---|---|
| Frontend | React + TypeScript (Vite), three.js, recharts, axios, zustand |
| Backend | Python 3.11, FastAPI, SQLAlchemy, GeoAlchemy2, Alembic, pydantic-settings |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| ML | scikit-learn (Isolation Forest), pandas, numpy, statsmodels (forecast), sgp4 (orbit propagation) |
| AI explanation | Anthropic API (optional; deterministic template fallback) |
| Packaging | Docker Compose (db, backend, frontend) |

---

## 5. Component Architecture

### 5.1 Repository Layout

```
skynexus/
├── backend/
│   ├── app/
│   │   ├── api/        # FastAPI routers (one per resource)
│   │   ├── core/       # config.py, db.py
│   │   ├── data/       # connectors, demo generator, pipeline, seed
│   │   ├── ml/         # baseline, zscore, isolation_forest, composite,
│   │   │               #   correlation, weather_filter, disruption_index
│   │   ├── services/   # what_changed, ai_explainer, forecast, playback
│   │   ├── models/     # SQLAlchemy models
│   │   └── schemas/    # Pydantic response models
│   ├── notebooks/      # validation.ipynb
│   ├── tests/
│   └── alembic/        # migrations
├── frontend/src/
│   ├── components/     # sidebar panels, modal
│   ├── hooks/          # data-fetching hooks
│   ├── api/            # typed axios client
│   ├── three/          # Globe + layers
│   └── theme/          # design tokens
├── docker-compose.yml
└── README.md
```

### 5.2 Backend Modules

```mermaid
flowchart TB
    subgraph API["app/api — routers"]
        R1[regions] --- R2[flights] --- R3[satellites]
        R4[anomalies] --- R5[events] --- R6[disruption_index]
        R7[stats] --- R8[what_changed] --- R9[forecast]
    end
    subgraph SVC["app/services"]
        S1[what_changed]
        S2[ai_explainer]
        S3[forecast]
        S4[playback *stretch*]
    end
    subgraph ML["app/ml"]
        M1[baseline] --> M2[zscore]
        M1 --> M3[isolation_forest]
        M2 --> M4[composite]
        M3 --> M4
        M4 --> M5[correlation]
        M1 --> M6[weather_filter]
        M5 --> M7[disruption_index]
        M6 --> M7
    end
    subgraph DATA["app/data"]
        D1[tle_connector]
        D2[weather_connector]
        D3[gdelt_connector]
        D4[demo_dataset]
        D5[pipeline]
    end
    DB[(PostGIS)]

    R8 --> S1 --> M7
    S1 --> S2
    R9 --> S3
    R6 --> M7
    D1 & D2 & D3 & D4 --> D5 --> DB
    ML <--> DB
    API <--> DB
```

**Layering rule:** routers → services → ml → models/DB. Routers never contain analytics logic; ML modules never import from `api/`.

### 5.3 Frontend Structure

```mermaid
flowchart TB
    App[App.tsx — grid shell]
    App --> Top[TopStatBar]
    App --> Center[Globe.tsx]
    App --> Side[Right Sidebar]

    Center --> FA[FlightArcs]
    Center --> ST[SatelliteTracks]
    Center --> AZ[AnomalyZones]

    Side --> G[DisruptionGauge]
    Side --> RL[RegionalAnomalyList]
    Side --> AF[AnomalyAlertFeed]
    Side --> ET[EventTimeline]
    Side --> AI[AIAssessmentPanel]
    Side --> FP[ForecastPanel]

    Top --> WC[WhatChangedModal]

    Store[(Zustand store<br/>selectedRegionId · selectedEventId)]
    Hooks[hooks/ — useRegions, useDisruptionIndex,<br/>useAnomalies, useEvents, useForecast,<br/>useStatsSummary, useFlightsLive, useSatellitesLive]
    Client[api/client.ts — typed axios]

    Store --- Top & Side & Center & WC
    Hooks --> Client
    FA & ST & AZ & G & RL & AF & ET & AI & FP & Top --> Hooks
```

The **Globe** owns only the sphere, lighting and camera; data layers attach through an imperative layer API so each layer is independently replaceable. All panels degrade independently — one failing endpoint never blanks the dashboard.

---

## 6. Data Architecture

### 6.1 Entity Relationship Overview

```mermaid
erDiagram
    regions ||--o{ airports : contains
    regions ||--o{ flight_routes : has
    regions ||--o{ weather_observations : has
    regions ||--o{ events : has
    airports ||--o{ flight_routes : "origin/dest"
    flight_routes ||--o{ flight_observations : has
    satellites ||--o{ satellite_observations : has

    regions ||--o{ anomaly_scores : has
    anomaly_scores ||--o{ event_correlations : "correlated via"
    events ||--o{ event_correlations : "correlated via"
    regions ||--o{ disruption_index : scored
    regions ||--o{ what_changed_reports : reported
    events ||--o{ what_changed_reports : "anchor"
    regions ||--o{ forecasts : projected
```

### 6.2 Table Groups

| Group | Tables | Notes |
|---|---|---|
| **Reference** | `regions`, `airports`, `flight_routes`, `satellites` | Seeded / slowly changing |
| **Observations** | `flight_observations`, `satellite_observations`, `weather_observations`, `events` | Append-only; carry `source` + `ingested_at`; PostGIS geometry with GiST indexes |
| **Engine** | `baselines`, `anomaly_scores`, `event_correlations` | Derived; recomputable from observations |
| **Output** | `disruption_index`, `what_changed_reports`, `forecasts` | Derived + `metrics_json` (JSONB) for report payloads |

Key indexes: GiST on every geometry column; btree on `flight_observations.timestamp`, `events(region_id, event_date)`, `anomaly_scores(region_id, timestamp)`.

### 6.3 Data Flow

```mermaid
sequenceDiagram
    participant Src as Sources / Demo generator
    participant Pipe as pipeline.py
    participant DB as PostGIS
    participant ML as ML engine
    participant API as FastAPI
    participant UI as Dashboard

    Src->>Pipe: raw rows (mode: demo | live)
    Pipe->>Pipe: clean (null/impossible/dupes)
    Pipe->>Pipe: feature engineering
    Pipe->>DB: observations
    ML->>DB: build baselines (30-day mean/std)
    ML->>DB: z-score + Isolation Forest → composite score
    ML->>DB: event correlations + weather filter
    ML->>DB: disruption_index
    UI->>API: poll /flights/live, /disruption-index, ...
    API->>DB: read
    API-->>UI: JSON
```

---

## 7. Analytics Engine

### 7.1 Anomaly Scoring (L3)

```mermaid
flowchart LR
    Obs[Observations] --> BL[Baseline<br/>30-day mean/std<br/>epsilon-floored]
    BL --> Z["Z-score<br/>(obs − mean) / std"]
    Obs --> IF["Isolation Forest<br/>multivariate, per entity type"]
    Z --> C[Composite<br/>weighted 0–100]
    IF --> C
    C --> SEV["Severity<br/>normal / low / medium / high"]
```

- **Z-score** catches single-feature deviations; **Isolation Forest** catches *combined* deviations a single z-score would miss.
- Composite weights (`Z_WEIGHT`, `IFOREST_WEIGHT`) are named constants.
- The Isolation Forest's inverted `decision_function` is rescaled so higher = more anomalous.

### 7.2 Correlation + Weather Filter (L4)

`confidence_score = f(temporal_proximity, geographic_overlap, anomaly composite)` with explicit named weights.

- **Temporal proximity:** decays to 0 at the ±72 h window edge.
- **Geographic overlap:** PostGIS `ST_Distance`, decaying to 0 at a max distance.
- **Weather explanation:** compares `storm_index` against the region's own weather baseline. **LOW** means weather does *not* explain the deviation, so escalation continues.

### 7.3 Regional Disruption Index

| Component | Default weight | Source |
|---|---|---|
| Flight anomaly | 0.25 | mean composite of route anomalies |
| Event relevance | 0.20 | mean correlation confidence |
| Airspace | 0.20 | share of flights above deviation threshold |
| Airport activity | 0.15 | \|% volume change vs baseline\| |
| Satellite | 0.10 | mean composite of satellite anomalies over region |
| Weather | 0.10 | weather-explanation score (inverse-weighted) |

Output: `composite_index` (0–100), `severity_label` (normal < 40 … high ≥ 70), and `confidence_pct` (from sample sizes / data completeness). All weights and thresholds are named constants so they can be retuned against the validation case.

### 7.4 Forecast

A deliberately simple, explainable method (e.g. Holt's linear smoothing) projects three metrics — flight congestion, route deviation, airport pressure — 6 hours ahead from the trailing ~72 h, with a naive residual-std confidence band. Gradient-boosted time-series models are documented future work.

---

## 8. "What Changed?" Flow (Hero Feature)

```mermaid
sequenceDiagram
    participant UI as WhatChangedModal
    participant API as POST /api/what-changed
    participant SVC as services/what_changed
    participant ML as disruption_index / correlation / weather_filter
    participant AI as services/ai_explainer
    participant DB as PostGIS

    UI->>API: {region_id, event_id?, window_days}
    API->>SVC: gather_what_changed_metrics()
    SVC->>DB: before/after aviation + satellite metrics
    SVC->>ML: weather score, correlations, index
    SVC-->>API: metrics_json (aggregates only)
    API->>AI: explain(metrics_json)
    AI-->>API: 2–4 sentence narrative + causation line
    Note over AI: Fallback template if API/key unavailable
    API->>DB: persist what_changed_reports
    API-->>UI: report (4 cards + overall assessment)
```

The **guardrail boundary** sits between `SVC` and `AI`: only aggregated `metrics_json` crosses it.

---

## 9. API Surface

| Method | Endpoint | Purpose | Consumer |
|---|---|---|---|
| GET | `/api/health` | Liveness | Ops |
| GET | `/api/regions`, `/api/regions/{id}` | Regions + latest index | Zones, list |
| GET | `/api/flights/live` | Latest flight positions + `is_anomalous` | FlightArcs |
| GET | `/api/satellites/live` | Latest satellite positions | SatelliteTracks |
| GET | `/api/anomalies` | Filterable anomaly list | Alert feed |
| GET | `/api/events` | Filterable events | Timeline |
| GET | `/api/disruption-index` | Latest index per region | Gauge, list, zones |
| GET | `/api/stats/summary` | Four headline counters | Top bar |
| POST | `/api/what-changed` | Generate before/after report | Modal |
| GET | `/api/forecast/{region_id}` | 6-hour projection | Forecast panel |
| GET | `/api/clock` | Simulated clock *(stretch)* | LIVE indicator |

OpenAPI docs are served at `/docs`. Responses use Pydantic models; PostGIS geometry is exposed as plain `lat`/`lon` floats.

---

## 10. Deployment

```mermaid
flowchart LR
    subgraph Docker Compose
        DB[(db<br/>postgis:16-3.4<br/>:5432 · volume)]
        BE[backend<br/>FastAPI :8000<br/>Alembic on startup]
        FE[frontend<br/>Vite :5173]
    end
    FE -->|VITE_API_URL| BE
    BE -->|DATABASE_URL| DB
    Browser([Browser]) --> FE
```

- `docker compose up` brings up all three services; migrations run automatically at backend start.
- One-command demo: `python -m app.scripts.bootstrap_demo` runs migrate → seed regions → generate demo data → ingest → baselines → anomaly scoring → correlation/weather filter → disruption index.
- Config via environment: `DATABASE_URL`, `ANTHROPIC_API_KEY` (optional), `ENV`, `VITE_API_URL`, `SIMULATE_LIVE` (optional).

---

## 11. Validation & Testing

| Level | What is checked |
|---|---|
| Unit | Baseline mean/std and zero-std guard; z-score values; Isolation Forest ranks planted outliers higher; composite severity buckets; correlation decay; weather filter LOW vs HIGH; forecast trend direction |
| Integration | Pipeline end-to-end row counts; each endpoint against a seeded test DB; `/api/what-changed` matches the index validation |
| **Scenario validation** | On the demo T0 event, the post-event 7-day window scores HIGH while the pre-event window stays in the normal band |
| Notebook | `validation.ipynb` reproduces the before/after volume, correlation-confidence and index-breakdown charts live from pipeline output, plus an anomaly-score timeline with T0 marked |

---

## 12. Limitations & Constraints

- **No causal claims.** Outputs are statistical anomalies and correlations only.
- **Flights are demo data.** A real historical ADS-B pull is out of scope; live mode covers satellite, weather and events only.
- **Latency.** Public feeds are batch/near-real-time, not streaming; "LIVE" is a simulated clock in demo mode.
- **Narrow GDELT scope.** Restricted to a bounded date range and region bounding box rather than a global pull.
- **Simple forecasting.** Chosen for explainability, not accuracy.
- **Tunable, not proven, weights.** Index weights are documented defaults calibrated against one validation scenario.

---

## 13. Extension Points

| Area | Extension |
|---|---|
| Data | Real ADS-B feed behind the same ingestion interface |
| Streaming | Replace polling with WebSocket/SSE; Kafka-style ingestion |
| ML | Gradient-boosted forecasting; learned (rather than fixed) index weights |
| Ops | Scheduler (e.g. APScheduler/Celery) for rolling index recompute |
| Frontend | Additional globe layers via the existing layer API |
