# SkyNexus — Build Prompt Playbook (Max-Split Edition)

This is a **further-split version** of the playbook: every prompt is now scoped to roughly one function, one component, or one narrow concern. This is intentionally granular — small enough that a free/lightweight model can complete each one without holding much context. The tradeoff is more prompts and more sequencing discipline: run them strictly in order, and each prompt tells you what already exists so you (or the agent) can check before starting.

Pipeline: **L1 Data Sources → L2 Ingestion/Processing → L3 Baseline+Anomaly Engine → L4 Correlation+Impact Engine → L5 Output**.

## How to use this

- **Run in strict order.** Prompts now frequently edit the same file as the one immediately before them.
- **Best tool: a persistent coding agent in one repo** so file state carries over. If pasting into a fresh chat each time, paste the **Project Context** block first, and tell the model which file the previous prompt touched.
- Tags: `[SETUP]` `[DATABASE]` `[DATA]` `[ML]` `[BACKEND]` `[FRONTEND]` `[INTEGRATION]` `[DOCS]`
- **Team split:** once Phase 0 is done, Phases 1–2, Phase 3, Phase 4, and Phase 5 are independent workstreams. Within any phase, hand one prompt at a time to a lighter model — don't batch several together.

### Scope decisions (unchanged from the original design)

- **Demo data by default** — a real historical ADS-B pull is out of scope; a synthetic dataset (Prompts 15–19) comes first, real connectors (20–28) alongside it.
- **Simple, explainable forecasting** — gradient-boosted forecasting is future work; the forecast prompts use a basic statistical method.
- **Causation discipline enforced in code** — the AI explainer only ever receives computed statistics, never raw rows, and always ends with a correlation-does-not-establish-causation line.

### No-key data sources

| Source | Access | Key needed? |
|---|---|---|
| CelesTrak (TLE) | Plain HTTPS GET | No |
| Open-Meteo (weather) | `archive-api.open-meteo.com/v1/archive` | No |
| GDELT 2.0 Events | Raw CSV export or free-tier BigQuery | No |
| Anthropic API (AI explanations) | `ANTHROPIC_API_KEY` | Optional — falls back to a template if unset |

## Project context block (paste this first in a fresh chat)

```
Project: SkyNexus — Global Activity Anomaly & Impact Intelligence System.
A mini-project that fuses aviation (ADS-B), satellite (TLE), weather
(Open-Meteo) and global-event (GDELT) data to detect anomalies against
30-day baselines, correlate them with real-world events, score a Regional
Disruption Index (0-100), and explain it in plain language without
asserting causation.

Stack: React + TypeScript + three.js frontend | Python + FastAPI backend |
PostgreSQL + PostGIS database | scikit-learn (Z-score, Isolation Forest).

Pipeline: L1 Data Sources -> L2 Ingestion/Processing -> L3 Baseline+Anomaly
Engine -> L4 Correlation+Impact Engine -> L5 Output (3D dashboard,
"What Changed?" report, AI explanation, 6-hour forecast).

Hard rule: the system reports statistical anomalies and correlations. It
never claims an observed change proves a specific geopolitical, military,
or security event. Every AI-generated explanation carries a "correlation
does not establish causation" line, and the LLM only ever receives
computed statistics/JSON, never raw rows.

Note: this build is a long sequence of very small, single-concern
prompts. Before starting, check what files already exist in the repo and
treat this prompt as adding to that codebase, editing only what it says
to edit.
```

## Suggested repo layout

```
skynexus/
├── backend/
│   ├── app/
│   │   ├── api/ core/ data/ ml/ services/ models/ schemas/
│   ├── notebooks/  tests/  alembic/
├── frontend/
│   └── src/ components/ hooks/ api/ three/ theme/
├── docker-compose.yml
└── README.md
```

---

## Phase 0 — Foundations

### Prompt 1 — [SETUP] Backend project init + dependencies

```
Initialize a Python 3.11 project in backend/ for a project called
SkyNexus (Poetry or requirements.txt — pick one and be consistent).
Add dependencies only: fastapi, uvicorn, sqlalchemy, geoalchemy2,
psycopg2-binary, alembic, pydantic-settings, scikit-learn, pandas,
numpy, httpx, python-dotenv, pytest. Confirm the environment installs
cleanly. Don't write any application code yet — that's the next prompt.
```

### Prompt 2 — [SETUP] Backend config.py

```
backend/'s dependencies are already installed (prior prompt). Create
backend/app/core/config.py: a pydantic-settings Settings class reading
DATABASE_URL, ANTHROPIC_API_KEY, and ENV from environment variables,
with a cached get_settings() accessor. No FastAPI app yet.
```

### Prompt 3 — [SETUP] Backend main.py + health endpoint

```
backend/app/core/config.py already exists (prior prompt). Create
backend/app/main.py: a FastAPI() instance using get_settings(), and a
GET /api/health endpoint returning {"status": "ok"}. Confirm the
backend starts and /api/health responds.
```

### Prompt 4 — [SETUP] Frontend Vite scaffold

```
Scaffold frontend/ with Vite's react-ts template for the SkyNexus
monorepo (backend/ already exists — leave it untouched). Confirm the
dev server serves the default Vite page with zero console errors. Don't
add extra dependencies yet — that's the next prompt.
```

### Prompt 5 — [SETUP] Frontend dependencies

```
frontend/ is already scaffolded with Vite react-ts (prior prompt). Add
these dependencies: axios, three, @types/three, recharts, zustand (or
your preferred lightweight state manager). Confirm the app still builds
and runs with zero console errors after installing them.
```

### Prompt 6 — [SETUP] docker-compose.yml

```
backend/ and frontend/ already exist as separate apps. Write
docker-compose.yml at the repo root with three services: db
(postgis/postgis:16-3.4, named volume, port 5432), backend (build
./backend, depends_on db, port 8000), frontend (build ./frontend, port
5173). Confirm `docker compose up` builds and starts all three without
errors.
```

### Prompt 7 — [SETUP] .env.example + placeholder README

```
docker-compose.yml already exists (prior prompt). Add .env.example at
the repo root listing DATABASE_URL, ANTHROPIC_API_KEY, and any other
needed variables with placeholder values and one-line comments. Write a
short top-level README.md: project name, one-line description, tech
stack, and "getting started" (docker compose up) — just a placeholder,
it gets expanded into the full README near the end of this playbook.
```

### Prompt 8 — [DATABASE] Aviation core tables + migration

```
Design and implement the aviation half of the PostgreSQL + PostGIS
schema for SkyNexus as SQLAlchemy models in backend/app/models/, plus an
initial Alembic migration. Enable the postgis extension in the
migration.

Tables:
- regions(id, name, geom GEOMETRY(POLYGON,4326), centroid GEOMETRY(POINT,4326))
- airports(id, iata_code, name, geom GEOMETRY(POINT,4326), region_id FK)
- flight_routes(id, origin_airport_id FK, dest_airport_id FK, region_id FK)
- flight_observations(id, route_id FK nullable, callsign, icao24, timestamp,
  position GEOMETRY(POINT,4326), altitude_ft, speed_kt, heading_deg,
  source, ingested_at)

Every row-producing table needs source (text) and ingested_at
(timestamptz, default now()). Add GiST indexes on all geometry columns
and a btree index on flight_observations.timestamp. This migration will
be extended with more tables in the next few prompts — confirm
`alembic upgrade head` runs cleanly for now.
```

