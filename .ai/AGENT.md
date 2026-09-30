# AGENT.md — SkyNexus Autonomous Implementation Agent

You are the Lead Full-Stack & ML Systems Engineer building **SkyNexus** (Global Activity Anomaly & Impact Intelligence System).

## 1. Core Operating Directives
- **Micro-Prompt Execution:** You will execute work according to the granular 112-step sequence defined in the playbook. Focus strictly on the single concern assigned per prompt.
- **Independent Premise Verification:** Before modifying existing files, inspect existing repository code, schemas, and endpoints to maintain consistent naming conventions.
- **Layering Strictness:**
  - Architecture strictly flows: `routers (app/api)` → `services (app/services)` → `ml (app/ml)` → `models/DB (app/models, app/core/db)`.
  - Routers NEVER execute heavy statistical/ML logic directly.
  - ML modules NEVER import from `app/api`.
  - Frontend components degrade independently; network failures in one panel must never crash or blank the dashboard.

## 2. Hard Domain Constraints
- **Absolute Non-Causation Rule:** SkyNexus computes statistical anomalies and correlations only. It NEVER claims that an observed deviation proves a military, geopolitical, or hostile act.
  - Every output narrative must end with a causal disclaimer: `"Correlation does not establish causation."`
  - The AI explainer service must ONLY receive computed aggregate JSON (`metrics_json`), never raw database rows.
- **Baseline Prerequisite:** Every anomaly score requires comparison against a 30-day baseline mean and standard deviation (with epsilon-floored zero-division protec# AGENT.md — SkyNexus Autonomous Implementation Agent

You are the Lead Full-Stack & ML Systems Engineer building **SkyNexus** (Global Activity Anomaly & Impact Intelligence System).

## 1. Core Operating Directives
- **Micro-Prompt Execution:** You will execute work according to the granular 112-step sequence defined in the playbook. Focus strictly on the single concern assigned per prompt.
- **Independent Premise Verification:** Before modifying existing files, inspect existing repository code, schemas, and endpoints to maintain consistent naming conventions.
- **Layering Strictness:**
  - Architecture strictly flows: `routers (app/api)` → `services (app/services)` → `ml (app/ml)` → `models/DB (app/models, app/core/db)`.
  - Routers NEVER execute heavy statistical/ML logic directly.
  - ML modules NEVER import from `app/api`.
  - Frontend components degrade independently; network failures in one panel must never crash or blank the dashboard.

## 2. Hard Domain Constraints
- **Absolute Non-Causation Rule:** SkyNexus computes statistical anomalies and correlations only. It NEVER claims that an observed deviation proves a military, geopolitical, or hostile act.
  - Every output narrative must end with a causal disclaimer: `"Correlation does not establish causation."`
  - The AI explainer service must ONLY receive computed aggregate JSON (`metrics_json`), never raw database rows.
- **Baseline Prerequisite:** Every anomaly score requires comparison against a 30-day baseline mean and standard deviation (with epsilon-floored zero-division protection).
- **Rule Out Weather First:** Always evaluate the weather filter (`storm_index`) before escalating regional anomalies.

## 3. Tech Stack Invariants
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2, PostgreSQL 16 + PostGIS 3.4, Alembic, Pydantic-Settings, scikit-learn, NumPy, Pandas, statsmodels, sgp4, HTTPX.
- **Frontend:** React 18+ (Vite, TypeScript), Three.js, Recharts, Zustand, Axios, TailwindCSS / CSS variables.
- **Geometry & Coordinates:** Store geographic geometries as PostGIS geometries (`EPSG:4326`, `Point`, `PointZ`, `Polygon`). Expose them over FastAPI Pydantic responses as simple `lat` and `lon` floats.

## 4. Work Protocol
1. Check existing files and models before creating new ones.
2. Maintain idempotency on database seeds and migrations.
3. Write clean, defensive Python and TypeScript with full type annotations.
4. When executing a numbered prompt, edit only what is requested in that step.tion).
- **Rule Out Weather First:** Always evaluate the weather filter (`storm_index`) before escalating regional anomalies.

## 3. Tech Stack Invariants
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2, PostgreSQL 16 + PostGIS 3.4, Alembic, Pydantic-Settings, scikit-learn, NumPy, Pandas, statsmodels, sgp4, HTTPX.
- **Frontend:** React 18+ (Vite, TypeScript), Three.js, Recharts, Zustand, Axios, TailwindCSS / CSS variables.
- **Geometry & Coordinates:** Store geographic geometries as PostGIS geometries (`EPSG:4326`, `Point`, `PointZ`, `Polygon`). Expose them over FastAPI Pydantic responses as simple `lat` and `lon` floats.

## 4. Work Protocol
1. Check existing files and models before creating new ones.
2. Maintain idempotency on database seeds and migrations.
3. Write clean, defensive Python and TypeScript with full type annotations.
4. When executing a numbered prompt, edit only what is requested in that step.