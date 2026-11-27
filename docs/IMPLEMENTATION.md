# SkyNexus research workspace

## Run locally

1. Copy `.env.example` to `.env` and retain your database port override if needed.
2. Local Compose enables **Enter demo** through `DEMO_DIRECT_LOGIN=true`. To require password login, set it false and set `DEMO_EMAIL` and a generated Argon2 `DEMO_PASSWORD_HASH`. Generate the hash using `python -m app.provision_demo` inside an environment with backend dependencies installed. Keep the complete hash single-quoted in `.env` so Compose does not interpolate its dollar signs. No plaintext password belongs in source control.
3. Run `docker compose up -d --build`. The backend applies additive migrations and seeds region geometry. The ingestion and analysis services wait for its health check.
4. Open http://localhost:5173. Choose **Enter demo** or log in with the provisioned account.

The current development machine has a generated password in the private file `/tmp/skynexus-demo-credentials.txt`. This temporary file is not a deployment credential or a committed asset.

The API no longer starts collectors inside its lifespan. Independent collectors run with `python -m app.worker`; report jobs run with `rq worker research --url "$REDIS_URL"`. Never use scheduled unauthenticated HTTP calls to trigger ingestion.

## Connected versus available

Sources lists connector attempts, latest successful acquisition, configured credential names, errors and delivery semantics. A configured key does not prove a source has usable coverage. Actual network outcomes are required. Do not infer source observation freshness from browser connection health.

Implemented adapters cover OpenSky, modern CelesTrak CSV/OMM, Open-Meteo, USGS, NOAA Kp, MBTA service alerts, IODA, GDACS, GDELT, FIRMS, OpenAQ, EIA, Cloudflare Radar, Global Fishing Watch port visits, and native AISStream vessel messages. Free keys are needed for several of these. GFW is historical context. MBTA supplies service alerts and matched prediction/schedule estimates; the offline GTFS matcher supports attributed static and protobuf files.

Scientific GloFAS/imagery acquisition and local processing are separate. After downloading an authorized product and processing it with the local scientific CLI, run:

```
python -m app.import_observations product.jsonl --source glofas --domain environment
```

Each JSONL row requires `external_id`, timezone-aware `observed_at`, `payload` with `provenance_url`, and optional `kind` (`observed`, `forecast`, `derived`, `synthetic`, `context`). The scientific CLI supports explicit EWDS download requests and local GeoTIFF/NetCDF/GRIB processing. Remote acquisition still needs credentials/terms and a product request; local processing, static/realtime GTFS matching and local archiving need no accounts. R2 upload is optional.

## Research and reports

Reports preserve input metrics, method version, dataset mode, input hash, limitations and coverage. Export JSON, Markdown, CSV or PDF through `/api/reports/{id}/export?format=pdf`. Stored reports are scoped to the browser's authenticated session. A new session cannot view another session's report, even with the same demo login.

`POST /api/experiments` accepts `source`, `metric` and optional `entity`. It requires at least 96 complete hourly observations and evaluates a chronological 70/30 split. It compares persistence, seasonal-24-observation and quantile gradient boosting forecasts; reports MAE, RMSE and empirical interval coverage. Anomaly counts compare Z-score and Isolation Forest. No precision/recall or predictive lead-time is fabricated without independent labels. Separate entities cannot silently be averaged.

Normalized observations are archived after seven days; hourly normalized numeric features are retained for 180 days. Legacy flight/weather retention uses `RETENTION_DAYS`. Set `LIVE_INGEST=0` and recreate the ingestion service to disable external acquisition; demo mode also disables acquisition. The 14-day numeric-analysis gate is provisional and does not substitute for independently labelled validation. Eight real historical datasets can now be downloaded without keys, replayed and evaluated. See [HISTORICAL_DATA.md](HISTORICAL_DATA.md) for sources, native cadence and the distinction between six event-window proxy targets and two independently annotated benchmarks. Verified infrastructure dependencies and original historical publication/orbital vintages remain external research inputs; no real-world accuracy claim is inferred from the synthetic benchmark.