### Prompt 9 — [DATABASE] Satellite/weather/event core tables

```
The aviation core tables (regions, airports, flight_routes,
flight_observations) already exist from a prior migration. Add these
tables as new SQLAlchemy models plus a migration that extends the
schema:

- satellites(id, norad_id, name)
- satellite_observations(id, satellite_id FK, timestamp,
  position GEOMETRY(POINTZ,4326), altitude_km, source, ingested_at)
- weather_observations(id, region_id FK, timestamp,
  position GEOMETRY(POINT,4326), wind_speed_kt, precipitation_mm,
  storm_index, source, ingested_at)
- events(id, external_id, event_date, event_type, category, severity,
  position GEOMETRY(POINT,4326), region_id FK, description, source,
  ingested_at)

Same source/ingested_at convention. Add GiST indexes on geometry columns
and a btree index on events.region_id + event_date. Confirm
`alembic upgrade head` runs cleanly and all 8 core tables now exist.
```

### Prompt 10 — [DATABASE] Engine tables (baselines/anomalies/correlations)

```
All 8 core entity tables already exist. Add these "engine" tables as new
SQLAlchemy models plus a new migration:

- baselines(id, entity_type, entity_id, feature_name, window_start,
  window_end, mean_value, std_value, sample_count, computed_at)
- anomaly_scores(id, entity_type, entity_id, region_id FK, timestamp,
  feature_name, observed_value, z_score, isolation_forest_score,
  composite_score, severity_label, computed_at)
- event_correlations(id, anomaly_id FK, event_id FK,
  temporal_proximity_score, geographic_overlap_score, confidence_score,
  computed_at)

Add a btree index on anomaly_scores.region_id + timestamp. Confirm
`alembic upgrade head` runs cleanly on top of the prior migrations.
```

### Prompt 11 — [DATABASE] Index/report tables

```
The core and engine tables already exist. Add the final three tables as
new SQLAlchemy models plus a new migration:

- disruption_index(id, region_id FK, window_start, window_end,
  flight_anomaly_score, event_relevance_score, airspace_score,
  airport_activity_score, satellite_score, weather_score,
  composite_index, severity_label, confidence_pct, computed_at)
- what_changed_reports(id, region_id FK, event_id FK, before_start,
  before_end, after_start, after_end, metrics_json JSONB,
  ai_explanation, confidence_pct, generated_at)
- forecasts(id, region_id FK, generated_at, horizon_hours, metric_name,
  predicted_values JSONB)

Confirm `alembic upgrade head` runs cleanly and every table across all
migrations now exists in the database.
```

### Prompt 12 — [DATABASE] Seed region data

```
The full schema already exists. In backend/app/data/seed_regions.py,
define (as a Python list/dict of dicts, not yet inserted into the DB) a
small fixed set of 5-8 regions — e.g. Middle East, Eastern Europe, South
China Sea, North Atlantic, Pacific — each with a name and an approximate
bounding polygon (lat/lon coordinates) and centroid. Just define the
data structure and validate the polygons are well-formed (closed rings,
plausible coordinates); the insert/upsert logic and CLI come in the next
prompt.
```

### Prompt 13 — [DATABASE] Seed region upsert + CLI

```
backend/app/data/seed_regions.py already has the region data defined
(prior prompt). Add the logic that writes it: upsert each region into
the regions table by name (idempotent — safe to run more than once
without duplicating rows), computing the PostGIS geometry/centroid from
the defined coordinates. Add a CLI entry point:
python -m app.data.seed_regions. Print a summary of regions
inserted/updated when done. Run it and confirm the regions table is
populated.
```

---

## Phase 1 — Data Layer

### Prompt 14 — [DATA] Demo dataset — flights generation

```
The full schema exists. Create backend/app/data/demo_dataset.py: start
it with a small config section defining a chosen demo T0 event (region,
event date, a plausible invented scenario like an emergency airspace
restriction — keep it clearly a "demo scenario," not attributed to any
real ongoing conflict) and a 14-day window (T-7 to T+7).

In this prompt, generate only flight_observations: for ~8-12 routes
into/out of the demo region, hourly volume that runs at a stable
baseline for T-7..T-1, then drops ~30% and shows increased
route-deviation (avg deviation km) and delay (avg minutes) from T0
onward, with realistic noise (not a clean step function). Write through
the SQLAlchemy models, tagging source='demo_dataset'. Leave TODOs for
satellites/weather/events generation, to be added in later prompts.
```

### Prompt 15 — [DATA] Demo dataset — satellites generation

```
backend/app/data/demo_dataset.py already has the T0/region config and
flight_observations generation (prior prompt) — don't change that
logic. Add satellite_observations generation to the same file: for 3-5
demo satellites, a stable ground-track pattern before T0, with a few
showing a >2-sigma deviation after T0. Tag source='demo_dataset'.
```

### Prompt 16 — [DATA] Demo dataset — weather generation

```
demo_dataset.py already generates flights and satellites (prior
prompts). Add weather_observations generation to the same file: for the
demo region, unremarkable, seasonal-norm values throughout
(wind/precip/storm index) across the full 14-day window — intentionally
unremarkable, so the pipeline later correctly rules weather out as an
explanation. Tag source='demo_dataset'.
```

### Prompt 17 — [DATA] Demo dataset — events generation

```
demo_dataset.py already generates flights, satellites, and weather
(prior prompts). Add events generation to the same file: 2-4
GDELT-style event rows clustered right around T0 in the demo region
(e.g. "Emergency airspace restriction (NOTAM)", "Major diplomatic
announcement"), each with lat/lon inside the region and a
category/severity. Tag source='demo_dataset'.
```

### Prompt 18 — [DATA] Demo dataset — CLI + reset + summary

```
demo_dataset.py now generates all four data types (flights, satellites,
weather, events) from prior prompts. Add the CLI/orchestration layer on
top, without changing the generation logic itself: make event date,
region, and noise level configurable via CLI args (argparse). Add a
`python -m app.data.demo_dataset --reset` mode that clears and reseeds
all four tables. Print a summary (row counts per table, the chosen T0
timestamp) when done. Run it once end-to-end and confirm all four
tables are populated.
```

### Prompt 19 — [DATA] TLE connector — fetch, parse, store satellites

```
Create backend/app/data/tle_connector.py. In this prompt, implement only
the fetch/store-satellites half:
- Fetch active TLE sets from CelesTrak (celestrak.org/NORAD/elements/,
  e.g. the "active" or "stations" group — pick a small, stable group of
  20-50 objects) using httpx. No API key required.
- Parse TLE pairs and upsert into the satellites table (norad_id, name).

Leave propagation and observation-insertion for the next prompt.
```

### Prompt 20 — [DATA] TLE connector — propagate + insert observations

```
tle_connector.py already fetches/parses TLEs and upserts satellites
(prior prompt). Add to the same file:
- Use the sgp4 Python package to propagate each object's position at
  5-minute intervals over a requested time window, converting ECI
  coordinates to lat/lon/altitude, and insert into
  satellite_observations with source='celestrak_tle'.
- Wrap it as fetch_and_propagate(start: datetime, end: datetime,
  step_minutes: int = 5) -> int (rows inserted).
```

