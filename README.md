# SkyNexus

**Global Activity Anomaly & Impact Intelligence System**

SkyNexus is a mission-control style dashboard that fuses global flight traffic,
satellite positions, weather, and security events into a single real-time 3D
operating picture — then quantifies *how disrupted* each world region is and
explains *what changed*.

![status](https://img.shields.io/badge/status-working_prototype-brightgreen)
![tests](https://img.shields.io/badge/tests-6%2F6_passing-brightgreen)

---

## Quickstart

```bash
cp .env.example .env          # optional: add an ANTHROPIC_API_KEY for live AI text
docker compose up -d          # starts PostGIS + FastAPI + Vite
./bootstrap.sh                # migrations + regions + demo dataset
```

Then open:

| Service | URL |
|---|---|
| **Dashboard** | http://localhost:5173 |
| API | http://localhost:8000/api/health |
| Swagger docs | http://localhost:8000/docs |

## What you get

- **Interactive 3D globe** — drag to rotate, click region markers to inspect.
  Severity-colored markers with pulsing rings for hotspots, animated flight
  arcs with mid-flight aircraft positions, satellite markers with orbit hints,
  and event dots color-coded by severity.
- **Live stats bar** — 24h flight count, satellites tracked, active events,
  global disruption index and the most disrupted region.
- **Regional Disruption Index** — a 0–100 composite per region from flight
  volume vs its own baseline, event severity, and storm intensity.
- **What Changed?** — pick any region and window (6h/24h/72h) for a real
  before/after comparison across aviation, satellites, weather and events,
  with a plain-language overall assessment (Anthropic Claude if a key is
  configured, deterministic local analysis otherwise).
- **6-hour forecast** — flight-volume projection chart with history overlay.

## Demo dataset

`./bootstrap.sh` generates a geo-realistic world so the dashboard is alive
out of the box: 15 real hub airports, 10 great-circle routes with staged
flight positions, storm scenarios (Middle East storms hardest), regional
security events, and 5 satellites (ISS, Starlink, Sentinel-6A, NOAA-19,
Terra) on inclined ground tracks.

## Architecture

Five-layer pipeline:

1. **L1 Sources** — TLE (satellites), Open-Meteo (weather), GDELT (events) connectors
2. **L2 Ingestion** — cleaning, dedup, feature engineering
3. **L3 Anomaly engine** — Z-score + Isolation Forest against 30-day baselines
4. **L4 Correlation & impact** — temporal/geographic correlation, Disruption Index
5. **L5 Delivery** — 3D dashboard, What-Changed reports, forecasts

```
┌──────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ PostGIS  │◄──│  FastAPI backend │◄──│  React + Vite +     │
│ (port    │   │  (port 8000)     │   │  Three.js dashboard │
│  5432)   │   │  scoring + API   │   │  (port 5173)        │
└──────────┘   └──────────────────┘   └─────────────────────┘
```

### API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | Global counters + disruption index |
| `GET /api/regions/map` | Regions with centroid + scores (globe) |
| `GET /api/flights/live` | Route arcs with origin/destination + progress |
| `GET /api/satellites/live` | Latest ground-track position per satellite |
| `GET /api/events` | Recent security events with coordinates |
| `GET /api/disruption-index` | Per-region score breakdown |
| `GET /api/what-changed/{region_id}?hours=` | Before/after analysis + narrative |
| `GET /api/what-changed/{region_id}/forecast` | 6h flight-volume projection |
| `GET /api/anomalies` | Recent anomaly scores |

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, GeoAlchemy2 + PostGIS,
  scikit-learn, Alembic
- **Frontend:** React 19, TypeScript, Vite 8, Three.js, Zustand, Recharts, Tailwind CSS
- **Infra:** Docker Compose (PostGIS 16 + PostGIS 3.4)

## Tests

```bash
docker compose exec backend python -m pytest tests/ -q
```

## Limitations

- **Demo scale** — the seeded dataset covers hours/days, not months; baseline
  anomaly statistics are correspondingly coarse.
- **Connectors** — live TLE/weather/GDELT ingestion is implemented but the
  demo runs on generated data for reproducibility.
- **AI text** — without `ANTHROPIC_API_KEY`, What-Changed narratives come from
  a deterministic template analyzer.
- **Rendering** — real-time 3D needs a reasonably modern browser/GPU.