## Hosting

`render.yaml` describes paid always-on web, ingestion and report-worker services, managed PostgreSQL and Redis-compatible storage. The root Dockerfile serves the frontend and API from one origin. The entrypoint installs PostGIS/pgcrypto and applies migrations; the database identity must have extension privileges. Source keys belong on the ingestion service. Configure the demo password hash on the web service. Set `PUBLIC_ORIGIN` to the hosted origin and keep `COOKIE_SECURE=true`.

No cloud resources have been provisioned. Review Render's actual resource costs, connect the repository, configure secrets and verify a backup/restore procedure before deployment. The blueprint does not constitute a deployed site or a tested production backup.

## Verification

Run `docker compose exec backend python -m pytest -q` and `npm run build` in `frontend`. Tests include authentication, session isolation, report exports, source metadata, scientific-import validation and chronological evaluation. Live-source acceptance additionally requires the relevant account credentials and actual coverage; unit tests do not establish upstream availability.

Local verification: 85 backend tests passed (dependency deprecation warnings only); frontend production builds passed. Historical replay, password-free demo entry, native cadences, actual missing measurements and evaluation ZIP fingerprints were verified in the browser. Batched recursive forecasts preserve prior-only inputs; the equipment case cold evaluation completed in about 0.9 seconds with single-thread native math libraries. A 24 MB local database/artifact backup restored into a separate empty PostgreSQL database, all three archived artifact checksums matched, and a second restore correctly refused the nonempty target. The temporary verification database was removed. Browser verification also passed synthetic playback and missing-data gaps, metadata-only restrictions, benchmark creation, synthetic exposure inspection, report generation and benchmark/report ZIP downloads with matching SHA-256. Mobile content remained 390px wide at a 390px viewport. Tested reports honestly showed empty supporting-evidence arrays where no attributed measurements matched their window; populated rendering was not validated against a real matched report. Nginx now refreshes Docker DNS after backend container replacement. Provider credential values were never printed. IODA returned an upstream read timeout during acquisition; source health records this as an error.

## Completed local continuation

The local-first continuation now includes:

- GeoTIFF threshold/difference footprints, nodata handling, CRS conversion and bounded vectorization.
- Explicit NetCDF/GRIB variable/time/ensemble slicing and conversion into the same scientific pipeline.
- Attributed asset import and observation/forecast exposure intersections, with synthetic/live isolation.
- Keyless MBTA prediction/schedule matching and offline GTFS static + protobuf matching, including cancellations, skipped stops, service dates and after-midnight times. Delay estimates remain labelled predictions, not final observed arrivals.
- Persistent hourly aviation/weather projections plus 1–24-hour numeric forecasts with rolling-origin, horizon-specific baseline comparisons and interval coverage.
- Six reproducible labelled **synthetic** scenarios with detector ablations and outage-quality tests. Eight additional public historical studies now contain real archived measurements after download, with separate historical evaluation and explicit label provenance.
- A separate independent-label validation CLI with chronological training/calibration/test partitions, Brier scores, reliability bins and advance-warning lead-time accounting.
- Session-private report/experiment ZIPs, deterministic checksum manifests, local archives, optional private R2 storage and archive-before-delete retention for both normalized observations and live flight/weather/orbit rows. Synthetic fixtures are preserved; failed storage writes prevent deletion. Hourly aggregates stop recomputing when their raw hour reaches the retention boundary. Cleanup processes bounded batches every five minutes.
- Readable report sections for complete-hour pattern counts, missing observations, reference-band departures, source provenance, exposure candidates and alternative explanations. Reference bands are descriptive and explicitly separate from heldout model evaluation.
- Strict session ownership for report lists and exports, synthetic/live observation isolation, cold-start anomaly gating, and weather-coincident labels that preserve measured disturbance severity.
- Local database/artifact backup, complete checksum verification and non-destructive restore into an empty target.