### Prompt 21 — [DATA] TLE connector — retry/backoff + CLI + test

```
tle_connector.py already has fetch/parse/store and
fetch_and_propagate() (prior prompts). Add basic retry/backoff on the
HTTP fetch, a CLI entry point (python -m app.data.tle_connector), and a
unit test (with a small fixture TLE) verifying the propagated position
is a plausible lat/lon/altitude.
```

### Prompt 22 — [DATA] Weather connector — fetch_weather function

```
Create backend/app/data/weather_connector.py. In this prompt, implement
only:
- fetch_weather(region_id: int, start_date: date, end_date: date) ->
  dict: look up the region's centroid from the regions table, call
  https://archive-api.open-meteo.com/v1/archive (no key required) with
  latitude, longitude, start_date, end_date, and
  hourly=windspeed_10m,precipitation, and return the parsed hourly data.
  Don't write to the database yet — that's the next prompt.
```

### Prompt 23 — [DATA] Weather connector — storm_index + insert

```
weather_connector.py already has fetch_weather() returning parsed hourly
data (prior prompt). Add to the same file:
- A storm_index calculation (0-100) from wind speed + precipitation,
  documented in a docstring (e.g. a normalized weighted sum, capped at
  100).
- Insert one row per region per hour into weather_observations with
  source='open-meteo', using fetch_weather()'s output.
```

### Prompt 24 — [DATA] Weather connector — caching + retry + CLI + test

```
weather_connector.py already fetches, computes storm_index, and inserts
(prior prompts). Add: basic retry on rate limits, a raw-response cache
to backend/app/data/.cache/ during development, a CLI entry point, and a
unit test with a mocked HTTP response.
```

### Prompt 25 — [DATA] GDELT connector — fetch + filter events

```
Create backend/app/data/gdelt_connector.py. In this prompt, implement
only the fetch/filter half, using GDELT 2.0's raw Event Database (not
the DOC 2.0 news-search API):
- Pull from GDELT's raw CSV export files (updated every 15 min, no key
  required) covering a target date range, or use a wrapper package like
  gdeltPyR / gdelt-client — your call.
- Filter rows to ones whose ActionGeo_Lat/Long fall inside a given
  region's polygon (shapely, or PostGIS ST_Contains after a bulk
  insert). Restrict to a narrow date range and bounding box, not a
  global pull — note this scoping decision in a comment.

Return the filtered rows in memory; don't map categories or insert into
the DB yet — those are the next prompt.
```

### Prompt 26 — [DATA] GDELT connector — category mapping + insert

```
gdelt_connector.py already fetches and filters raw GDELT rows (prior
prompt). Add to the same file:
- fetch_events(region: Region, start_date: date, end_date: date) -> int:
  wraps the fetch/filter step, then maps GDELT's EventCode/QuadClass
  into a simpler category (political / disaster / airspace /
  infrastructure / other) and a 0-100 severity using GoldsteinScale and
  NumMentions as inputs — document the mapping in a comment.
- Insert into events with source='gdelt'.
```

### Prompt 27 — [DATA] GDELT connector — CLI + test

```
gdelt_connector.py already has fetch_events() with category mapping and
insertion (prior prompt). Add a CLI entry point and a test using a small
fixture CSV instead of a live GDELT call.
```

### Prompt 28 — [DATA] Ingestion pipeline — mode dispatch

```
The demo dataset generator and the three real connectors (TLE, weather,
GDELT) already exist. Start backend/app/data/pipeline.py — the deck's L2
"Ingestion & Processing" layer. In this prompt, implement only:
- An IngestionSummary dataclass with row counts per table and elapsed
  time.
- run_ingestion(mode: Literal["demo", "live"], region_ids: list[int],
  start: datetime, end: datetime) -> IngestionSummary: "demo" mode calls
  the demo_dataset generator; "live" mode calls the TLE, weather, and
  GDELT connectors for the given regions/window (flights stay demo-only
  for now — flag this clearly in a comment and in IngestionSummary).

Leave cleaning and feature engineering for later prompts.
```

### Prompt 29 — [DATA] Ingestion pipeline — cleaning step

```
pipeline.py already has run_ingestion() with demo/live dispatch (prior
prompt). Add a cleaning step, called after ingestion: drop rows with
null position/timestamp, clip physically-impossible values (negative
altitude, speed beyond a reasonable max), and dedupe on (entity_id,
timestamp, source). Leave a TODO for feature engineering.
```

### Prompt 30 — [DATA] Ingestion pipeline — flight feature engineering

```
pipeline.py already has run_ingestion() and the cleaning step (prior
prompts). Add the flight-route feature-engineering step: a rolling
hourly volume count and an average route-deviation-km per hour
(deviation from that route's median great-circle path), writing these as
derived columns/tables the anomaly engine will need.
```

### Prompt 31 — [DATA] Ingestion pipeline — satellite/region features + CLI + test

```
pipeline.py already has flight feature engineering (prior prompt). Add
the remaining feature-engineering steps to the same file: for
satellites, per-observation deviation-from-expected-track in km; for
regions, an hourly aggregate weather storm_index. Then expose
`python -m app.data.pipeline --mode demo` as a CLI command, and add a
test that runs it end-to-end against a test database and asserts
non-zero row counts in every table.
```

---

## Phase 2 — ML: Baseline + Anomaly Engine

### Prompt 32 — [ML] Baseline builder — mean/std computation

```
Create backend/app/ml/baseline.py. In this prompt, implement only the
computation half: build_baselines(entity_type: str, window_days: int =
30, as_of: datetime | None = None) computing, for each entity of the
given type (flight_route, satellite, region) and each relevant feature
(hourly volume, route-deviation-km, delay-min for routes;
track-deviation-km for satellites; storm_index for regions), the mean
and std over the trailing window_days ending at as_of (default: now).
Return the computed values (as a list of dicts/dataclasses) without
writing to the DB yet.
```

### Prompt 33 — [ML] Baseline builder — upsert + epsilon guard + test

```
baseline.py already computes mean/std per entity/feature (prior
prompt). Add: upserting the computed values into the baselines table
with window_start/window_end/computed_at set, returning the row count
as build_baselines()'s return value. Guard against a std of 0 (flat
history) by flooring it to a small epsilon. Add a unit test with a
synthetic history checking the mean/std and confirming a flat history
doesn't produce a zero std.
```

### Prompt 34 — [ML] Z-score — score_observation

```
baseline.py already exists (prior prompts). Create backend/app/ml/
zscore.py with score_observation(entity_type: str, entity_id: int,
feature_name: str, observed_value: float, at: datetime) -> float | None:
look up the most recent baseline for that entity/feature, return
(observed_value - mean) / std, or None if no baseline exists yet. Add a
unit test with a synthetic baseline (mean=100, std=10) checking that an
observed value of 150 scores z≈5 and 100 scores z≈0, and that it returns
None with no baseline.
```

### Prompt 35 — [ML] Z-score — score_window batch scorer

