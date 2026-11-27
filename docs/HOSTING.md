# SkyNexus free hosting

Updated 27 November 2026. Selected layout: one sleeping **Render Free** web service and **Neon Free** PostgreSQL/PostGIS in Singapore. The root Dockerfile serves React and FastAPI together on one HTTPS origin. Deployment status and the public URL are recorded after acceptance below.

## Free profile

`HOSTING_PROFILE=free_demo` enables the bounded public research demo:

- Eight real historical cases, their native-cadence replay, and cached chronological anomaly/forecast/advance-warning evaluations.
- Six separately labelled synthetic fixtures and a cached synthetic benchmark.
- Direct demo entry, optional provisioned password login, the full interface and all globe/window controls.
- Session-private evidence ZIPs stored in PostgreSQL, with checksums, deduplication, an 8 MiB object limit and a 64 MiB total byte limit. Quota checks are serialized in the database. Old objects with no active owning session are eligible for cleanup after eight hours when another export is written.
- One export at a time per API process; unsupported queued jobs, new archive downloads and observed-series model fitting return an explicit availability response.
- Polling and SSE stop when a tab is hidden or idle. Continuous event subscriptions and source collection are disabled in the sleeping profile. Sessions and exports survive application restarts.

The checked-in `backend/app/data/hosted` release contains only attributed public datasets, cached evaluations, license material and generated fixtures. Its manifest is verified at startup, and each historical case verifies its own canonical hash. It is rebuilt offline with `python -m app.prepare_hosted_data`; large raw upstream archives are not downloaded by visitors.

Small exports use the existing Neon database so this first deployment needs **no object-storage key, Redis account or background worker**. `ARCHIVE_STORAGE=local` and `r2` remain available to full local/always-on deployments. Public cached studies are not live acquisition; event-window proxy labels and retrospective warning limitations remain visible in the interface and exports.

## Accounts and cost

Target: **$0 within free allowances**, using the supplied Render subdomain and TLS. Neon was provisioned through the existing Vercel Marketplace integration on its explicit `free_v3` plan; a Vercel-managed Neon organization cannot create projects directly through the Neon project API.

[Render Free](https://render.com/docs/free) sleeps after 15 minutes without inbound traffic, wakes on a subsequent request, and loses local file changes on sleep/restart. Its free Postgres expires after 30 days, so this deployment uses Neon instead. Render's free compute is [512 MB RAM and 0.1 CPU](https://render.com/docs/compute-plans). [Neon Free](https://neon.com/pricing) currently includes 1 GB DB storage and 100 CU-hours per project/month. Quotas and availability can change; confirm the account's current plan and controls before adding services.

No always-on acquisition, unattended alerts or background report execution is claimed while the app sleeps. Do not add keep-alive pings. Use the full Docker stack for live-stream presentations and scientific-file/model experiments. Optional paid upgrades are documented in [HOSTING_ALWAYS_ON.md](HOSTING_ALWAYS_ON.md).

## Configuration

| Variable | Hosted setting |
| --- | --- |
| `DATABASE_URL` | Neon pooled TLS runtime URL; stored only in Render environment settings. |
| Direct database URL | Used from a protected operator environment for migrations and backups; never committed. |
| `HOSTING_PROFILE` | `free_demo` |
| `STARTUP_PREPARE` | `false` after one-time preparation. Cold starts launch Uvicorn directly. |
| `ARCHIVE_STORAGE` | `database` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `2` / `1` |
| `ENV` / `DATA_MODE` / `LIVE_INGEST` | `production` / `live` / `0` |
| `PUBLIC_ORIGIN` | Exact public Render HTTPS origin. |
| `COOKIE_SECURE` / `DEMO_DIRECT_LOGIN` | `true` / `true` |
| `DEMO_EMAIL` / `DEMO_PASSWORD_HASH` | Optional existing provisioned demo credentials; keep the hash private. |
| `ARCHIVE_MAX_BYTES` / `ARCHIVE_MAX_OBJECT_BYTES` | Defaults: 67108864 / 8388608. |

Historical replay and cached evaluations require no aviation, weather, maritime or AI provider keys. The browser never receives DB credentials. Preserve `.env` and `.env.*` exclusions and use Render's secret environment settings.

`render.free.yaml` describes the single-service layout. The older `render.yaml` is the optional paid multi-service layout; do not use it for the free release.

## Release procedure

1. Run the backend tests against an isolated PostGIS database and build the frontend. GitHub Actions performs both on pushes and pull requests.
2. Verify the packaged data manifest and build the root Docker image. Smoke-test the image at the free CPU/RAM budget, including the largest case and evidence exports.
3. Prepare a new demo DB with the **direct** connection and `python -m app.prepare_database` from `backend`. This enables PostGIS/pgcrypto, migrates and seeds only attributed reference data. It does not copy local sessions, private files or live-looking synthetic observations.
4. Deploy the pinned GitHub branch/commit to one Render Free Docker web service. Set the runtime environment above. Keep startup preparation disabled after the controlled migration succeeds.
5. Check `/api/health` for process liveness and `/api/ready` for the required DB tables. Use `/api/health` for regular host probes so probes do not keep the database awake unnecessarily.
6. Verify HTTPS, secure login cookies, all eight cases/evaluations, session-owned downloads, anonymous rejection and Earth controls. Restart the service and re-download a previously created export with the same session cookie.
7. Close test clients, allow natural sleep and reopen the app. Record actual wake-up behavior and quota use. Do not claim a measured natural sleep test based only on a forced restart.

## Backup and recovery

The root deployment image includes PostgreSQL 18 client tools to match the provisioned Neon PostgreSQL 18 database. The local backend image retains the PostgreSQL 16 client by default for its local database.

`python -m app.backup create PATH.zip` supports `ARCHIVE_STORAGE=database`: the DB dump includes export bytes and ownership metadata. Local mode also copies local artifact files; remote R2 mode still needs a separate bucket backup. Backups contain private sessions and must remain outside Git, with file permissions restricted and copies protected independently of the hosted project.

Verify with `python -m app.backup verify PATH.zip`. Restore only into a fresh empty database with a compatible PostgreSQL client/server version, using `RESTORE_DATABASE_URL` and `python -m app.backup restore PATH.zip --artifacts-dir EMPTY_DIR`. The CLI refuses to overwrite an existing application database. Check migration revision, record counts, login and export checksums after restoration.

Free hosted compute has no unattended backup worker. Take an independent backup before migrations and presentations; automate off-host backups separately if the demo becomes a maintained service. Neon instant-restore history is not an independent backup.

## Acceptance record

- Fresh PostgreSQL 16/PostGIS migrations passed; Neon PostgreSQL 18 preparation passed.
- Backend: 88 tests passed; frontend production build passed.
- Constrained-image, hosted deployment and restart verification: recorded after completion.
- Natural sleep/wake: requires a full idle interval and is recorded separately from restart checks.
