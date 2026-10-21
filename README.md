# SkyNexus

SkyNexus watches 15 regions of the world and tells you which ones are behaving unusually right now. It combines four public data feeds (aircraft positions, satellite orbits, weather and earthquakes), compares each region with its own normal, and gives a 0–100 disruption index with a plain-language explanation.

It measures statistical change only. **Correlation does not establish causation.**

![Overview](docs/screenshots/overview.png)

## Run it

You need Docker Desktop (or Docker Engine with Compose v2).

**Windows:** double-click **`run.bat`** and choose from the menu.

1. Start with live data
2. Start with demo data
3. Stop
4. Show logs
5. Regenerate the demo world
6. Delete all data
7. Open the dashboard

`run.bat` checks that Docker is running and starts Docker Desktop if needed. It creates `.env`, builds and starts everything, waits until the app answers, then opens your browser. You can also pass the option directly: `run.bat demo`, `run.bat stop`.

**macOS / Linux:** `./run.sh` (same options, for example `./run.sh demo`).

**By hand:**

```bash
cp .env.example .env          # optional; defaults work
docker compose up --build
```

Open **http://localhost:5173**. The first start takes a few minutes while images build.

| Mode | How | What you get |
|---|---|---|
| Live (default) | `DATA_MODE=live` | Real feeds from adsb.lol, Celestrak, Open-Meteo and USGS, refreshed every 10 minutes. Needs internet. Air-traffic scores need about a day of history before they mean anything; until then they show "building baseline". |
| Demo | `DATA_MODE=demo` | A generated 8-day world that works offline and shows every feature immediately. It includes four scripted scenarios: a Red Sea surge with M6.1 and M5.8 quakes (Critical), a Taiwan Strait traffic drop (Elevated), a storm-explained drop in the Eastern Mediterranean (Watch), and a mild surge over Korea. |

To switch modes, edit `.env` and run `docker compose up -d`. To regenerate the demo world, set `DEMO_RESET=1` for one start. To wipe everything, run `docker compose down -v`.

Optional: set `ANTHROPIC_API_KEY` in `.env` to have Claude write the report assessments. Without a key, a built-in template writes them.

| URL | |
|---|---|
| http://localhost:5173 | Dashboard |
| http://localhost:8000/docs | API documentation (Swagger) |
| http://localhost:8000/api/health | Health check |

## What is in the app

- **Overview:** a one-line world status, all regions ranked by disruption index, the globe, and a detail panel. Select a region to see what drives its score, aircraft per hour over 48 hours against the usual range with a 6-hour projection, recent earthquakes, hours flagged by the anomaly model, and the satellites overhead right now.
- **Regions:** a sortable table with 24-hour change, a watchlist (stars, saved in your browser), side-by-side comparison of 2–3 regions, and CSV export.
- **Satellites:** every tracked spacecraft positioned live from its orbital elements. Search and filter by type; open one to see its ground track (last and next 90 minutes), orbital parameters and TLE.
- **Events:** an earthquake map and list with region, time and magnitude filters, plus the anomaly log. Both export to CSV.
- **Reports:** "What changed" compares a region's last 6, 24 or 72 hours with the period before. Reports are saved and can be downloaded as Markdown or printed to PDF.
- **System:** status of each data source, a "Run ingest now" button, and stored totals.
- **Everywhere:** Ctrl+K (or /) search, an alerts menu for critical regions, big earthquakes, strong anomalies and stale data, and keyboard-operable controls. The layout works down to phone width.

## How the scores work

**Disruption index (0–100)** = 0.40 × air traffic + 0.35 × earthquakes + 0.25 × storm.

- **Air traffic:** distinct aircraft per hour over the last 3 complete hours, compared with the same hours of day across the previous 7 days. Both surges and drops count, since a drop is what an airspace closure looks like. The z-score is mapped so |z| ≤ 1 scores 0 and |z| ≥ 4 scores 100. Hours when ingestion was down are treated as missing, not as zero traffic.
- **Earthquakes:** magnitude-weighted points over the last 24 hours, fading with a 12-hour time constant. Half of the region's usual daily level is subtracted so quake-prone zones are not permanently flagged.
- **Storm:** the latest storm index (wind, gusts and rain) at the region centre.
- **Bands:** Calm < 20 ≤ Watch < 40 ≤ Elevated < 70 ≤ Critical. These are tunable in `.env`.