```
zscore.py already has score_observation() (prior prompt). Add
score_window(entity_type: str, start: datetime, end: datetime) -> int:
batch-score every observation of that entity type in the window using
score_observation(), writing z_score into anomaly_scores
(composite_score and isolation_forest_score stay null — a later prompt
fills those in). Add a test asserting the right number of anomaly_scores
rows get written for a small synthetic window.
```

### Prompt 36 — [ML] Isolation Forest — train_isolation_forest

```
Create backend/app/ml/isolation_forest.py. In this prompt, implement
only train_isolation_forest(entity_type: str, window_days: int = 30) ->
a fitted sklearn.ensemble.IsolationForest, trained on the trailing
window_days of that entity type's full feature matrix (all features
together, not one at a time). Persist the fitted model to
backend/app/ml/artifacts/{entity_type}_iforest.joblib via joblib.
```

### Prompt 37 — [ML] Isolation Forest — scoring function + test

```
isolation_forest.py already has train_isolation_forest() (prior
prompt). Add score_with_isolation_forest(entity_type: str, entity_id:
int, feature_vector: dict[str, float]) -> float: load the persisted
model, return decision_function() rescaled to 0-100 (higher = more
anomalous — IsolationForest's raw score is inverted; handle that
inversion here and document it). Add a test that trains on a small
synthetic dataset with 2 obvious outliers and asserts they score
meaningfully higher than the normal points.
```

### Prompt 38 — [ML] Composite score — composite_score function + test

```
zscore.py and isolation_forest.py already exist (prior prompts). Create
backend/app/ml/composite.py with composite_score(z_score: float,
iforest_score: float) -> tuple[float, str]: combine the two into one
0-100 score and a severity_label (normal / low / medium / high) — clip
|z_score| to a 0-100 range via a configurable scaling constant, then
take a weighted average with the isolation-forest score (name the
weights as constants at the top of the file, e.g. Z_WEIGHT = 0.5,
IFOREST_WEIGHT = 0.5). Add a test with a few (z_score, iforest_score)
pairs asserting the composite lands in the expected severity bucket.
```

### Prompt 39 — [ML] Composite score — update_composite_scores batch fn

```
composite.py already has composite_score() (prior prompt). Add
update_composite_scores(start: datetime, end: datetime) -> int: for
every anomaly_scores row in the window missing a composite_score,
isolation-forest-score it (reusing isolation_forest.py) and fill in
composite_score + severity_label via composite_score(). Add a test
covering a small batch of rows.
```

---

## Phase 3 — Correlation + Impact Engine

### Prompt 40 — [ML/BACKEND] Correlation — temporal + geographic scoring

```
Create backend/app/ml/correlation.py. In this prompt, implement only the
two component scores as pure functions (no DB write yet):
- temporal_proximity_score(anomaly_time: datetime, event_time: datetime,
  window_hours: int = 72) -> float (0-100): closer in time = higher,
  decaying linearly or exponentially to 0 at the window edge (pick one,
  document it).
- geographic_overlap_score(anomaly_region_centroid, event_position,
  max_distance_km: float) -> float (0-100): based on PostGIS
  ST_Distance, decaying to 0 at max_distance_km.

Add unit tests for both at a few distances/time offsets.
```

### Prompt 41 — [ML/BACKEND] Correlation — confidence combine + persist + test

```
correlation.py already has temporal_proximity_score() and
geographic_overlap_score() (prior prompt). Add:
- correlate_anomaly(anomaly_id: int) -> list[EventCorrelation]: for a
  given anomaly_scores row, find every events row within a configurable
  time window and same/adjacent region, compute confidence_score (0-100)
  as a named-weight combination of the two component scores plus the
  anomaly's own composite_score, and write results into
  event_correlations.

Add tests with a synthetic anomaly + nearby event (expect high
confidence) and an anomaly with no nearby events (expect an empty
list).
```

### Prompt 42 — [ML/BACKEND] Weather-explanation filter + test

```
baseline.py already exists. Create backend/app/ml/weather_filter.py with
weather_explanation_score(region_id: int, at: datetime) -> float
(0-100): look up weather_observations for that region/time and compare
storm_index against that region's own weather baseline (reuse
baseline.py), scaled to 0-100 — LOW means weather does not explain the
deviation. Add a test with an unremarkable-weather scenario (expect LOW)
and a stormy scenario (expect HIGH).
```

### Prompt 43 — [ML/BACKEND] Disruption Index — component score gathering

```
correlation.py and weather_filter.py already exist. Start
backend/app/ml/disruption_index.py. In this prompt, implement only the
data-gathering half: a function that, given (region_id, window_start,
window_end), pulls and returns the six raw component values:
- flight_anomaly_score: mean composite_score of flight-route anomalies
  in the region
- event_relevance_score: mean confidence_score of event_correlations
  tied to those anomalies
- airspace_score: share of flights with route deviation above a
  configurable threshold, scaled to 0-100
- airport_activity_score: |% change in hourly flight volume vs
  baseline|, scaled to 0-100
- satellite_score: mean composite_score of satellite anomalies whose
  ground track passes through the region
- weather_score: output of weather_explanation_score

Don't combine them into a composite index yet — that's the next prompt.
```

### Prompt 44 — [ML/BACKEND] Disruption Index — composite combine + severity + test

```
disruption_index.py already gathers the six raw component scores (prior
prompt). Add compute_disruption_index(region_id, window_start,
window_end) -> DisruptionIndexResult that combines them into
composite_index via a weighted average — put the six weights in a
WEIGHTS dict at the top of the file as named constants (defaults:
flight_anomaly 0.25, event_relevance 0.20, airspace 0.20,
airport_activity 0.15, satellite 0.10, weather 0.10, inverse-weighted so
a low weather score doesn't drag the index down). Derive severity_label
(normal <40, low, medium, high >=70 — named constants) and a
confidence_pct (based on sample sizes / data completeness). Add a basic
unit test with synthetic component inputs.
```

### Prompt 45 — [ML/BACKEND] Disruption Index — persist + rolling recompute

```
disruption_index.py already has compute_disruption_index() (prior
prompt) — don't change its logic. Add:
- persist_disruption_index(...) writing one row per call into
  disruption_index.
- A service function to recompute the index for all regions over a
  rolling window (e.g. "last 24h"), callable by a scheduler later.
```

### Prompt 46 — [ML/BACKEND] Disruption Index — validation test

```
disruption_index.py already has compute + persist logic (prior prompts).
Add the key validation test using the demo dataset's T0 event: assert
the post-event 7-day window scores meaningfully higher (and HIGH-ish)
than the pre-event window, which should stay in the normal band — this
is the specific validation claim needed for the Results slide. Get it
passing before building UI on top of it.
```

---

## Phase 4 — Backend API

### Prompt 47 — [BACKEND] FastAPI main.py + CORS + startup check

```
Extend backend/app/main.py (from the earlier placeholder): add CORS
middleware allowing the frontend's dev origin, and a startup event that
verifies the DB connection. Don't add routers or db.py yet — those are
the next prompts.
```

### Prompt 48 — [BACKEND] db.py session/engine

```
main.py already has CORS + startup check (prior prompt). Create
backend/app/core/db.py: SQLAlchemy engine + session factory + a get_db()
dependency, using DATABASE_URL from config.py.
```