Exact configuration and provider acquisition links: [CONFIGURATION.md](CONFIGURATION.md).

### Scientific processing

For a local GeoTIFF (threshold units must match the product):

```
python -m app.scientific_cli process product.tif --source earth-observation --observed-at 2026-01-01T12:00:00Z --provenance-url https://provider.example/product --threshold 0.5 --output footprint.jsonl
python -m app.import_observations footprint.jsonl --source earth-observation --domain environment
```

NetCDF/GRIB additionally requires `--variable discharge --selection '{"time":0,"number":0,"step":0}'` using the actual dimension names in the file. Unselected nonspatial dimensions are rejected. Forecast products require `--kind forecast --published-at <issue-time>` and `--observed-at <valid-time>`. Do not infer a flood boundary from river-discharge grid cells: these are thresholded model grid cells unless a proper inundation product is supplied.

Nighttime-light changes use `--baseline before.tif --percent --comparison lte --threshold -25`. Supply product quality/cloud masking as nodata. A light decline alone does not prove a power outage. Original inputs are content-addressed in archive storage before import.

For an authorized EWDS request, first download a cropped product with `python -m app.scientific_cli download --dataset cems-glofas-forecast --request request.json --output product.grib`. This command needs EWDS credentials and accepted terms; local processing does not.

### Assets, transit and validation

```
python -m app.assets_cli assets.geojson
python -m app.transit_cli --schedule gtfs.zip --feed updates.pb --service-date 20260101 --provenance-url https://agency.example/feed
python -m app.validate_dataset independently-labelled.json --output evaluation.zip
```

Asset files are GeoJSON FeatureCollections. Each feature requires an id, WGS84 geometry, and properties `name`, `provenance_url`, optional `asset_type`, `available_at` and `dataset_mode` (`live`/`synthetic`). The worker also obtains attributed study-area airport geometry directly from OurAirports without a key.

Labelled validation input requires `dataset_mode`, `provenance_url`, `labels_provenance_url`, optional `horizon_hours` (1–24), and 240–10000 consecutive hourly `series` entries with `time`, numeric `value`, boolean `label`, optional boolean `quality`. Labels must be independently supplied; the tool does not manufacture historical labels. Advance-warning calibration needs both outcomes in training and calibration windows; otherwise it explicitly reports insufficient labels.

### Backup and restore

```
docker compose exec backend python -m app.backup create /app/backups/research.zip
docker compose exec backend python -m app.backup verify /app/backups/research.zip
```

Backups include database content and local artifacts, with a manifest and SHA-256 checksums. They are private files with mode 0600, stored in the ignored local `backups/` directory. R2 buckets need their own object-storage backup procedure.

Restore requires an empty target database and empty artifact directory. Set its connection string in `RESTORE_DATABASE_URL` and run `python -m app.backup restore research.zip --artifacts-dir restored-artifacts`. The implementation never drops/reinstalls a live database. The Docker images include PostgreSQL 16 client tools matching the local database version.

Remaining external inputs are credentials/permissions for protected acquisition, additional independently reviewed operational-impact labels, original publication vintages and hosting configuration. Synthetic benchmarks are a functional demo and methodology test, not evidence of real-world prediction accuracy.


## Earth window controls

Dashboard and Explore keep the same globe mounted across normal, minimised and maximised sizes. Maximise uses a native modal dialog for keyboard focus containment and an inert background. Escape restores the dashboard size and trigger focus; minimising pauses canvas drawing by hiding its container. The current map style, camera and layer selections remain in component state. Mobile controls fit 320px and 390px layouts. Verified desktop/mobile resize cycles, retained canvas identity and Line view, collapsed spacing, modal focus, body-scroll restoration and successful frontend production builds.