**Anomaly model.** Each hour of each region is a vector [aircraft per hour, storm index, event count].

- **Z-score part:** each feature is compared with the region's history older than 24 hours.
- **Isolation Forest part:** a model trained on that history scores how easy the hour is to isolate.
- **Composite:** composite = 0.5 × z part + 0.5 × forest part. Hours scoring ≥ 50, with |z| ≥ 2 or a strong forest score, are stored.
- **Weather first:** a traffic drop during a storm is labelled weather-explained.

**Satellites.** TLEs come from Celestrak and are propagated with SGP4, then rotated by Greenwich sidereal time to ground positions. A test checks the result against Skyfield.

## Architecture

```
 adsb.lol  Celestrak  Open-Meteo  USGS          (live mode, every 10 min)
      \        |          |        /
       app/data/live_connectors.py ──► PostGIS (observations, events)
                                            │
          app/services/series.py  hourly per-region series (cached 45 s)
            ├─ services/disruption.py  disruption index + explanation
            ├─ ml/anomaly.py           z-score + Isolation Forest ─► anomaly_scores
            ├─ services/reports.py     what-changed reports ─► what_changed_reports
            └─ services/satellites.py  live SGP4 positions
                                            │
                   FastAPI  /api/*  (backend container, :8000)
                                            │
         nginx ─► React + d3-geo canvas globe  (frontend container, :5173)
```

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | Headline numbers |
| `GET /api/regions` | All regions with scores, components, explanation, sparkline |
| `GET /api/regions/{id}` · `/history` · `/overhead` · `/forecast` | Region detail, hourly history with usual range, satellites overhead, 6 h projection |
| `GET /api/regions/outline` | Region boundaries |
| `GET /api/flights/live` | Latest position of each aircraft |
| `GET /api/satellites/live` · `/categories` · `/{norad}` | Live positions, type counts, orbit and ground track |
| `GET /api/events` | Earthquakes (`region_id`, `days`, `min_magnitude`) |
| `GET /api/anomalies` | Flagged hours |
| `GET /api/alerts` | Current alerts |
| `POST /api/reports` · `GET /api/reports` · `GET/DELETE /api/reports/{id}` | Saved What-changed reports |
| `GET /api/what-changed/{region_id}?hours=` | Same comparison without saving |
| `GET /api/search?q=` | Regions and satellites by name or NORAD ID |
| `GET /api/system/health` · `POST /api/ingest/live` | Source health, trigger a cycle |

## Develop without Docker

```bash
# database: any PostgreSQL 16 with PostGIS
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:password@localhost:5432/skynexus DATA_MODE=demo
./entrypoint.sh                      # migrate, seed, (demo data), start API on :8000

cd ../frontend
npm install && npm run dev           # http://localhost:5173, proxies /api to :8000
```

Tests: `docker compose exec backend python -m pytest -q`. That runs 21 tests covering orbits, scoring, the anomaly engine, the explainer, and API integration.

## Project layout

```
backend/
  app/api/            HTTP routes
  app/services/       series, disruption, reports, satellites, orbits, geo, ingest, ai_explainer
  app/ml/anomaly.py   z-score + Isolation Forest engine
  app/data/           live connectors, demo world generator, region and airport seeds
  app/models/         SQLAlchemy + GeoAlchemy2 tables
  alembic/            migrations
  tests/
  entrypoint.sh       wait for DB, migrate, seed, start
frontend/
  src/pages/          Overview, Regions, Satellites, Events, Reports, System
  src/globe/          canvas globe and flat map (d3-geo)
  src/components/     region panel, traffic chart, UI primitives
  src/lib/            API client, polling, routing, watchlist store, formatting
  nginx.conf          serves the build, proxies /api
docs/DEMO_SCRIPT.md   4-minute walkthrough
```

## Limitations

- **Live air-traffic history:** air-traffic scores need about a day of live history, and a full week for a reliable hour-of-day baseline.
- **ADS-B coverage:** adsb.lol coverage depends on volunteer receivers, so oceanic regions see fewer aircraft.
- **Earthquakes only:** events are USGS earthquakes inside monitored regions. GDELT was dropped because it blocks many datacenter IPs.
- **Region shapes:** regions are simple latitude/longitude boxes and some overlap. A point belongs to the smallest box containing it.
- **Short-term projection:** the projection is a linear trend on the last 12 hours, intended as a simple illustration rather than a forecast model.