### Prompt 49 — [BACKEND] Empty router skeleton

```
db.py already exists (prior prompt). Create app/api/ with one router
module per resource: regions.py, flights.py, satellites.py,
anomalies.py, events.py, disruption_index.py, what_changed.py,
forecast.py, stats.py — each with a placeholder GET for now, mounted
under /api/{resource} and registered in main.py. Confirm every
placeholder route shows up at /docs.
```

### Prompt 50 — [BACKEND] Core entity schemas

```
The router skeleton exists. Add app/schemas/ Pydantic response models
for the core entity tables: RegionOut, AirportOut, FlightRouteOut,
FlightObservationOut, SatelliteOut, SatelliteObservationOut,
WeatherObservationOut, EventOut. For any model with a PostGIS geometry
column, expose lat/lon (and altitude where relevant) as plain floats.
Don't wire these into routers yet.
```

### Prompt 51 — [BACKEND] Analysis schemas

```
Core entity schemas already exist (prior prompt). Add the remaining
Pydantic response models to app/schemas/: BaselineOut, AnomalyScoreOut,
EventCorrelationOut, DisruptionIndexOut, WhatChangedReportOut,
ForecastOut.
```

### Prompt 52 — [BACKEND] GET /api/regions endpoints

```
Router skeleton and schemas already exist. Implement the real logic in
app/api/regions.py:
GET /api/regions -> list of regions, each with its latest
disruption_index row (or null) and centroid lat/lon.
GET /api/regions/{region_id} -> region detail: the above plus recent
anomaly_scores and events counts.
Use proper SQLAlchemy queries (no N+1s), a response_model, and at least
one pytest per endpoint against a seeded test DB.
```

### Prompt 53 — [BACKEND] GET /api/flights/live endpoint

```
regions.py already has real logic (prior prompt). Implement app/api/
flights.py: GET /api/flights/live?region_id=&limit=200 -> most recent
flight_observations (one per active route/callsign), as {lat, lon,
altitude_ft, heading_deg, callsign, route_id, is_anomalous} —
is_anomalous true if that route has an unresolved anomaly_scores row
above the "medium" threshold in the last hour. Add a response_model and
a pytest against a seeded test DB.
```

### Prompt 54 — [BACKEND] GET /api/satellites/live endpoint

```
flights.py already exists (prior prompt). Implement app/api/
satellites.py: GET /api/satellites/live -> most recent
satellite_observations per satellite, same shape pattern as flights
(lat, lon, altitude_km, is_anomalous). Add a response_model and a
pytest against a seeded test DB.
```

### Prompt 55 — [BACKEND] GET /api/anomalies endpoint

```
Implement app/api/anomalies.py: GET /api/anomalies?region_id=&since=
&severity= -> filterable anomaly_scores list, newest first, paginated
(limit/offset). Add a response_model and a pytest against a seeded test
DB.
```

### Prompt 56 — [BACKEND] GET /api/events endpoint

```
anomalies.py already exists (prior prompt). Implement app/api/events.py:
GET /api/events?region_id=&since= -> filterable events list, newest
first. Add a response_model and a pytest against a seeded test DB.
```

### Prompt 57 — [BACKEND] GET /api/disruption-index endpoint

```
Implement app/api/disruption_index.py: GET /api/disruption-index ->
latest disruption_index row per region (no N+1 — use a subquery for
"latest per region"). Add a response_model and a pytest against a seeded
test DB.
```

### Prompt 58 — [BACKEND] GET /api/stats/summary endpoint

```
disruption_index.py router already exists (prior prompt). Implement
app/api/stats.py: GET /api/stats/summary -> {flights_tracked,
satellites_tracked, events_tracked, active_anomalies} counts. Add a
response_model and a pytest against a seeded test DB.
```

### Prompt 59 — [BACKEND] What Changed — aviation + satellite metrics

```
All core GET endpoints and the ML engine (disruption_index.py,
correlation.py, weather_filter.py) already exist. Start
backend/app/services/what_changed.py. In this prompt, implement only:
- Resolving the before window (T-window_days..T) and after window
  (T..T+window_days) around an event's event_date.
- Pulling aviation metrics for both windows: daily flight volume, avg
  route deviation km, avg delay min, plus their %/absolute change.
- Pulling satellite metrics: baseline deviation in sigma, and a
  behavior label ("normal"/"unusual") from whether it exceeds a
  threshold.

Return these as a partial dict for now; weather/events/overall come in
the next prompt.
```

### Prompt 60 — [BACKEND] What Changed — weather + events + overall + test

```
what_changed.py already gathers aviation and satellite metrics (prior
prompt) — don't change that logic. Add:
- Pulling the weather_explanation_score for the after window.
- Pulling event_correlations for anomalies in the after window tied to
  the event: temporal_proximity_score, geographic_overlap_score, and the
  anomaly/weather scores feeding disruption_index.
- Pulling (or computing on demand) the disruption_index
  composite_index + severity_label + confidence_pct for the after
  window.
- Assembling everything into one metrics_json payload matching the
  aviation / satellite / weather / events / overall_assessment sections,
  returned by a single public function, e.g. gather_what_changed_metrics
  (region_id, event_id, window_days).

Add a unit test using the demo dataset's T0 event asserting the returned
metrics_json's overall composite_index/severity_label match the
disruption_index validation test.
```

### Prompt 61 — [BACKEND] What Changed — POST endpoint wiring

```
what_changed.py's service function (gather_what_changed_metrics) already
exists (prior prompts). Wire up POST /api/what-changed in
app/api/what_changed.py: request body { region_id: int, event_id: int |
null, window_days: int = 7 } (if event_id is omitted, use the most
severe event in the region near "now"). Call the metrics service to get
metrics_json and return it directly for now — AI explanation and
persistence come in the next prompts.
```

### Prompt 62 — [BACKEND] What Changed — persistence + test

```
POST /api/what-changed already returns metrics_json (prior prompt). Add
persistence: persist the response as a what_changed_reports row
(ai_explanation can stay a TODO placeholder string until the AI
explainer service exists) and return the persisted report. Add a test
using the demo dataset's T0 event asserting the endpoint response's
overall composite_index and severity_label match the earlier validation
test.
```

### Prompt 63 — [BACKEND] AI explainer — system prompt + API call

```
Implement backend/app/services/ai_explainer.py: explain(metrics_json:
dict) -> str, calling the Anthropic API (via the anthropic Python SDK;
read ANTHROPIC_API_KEY from settings) with a system prompt that:
- Is given ONLY the aggregated metrics_json payload — never raw rows,
  and never told about any real-world cause beyond the
  category/description already resolved by the correlation engine.
- Is instructed to write 2-4 sentences: what changed, in which region,
  how confident the correlation is, ending with a line equivalent to
  "correlation does not establish causation."
- Is explicitly told never to assert a specific geopolitical, military,
  or security cause — only to describe the statistical pattern and name
  the category of the correlated event if one was matched.
- Uses a low temperature (e.g. 0.3).

Leave the offline fallback and tests for later prompts.
```

### Prompt 64 — [BACKEND] AI explainer — wire into What Changed endpoint

