# SkyNexus

SkyNexus is an academic workspace for observing regional disturbances across aviation, maritime activity, public transit, weather, environmental hazards, energy and connectivity. It preserves source provenance, separates simulated and live evidence, compares activity with historical baselines, and produces reproducible investigation reports.

Statistical anomalies and spatial exposure indicate candidates for investigation. They do not establish cause, damage, closures or conflict. Synthetic benchmark results do not establish real-world prediction accuracy.

## Run locally

Docker Engine with Compose v2 is required.

1. Copy `.env.example` to `.env` if it does not already exist. Local Compose enables **Enter demo** without a password. For restricted access set `DEMO_DIRECT_LOGIN=false`, configure `DEMO_EMAIL` and an Argon2 `DEMO_PASSWORD_HASH`; `python -m app.provision_demo` generates a hash interactively in an environment with backend dependencies. Keep the complete hash single-quoted in `.env`.
2. Run `docker compose up -d --build`.
3. Open [SkyNexus](http://localhost:5173) and select **Enter demo**, or use the provisioned credentials.

The backend applies migrations and seeds study regions and explicitly synthetic fixtures. Independent ingestion and analysis workers run alongside PostgreSQL/PostGIS and Redis. `DB_PORT`, `API_PORT` and `WEB_PORT` can override host ports. Keep secrets and backups out of source control.

`DATA_MODE=live` collects available real feeds. The workspace also offers an isolated synthetic viewer and repeatable cases. Live baselines and numeric forecasts require sufficient continuous history; insufficient or stale data is reported explicitly.

## Workspace

- Public landing page, provisioned login, responsive sidebar shell and keyboard search.
- Earth-texture, line, dot and flat-map views, region inspection and orbit propagation. The Earth window minimises into a compact card or maximises with Escape-to-restore, preserving the current view.
- Realtime/pause controls and server-sent observation updates. Native vessel streaming requires an AISStream key; HTTP providers update at their supported polling cadence.
- Sources with collector state, credential requirements, acquisition errors, freshness and coverage.
- Domain signals, 1–24 hour numeric forecasts, horizon-specific baseline comparisons and empirical interval coverage.
- Incidents and exposure inspection with attributed hazard/asset intersections and explicit uncertainty.
- Eight replayable real historical studies with native timestamps, public-source downloads, heldout evaluation and private ZIPs; six labelled synthetic scenarios remain separate.
- Reproducible synthetic detector ablations, chronological experiments and checksum archives.
- Session-private reports with evidence snapshots, alternative explanations, pattern analysis and JSON/Markdown/CSV/PDF/ZIP exports.

## Account-free tools

GeoTIFF threshold/difference footprints, explicit NetCDF/GRIB slices, local asset imports, static/realtime GTFS matching, independent-label evaluation, local artifact storage and verified database/artifact backup/restore work without provider accounts. Scientific inputs must supply attribution, correct units, quality masks and publication/valid times. See [historical sources and evaluation methodology](docs/HISTORICAL_DATA.md) for real case acquisition, event-window proxy labels and independently published benchmark annotations.

See [implementation and CLI examples](docs/IMPLEMENTATION.md) and [exact credential configuration](docs/CONFIGURATION.md). Protected acquisition needs credentials and dataset permissions. Keyless feeds remain subject to coverage, limits and upstream availability.

Measured historical detection, forecast and warning results are recorded in [HISTORICAL_RESULTS.md](docs/HISTORICAL_RESULTS.md).

## Verify

```bash
docker compose exec backend python -m pytest -q
docker compose exec ingestion python -m app.check_config
cd frontend
npm run build
```

Tests cover authentication and session isolation, temporal boundaries, scoring, scientific formats, transit schedule matching, forecast evaluation, exposure isolation and archive integrity. They do not prove live provider availability or real-world forecast accuracy.

## Architecture and deployment

See the [complete hosting plan](docs/HOSTING.md) for service sizing, cost estimates, required blueprint changes, environment settings, deployment order, backups, monitoring and rollback.

FastAPI exposes authenticated APIs and event delivery; React/Vite renders the workspace. PostgreSQL/PostGIS stores observations, features, reports and sessions. A supervised ingestion process collects sources and projects hourly features; Redis streams deliver updates and an RQ worker handles queued reports. Raw evidence and exports use content-addressed local storage or optional private S3-compatible storage.

`render.yaml` supplies an always-on deployment blueprint; no cloud resources are provisioned automatically. Hosted services need configured secrets, origin/secure-cookie settings, managed database/Redis and shared archive storage. Local Docker uses a persistent shared artifact volume. Review hosting costs and the configuration guide before deploying. Scheduled anonymous ingestion pings are disabled.