```
ai_explainer.py's explain() already exists (prior prompt). In
app/api/what_changed.py, replace the ai_explanation TODO placeholder
with a real call to explain(metrics_json), and persist the result in the
what_changed_reports row.
```

### Prompt 65 — [BACKEND] AI explainer — offline fallback

```
ai_explainer.py already has explain() calling the live Anthropic API
(prior prompts) — don't change that call logic. Add a fallback: if the
API call fails or ANTHROPIC_API_KEY isn't set, return a deterministic
template string built from metrics_json (e.g. f"Significant regional
disruption detected ({index}/100, {confidence}% confidence). Correlation
does not establish causation.") so the rest of the app still works
offline/in CI.
```

### Prompt 66 — [BACKEND] AI explainer — tests

```
ai_explainer.py's fallback already exists (prior prompt). Add a test
asserting the fallback template path works without a live key, and (if a
key is available in the dev environment) a manual/skipped test for the
real call.
```

### Prompt 67 — [BACKEND] Forecast — forecast_region function

```
Create backend/app/services/forecast.py: forecast_region(region_id: int,
horizon_hours: int = 6) -> ForecastResult. Per the project's own Next
Steps slide, keep this simple and explainable, not a deep model: for
each of flight congestion, route deviation, and airport pressure, pull
the trailing ~72h of hourly values for the region and project forward
horizon_hours using a simple, documented method (e.g. Holt's linear
exponential smoothing via statsmodels, or a basic weighted
moving-average trend extrapolation) — pick one, name it in a docstring,
keep it under ~40 lines per metric. Return predicted values as {
hour_offset, predicted_value } plus a naive confidence band (+/- recent
residual std). Don't persist or wire the endpoint yet.
```

### Prompt 68 — [BACKEND] Forecast — persistence + endpoint + test

```
forecast.py already has forecast_region() (prior prompt). Add
persistence to the forecasts table, then wire GET
/api/forecast/{region_id} in app/api/forecast.py. Add a test with a
synthetic upward-trending series asserting the forecast continues the
trend direction (not that it hits an exact number).
```

### Prompt 69 — [BACKEND] Playback — simulated clock (stretch)

```
Optional — only do this after Phases 1-4's core prompts are working.
Create backend/app/services/playback.py: a background task (FastAPI's
BackgroundTasks, or a simple asyncio loop started on app startup) that
replays the demo dataset on a compressed timeline (e.g. 14 real days
played back over 14 minutes) by advancing a shared "simulated now"
clock, active only when SIMULATE_LIVE=true is set. Don't wire it into
the live endpoints yet — that's the next prompt.
```

### Prompt 70 — [BACKEND] Playback — wire into endpoints + /api/clock (stretch)

```
playback.py's simulated clock already exists (prior prompt). Wire
/api/flights/live, /api/satellites/live, /api/anomalies, etc. to use the
simulated clock instead of wall-clock time when SIMULATE_LIVE=true. Add
GET /api/clock returning the current simulated timestamp. Document
clearly (inline comment is enough for now) that this is a demo-mode
simulation, not a live feed, and how to disable it.
```

---

## Phase 5 — Frontend

### Prompt 71 — [FRONTEND] Theme — color tokens

```
Create frontend/src/theme/tokens.ts: color design tokens matching a dark
intelligence-dashboard look — near-black/navy background, a deep teal
accent for primary UI/positive states, a warm orange accent for
alerts/highlights/severity, and a light cream/off-white for
title-slide-style headers. Export as CSS custom properties on :root plus
a matching TS const object. Fonts come in the next prompt.
```

### Prompt 72 — [FRONTEND] Theme — fonts

```
tokens.ts already has color tokens (prior prompt). Add typography
tokens to the same file: a clean geometric sans for headers and a
monospace font for data/HUD panels (matching a technical-readout
style) — self-host or use a Google Fonts import, documented as a
deliberate choice.
```

### Prompt 73 — [FRONTEND] API client — TypeScript types

```
Theme tokens already exist. Create frontend/src/api/client.ts (types
only for now): TypeScript interfaces for every backend response shape
matching the Pydantic schemas (RegionOut, FlightObservationOut,
SatelliteObservationOut, AnomalyScoreOut, EventOut, DisruptionIndexOut,
WhatChangedReportOut, ForecastOut, StatsSummary). No axios calls yet.
```

### Prompt 74 — [FRONTEND] API client — request functions

```
client.ts already has the TS interfaces (prior prompt). Add an axios
instance with baseURL from import.meta.env.VITE_API_URL, and typed
request functions matching every backend endpoint (getRegions,
getFlightsLive, getSatellitesLive, getAnomalies, getEvents,
getDisruptionIndex, postWhatChanged, getForecast, getStatsSummary). Add
frontend/.env.example with VITE_API_URL.
```

### Prompt 75 — [FRONTEND] App shell layout

```
Theme tokens and the API client already exist. Create
frontend/src/App.tsx: a full-bleed dark layout shell with three regions
— a top stat bar, a center area for the globe, and a right sidebar —
using CSS grid, styled from the theme tokens, with labeled placeholder
boxes only (no real content yet). Get it rendering with zero console
errors.
```

### Prompt 76 — [FRONTEND] Globe — sphere + texture

```
The App shell exists with a placeholder center region. Create
frontend/src/three/Globe.tsx. In this prompt, implement only: a React
component wrapping a three.js scene with a sphere (radius ~5 units) and
a subtle dotted/wireframe world-map texture (a simple canvas-drawn
dot-grid over an equirectangular world outline, or a coarse point cloud
approximating continents — document whichever approach you take).
Camera/controls and the layer API come in the next prompt.
```

### Prompt 77 — [FRONTEND] Globe — controls + layer API

```
Globe.tsx already renders the base sphere with texture (prior prompt).
Add: OrbitControls for rotate/zoom/pan (verify the installed three.js
version before importing from three/examples/jsm; vendor or use an
alternative if it doesn't resolve cleanly); auto-rotate slowly when
idle, stopping on user interaction; and an imperative ref API
(latLonToVector3(lat, lon, altitude?) plus a way for parent components
to add/remove Object3D layers) so later prompts can add data layers
without this component knowing about them. Render it inside App.tsx's
center region and confirm smooth 60fps rotation.
```

### Prompt 78 — [FRONTEND] Flight arcs — geometry + color

```
Globe.tsx exists with the layer API (prior prompt); the API client
already has getFlightsLive(). Create frontend/src/three/FlightArcs.tsx.
In this prompt, implement only: given a /api/flights/live response, draw
a great-circle arc (a QuadraticBezierCurve3 or similar lifted-above-the-
surface curve, not a straight chord) between each flight's recent
positions or route endpoints, colored by is_anomalous (teal/normal vs
orange/red anomalous). Animation and polling come next.
```

### Prompt 79 — [FRONTEND] Flight arcs — animation + polling

```
FlightArcs.tsx already draws colored arcs from static data (prior
prompt). Add: a small dot animated traveling along each arc to suggest
motion; a cap on total arc count (e.g. top 100 by recency) for
performance; and polling of /api/flights/live on an interval (e.g. every
10-15s) using useEffect + setInterval. Wire it into Globe.tsx's layer
API.
```

### Prompt 80 — [FRONTEND] Satellite tracks — markers

```
Globe.tsx and FlightArcs.tsx already exist; the API client has
getSatellitesLive(). Create frontend/src/three/SatelliteTracks.tsx. In
this prompt, implement only: given /api/satellites/live, draw each
satellite as a small sphere at its propagated position. Orbital rings,
pulsing, and polling come next.
```

### Prompt 81 — [FRONTEND] Satellite tracks — orbital ring + pulse + polling

```
SatelliteTracks.tsx already renders satellite markers (prior prompt).
Add: a faint inclined orbital ring per satellite (approximating from
recent position history is fine); pulsing/recoloring a marker when its
latest anomaly_scores composite_score is above the medium threshold; and
polling on the same 10-15s interval as FlightArcs. Wire it into Globe.
tsx's layer API.
```

### Prompt 82 — [FRONTEND] Anomaly zones — ring rendering by severity

```
Globe.tsx, FlightArcs.tsx, and SatelliteTracks.tsx already exist; the
API client has getDisruptionIndex(). Create
frontend/src/three/AnomalyZones.tsx. In this prompt, implement only: for
each region from /api/disruption-index, draw a ring/disc at its
centroid, radius and pulse speed scaled by composite_index, color scaled
by severity_label (green/teal -> yellow -> orange -> red), animated with
a sine-wave driven opacity/scale pulse. Click/hover interactivity comes
next.
```

### Prompt 83 — [FRONTEND] Anomaly zones — click + hover interactivity

```
AnomalyZones.tsx already renders pulsing severity rings (prior prompt).
Add: click handling (raycasting against the globe, or an invisible
larger hit-sphere per zone) that sets a selectedRegionId in local state
for now (a later prompt unifies this into shared global state); and a
hover tooltip showing region name + composite_index + severity label.
Wire it into Globe.tsx's layer API.
```

### Prompt 84 — [FRONTEND] TopStatBar component

```
The App shell and API client already exist. Create
frontend/src/components/TopStatBar.tsx: reads /api/stats/summary and
renders the four counters (flights tracked, satellites tracked, events
tracked, active anomalies), a "LIVE" indicator and current timestamp
(real time for now), and a "What Changed?" button (leave onClick as a
TODO — the modal doesn't exist yet). Drop it into App.tsx's top stat bar
region.
```

### Prompt 85 — [FRONTEND] DisruptionGauge component

```
TopStatBar.tsx already exists (prior prompt). Create
frontend/src/components/DisruptionGauge.tsx: a radial/donut gauge
(recharts RadialBarChart, or a hand-rolled SVG arc) showing the selected
region's (or globally highest) composite_index 0-100 with the
severity_label as the center label. Add it to the sidebar's top section
in App.tsx.
```

### Prompt 86 — [FRONTEND] RegionalAnomalyList component

```
DisruptionGauge.tsx already exists (prior prompt). Create
frontend/src/components/RegionalAnomalyList.tsx: a ranked list of all
regions from /api/disruption-index, sorted by composite_index
descending, each row showing name, severity_label badge, and score.
Clicking a row selects that region using the same local-selection
approach AnomalyZones.tsx used (a later prompt unifies selection into
shared state). Add it below DisruptionGauge in App.tsx.
```

### Prompt 87 — [FRONTEND] AnomalyAlertFeed component

```
The API client has getAnomalies(). Create
frontend/src/components/AnomalyAlertFeed.tsx: reads /api/anomalies,
filtered to recent + medium/high severity, newest first, each row
showing entity/region, a short human-readable description derived
client-side from entity_type/feature_name/severity, and a relative
timestamp. Add it to the sidebar's lower section in App.tsx.
```

### Prompt 88 — [FRONTEND] EventTimeline component

```
AnomalyAlertFeed.tsx already exists (prior prompt); the API client has
getEvents(). Create frontend/src/components/EventTimeline.tsx: reads
/api/events for the selected region (or globally), rendered as a
vertical timeline of timestamped event descriptions, newest first. Add
it to the sidebar's lower section in App.tsx.
```

### Prompt 89 — [FRONTEND] AIAssessmentPanel component

```
EventTimeline.tsx already exists (prior prompt). Create
frontend/src/components/AIAssessmentPanel.tsx: shows the ai_explanation
text from the most recent what_changed_reports entry for the selected
region (add a lightweight GET to the backend's what_changed router for
the latest saved report per region, or hold the last POST
/api/what-changed response in local state once the modal exists), with
the causation-disclaimer line visually distinguished (smaller/muted
text) from the main assessment. Add it to the sidebar's lower section.
```

### Prompt 90 — [FRONTEND] ForecastPanel component

```
AIAssessmentPanel.tsx already exists (prior prompt); the API client has
getForecast(). Create frontend/src/components/ForecastPanel.tsx: reads
/api/forecast/{region_id} and renders the 6-hour projection as small
sparkline/bar indicators per metric (flight congestion, route deviation,
airport pressure) with a directional +/-% label. Add it to the sidebar's
lower section.
```

### Prompt 91 — [FRONTEND] What Changed modal — open flow + picker

```
TopStatBar.tsx already has a "What Changed?" button with a TODO onClick.
Start frontend/src/components/WhatChangedModal.tsx. In this prompt,
implement only the open flow: opens from TopStatBar's button or a
region's context menu; if no region is selected, lets the user pick one
(a simple dropdown of regions) plus which event to compare against
(default to the most severe recent one) and a window_days control
(default 7). No fetch or report UI yet. Wire the TODO onClick in
TopStatBar.tsx to open this modal.
```

### Prompt 92 — [FRONTEND] What Changed modal — fetch + loading state

```
WhatChangedModal.tsx already has the open flow and picker (prior
prompt). Add: on confirm, POST /api/what-changed with a loading state,
storing the response in local component state; a minimal placeholder
body rendering a JSON dump of the response so the fetch/loading/error
flow is verifiable end-to-end (the real report layout comes next); and
make the modal closable and re-runnable without a full page reload.
```

### Prompt 93 — [FRONTEND] What Changed modal — aviation + satellite cards

```
WhatChangedModal.tsx already fetches and stores the report response
(prior prompt), currently showing a JSON placeholder. Replace part of
that placeholder with the real Aviation and Satellite cards (2x2 grid
layout, top-left and top-right): Aviation card — flight volume
before->after with %, route deviation before->after, average delay
before->after, each with an up/down arrow and colored delta (matching
"8,376 down 31%" styling). Satellite card — baseline deviation in sigma,
behavior label (normal/unusual badge). Leave weather/events/overall as
the remaining JSON placeholder for now.
```

### Prompt 94 — [FRONTEND] What Changed modal — weather + events cards

```
The Aviation and Satellite cards already exist (prior prompt). Replace
more of the JSON placeholder with the Weather and Events cards (bottom
row of the 2x2 grid): Weather card — estimated influence % with a
LOW/MED/HIGH badge plus the one-line explanation text. Events card —
relevant event count, the top event's description, and the five
correlation bars (temporal proximity, geographic overlap, flight
anomaly, satellite anomaly, weather explanation) as horizontal % bars.
```

### Prompt 95 — [FRONTEND] What Changed modal — overall assessment + disclaimer

```
All four report cards already exist (prior prompts) — remove the
remaining JSON placeholder now. Add the Overall Assessment banner: the
big composite_index/100 number with severity label and confidence %,
plus the AI explanation text. Add the footer disclaimer exactly as
required — something like "Correlation does not establish causation -
anomalies derived from public sources only" — always visible, never
conditionally hidden.
```

### Prompt 96 — [FRONTEND] Hooks — regions/index/stats

```
Every globe layer and sidebar panel currently fetches its own data with
local useEffect/useState. Create frontend/src/hooks/useRegions.ts,
useDisruptionIndex.ts, and useStatsSummary.ts — each returning { data,
isLoading, error } with a configurable poll interval (default ~15s).
Update RegionalAnomalyList, DisruptionGauge/AnomalyZones, and
TopStatBar to use these hooks instead of their own fetch logic; behavior
should be unchanged.
```

### Prompt 97 — [FRONTEND] Hooks — anomalies/events/forecast

```
useRegions/useDisruptionIndex/useStatsSummary already exist (prior
prompt). Add useAnomalies.ts, useEvents.ts, and useForecast.ts with the
same { data, isLoading, error } + poll-interval pattern. Update
AnomalyAlertFeed, EventTimeline, and ForecastPanel to use them instead of
local fetch logic.
```

### Prompt 98 — [FRONTEND] Hooks — live flights/satellites

```
The previous six hooks already exist. Add useFlightsLive.ts and
useSatellitesLive.ts, same pattern. Update FlightArcs and
SatelliteTracks to use them instead of their own polling logic.
```

### Prompt 99 — [FRONTEND] Global selection state store

```
All hooks now exist and every component uses them (prior prompts). Add
a global selectedRegionId + selectedEventId store (Zustand or React
context) and update TopStatBar, DisruptionGauge, RegionalAnomalyList,
AnomalyZones, EventTimeline, AIAssessmentPanel, ForecastPanel, and
WhatChangedModal to read/write from it, replacing any local selection
state they used before — so clicking a region anywhere updates every
panel consistently.
```

### Prompt 100 — [FRONTEND] Loading skeletons + error resilience

```
The global selection store already exists and every component uses it
(prior prompt). Do a final pass: add consistent loading skeletons
(simple pulsing placeholder blocks matching each component's shape) and
error states (a small inline retry affordance) to every hook-consuming
component — don't let one failed endpoint blank out the whole dashboard;
each panel should degrade independently. Confirm the whole dashboard
renders live data end-to-end and clicking a region anywhere updates all
panels.
```

---

## Phase 6 — Integration & Validation

### Prompt 101 — [INTEGRATION] docker-compose wiring finalize

```
Confirm and finalize docker-compose.yml: DATABASE_URL wired correctly
between db and backend, Alembic migrations run automatically on backend
startup (an entrypoint script step, not manual), and the frontend's
VITE_API_URL points at the backend service. Confirm `docker compose up`
from a clean clone brings up all three services with migrations applied
and no manual steps.
```

### Prompt 102 — [INTEGRATION] Bootstrap demo script

```
docker-compose.yml is already wired (prior prompt). Add
backend/app/scripts/bootstrap_demo.py (or a Makefile target) that, in
one command: runs migrations -> seeds regions -> generates the demo
dataset -> runs the ingestion pipeline -> builds baselines -> scores
anomalies -> runs correlation + weather filter -> computes the
disruption index for the demo window.
```

### Prompt 103 — [INTEGRATION] Bootstrap script — docs + confirm

```
bootstrap_demo.py already runs the full pipeline (prior prompt). Document
it as `make demo` or
`docker compose exec backend python -m app.scripts.bootstrap_demo` in
the README (a placeholder line is fine — the full README comes later).
Confirm `docker compose up` followed by the bootstrap command produces a
fully working dashboard with live anomaly zones, a populated regional
list, and a working "What Changed?" modal.
```

### Prompt 104 — [ML/DOCS] Validation notebook — data load

```
Create backend/notebooks/validation.ipynb. In this prompt, implement
only Section 1: load the demo dataset and baselines via the same DB
session the app uses — no duplicated logic, import from app.ml /
app.data. Print basic row counts to confirm the data loaded.
```

### Prompt 105 — [ML/DOCS] Validation notebook — flight volume chart

```
validation.ipynb already has the data-load section (prior prompt). Add
Section 2: reproduce the "Daily flight volume - before vs after" bar
chart (matplotlib), printing the actual before/after numbers your demo
dataset generated — pulled live from the loaded data, not hardcoded.
```

### Prompt 106 — [ML/DOCS] Validation notebook — correlation chart

```
validation.ipynb already has Sections 1-2 (prior prompts). Add Section
3: reproduce the "Event-correlation confidence" bar chart (temporal
proximity, geographic overlap, flight anomaly, satellite anomaly,
weather explanation) for the demo event, live from the pipeline output.
```

### Prompt 107 — [ML/DOCS] Validation notebook — disruption index chart

```
validation.ipynb already has Sections 1-3 (prior prompts). Add Section
4: reproduce the "Disruption Index" breakdown chart (the 6 weighted
components) and the final composite_index/confidence_pct, live from the
pipeline output.
```

### Prompt 108 — [ML/DOCS] Validation notebook — validation assertion

```
validation.ipynb already has Sections 1-4 (prior prompts). Add Section
5: a short written validation section — run compute_disruption_index on
the pre-event window and the post-event window separately, and
assert/print that pre-event stays in the "normal" band while post-event
reaches "HIGH". This is the specific claim needed for the Results slide.
```

### Prompt 109 — [ML/DOCS] Validation notebook — Isolation Forest eval

```
validation.ipynb already has Sections 1-5 (prior prompts). Add Section
6: a brief Isolation Forest evaluation — plot anomaly scores over the
full 14-day window as a time series with T0 marked, so the separation is
visually obvious.
```

### Prompt 110 — [DOCS] README — setup + pipeline section

```
The placeholder README.md from an earlier setup prompt already exists.
Replace it with: project name/tagline, the problem statement in 2-3
sentences, the 5-layer pipeline as a diagram (ASCII or Mermaid:
L1->L2->L3->L4->L5), the tech stack table, and full setup instructions
(clone -> docker compose up -> bootstrap demo command -> open
http://localhost:5173). Limitations and references come in the next
prompt.
```

### Prompt 111 — [DOCS] README — limitations + references section

```
README.md already has the setup/pipeline section (prior prompt). Add:
a "What this does NOT claim" section (no causation, data latency,
demo-data scope) — keep this prominent, not buried; and a references
section listing the six data/methodology sources used in the project.
```

### Prompt 112 — [DOCS] Viva demo script

```
The full README.md already exists (prior prompts). Create
backend/DEMO_SCRIPT.md — a short runbook for the viva/presentation:
step-by-step (start the stack, run the bootstrap, open the dashboard,
click through: globe overview -> click the high-severity region -> read
the sidebar gauge/list -> open "What Changed?" -> walk through each of
the four cards -> point out the causation disclaimer -> open the
forecast panel), plus one paragraph anticipating "how do you know this
isn't just noise?" with the answer already in the validation notebook
(pre/post baseline separation, isolation forest score timeline).
```
