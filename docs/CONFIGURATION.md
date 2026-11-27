# Exact credential configuration

No provider keys or external accounts are required for direct demo entry, eight public historical studies and their evaluations, local login, the six-case synthetic benchmark, local scientific-file processing, GTFS file matching, asset imports/exposures, forecast evaluation, report ZIPs, or database/artifact backup and restore.

Keep secrets in the root `.env` file, which is ignored by Git. Never use `VITE_` variables for provider credentials. After editing local credentials, run `docker compose up -d --force-recreate backend ingestion analysis`. For a hosted deployment use service environment variables, not a committed file.

Public historical sources need none of the credentials below. See [HISTORICAL_DATA.md](HISTORICAL_DATA.md) for datasets, replay and measured evaluation boundaries.

## Provider acquisition credentials

| Environment variable | Enables | Where to obtain it | Notes |
| --- | --- | --- | --- |
| `AISSTREAM_API_KEY` | Native live vessel WebSocket | [AISStream account/documentation](https://aisstream.io/documentation) | Backend subscription only; no browser connection or key exposure. |
| `FIRMS_MAP_KEY` | NASA active-fire acquisition | [Request a free FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | Configure the MAP_KEY itself; do not paste a full URL. |
| `OPENAQ_API_KEY` | Ground air-quality measurements | [OpenAQ Explorer](https://explore.openaq.org/) → account settings | Sent as `X-API-Key`. [Official quick start](https://docs.openaq.org/using-the-api/quick-start). |
| `EIA_API_KEY` | Electricity demand/generation observations | [EIA API registration](https://www.eia.gov/opendata/register.php) | Enables the configured ISO New England series. |
| `CLOUDFLARE_API_TOKEN` | Radar connectivity/outage acquisition | [Radar API setup](https://developers.cloudflare.com/radar/get-started/first-request/) | Custom token: **Account → Radar → Read**. This is not an R2 access key. |
| `GFW_API_TOKEN` | Historical maritime/port events | [Global Fishing Watch API authentication](https://globalfishingwatch.org/our-apis/documentation/docs/authentication) | Personal bearer access token; dataset permissions and publication delays still apply. |
| `EWDS_API_TOKEN` | Authorized Copernicus GloFAS downloads | [EWDS API setup](https://ewds.climate.copernicus.eu/how-to-api) | Personal access token; manually accept dataset terms and supply an explicit study-area request JSON. The key alone does not choose a scientific product. |

For local Docker, these values are read from `.env`. On Render, acquisition credentials belong on **skynexus-ingestion**. Put `EWDS_API_TOKEN` on whichever processing service executes the explicit download command, normally **skynexus-analysis**. The Sources screen reads the collector's persisted configured state without receiving the secrets.

## Optional credentials

| Variable(s) | Purpose | Required? |
| --- | --- | --- |
| `OPENSKY_CLIENT_ID` + `OPENSKY_CLIENT_SECRET` | OAuth client-credentials access and a larger flight-data allowance; create an API client in your [OpenSky account](https://openskynetwork.github.io/opensky-api/rest.html). | No; anonymous acquisition uses a slower cadence. Both values are needed together. Legacy username/password are not required. |
| `MBTA_API_KEY` | Increased MBTA request allowance; obtain from the [MBTA V3 developer portal](https://api-v3.mbta.com/). | No; bounded keyless predictions/schedule matching works. |
| `ANTHROPIC_API_KEY` + a valid `ANTHROPIC_MODEL` | Optional AI narrative. | No; deterministic reports and all research features work without AI. Configure only on the web/report-processing services if desired. |

Open-Meteo, USGS, GDACS, GDELT, NOAA space weather, IODA, CelesTrak and OurAirports do not require keys in the implemented connectors. Availability, coverage and upstream errors remain visible; keyless does not mean unlimited or guaranteed service.

## Optional remote archive storage

Default `ARCHIVE_STORAGE=local` works without accounts. Docker shares a persistent `research_artifacts` volume between the services.

For private Cloudflare R2/S3-compatible storage configure **all** of:

```
ARCHIVE_STORAGE=r2
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
```

Create a private bucket and bucket-scoped Object Read & Write credentials using the [official R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/). The endpoint is the S3 API endpoint, not the public `r2.dev` URL. No generic Cloudflare API token can replace the S3 access-key pair. Configure these values on web, ingestion and analysis services so reports, raw archives and downloads share the same storage. Remote archiving/upload is opt-in; local mode never contacts R2.

Render services do not share local disks. Before enabling persistent hosted archives, choose shared R2/S3 storage or an equivalent supported shared-storage arrangement. The checked-in blueprint does not create an object bucket or incur purchases by itself.

## Application configuration, not provider API keys

- `DEMO_DIRECT_LOGIN=true`: enables the requested **Enter demo** button and public demo sessions. Local Compose enables this; set false to require password login.
- `DEMO_EMAIL` and `DEMO_PASSWORD_HASH`: provisioned password login. Generate the hash using `python -m app.provision_demo`. Keep Argon2's dollar signs intact (single-quote the value in `.env`). No email-delivery service is used.
- `DATABASE_URL` and `REDIS_URL`: connection strings; Docker supplies internal defaults and Render supplies managed-resource references.
- `PUBLIC_ORIGIN`: exact browser origin, e.g. `https://your-app.onrender.com`.
- `COOKIE_SECURE=true` for hosted HTTPS; local Docker overrides it to false.
- `ARTIFACT_DIR=artifacts` in local mode; Docker mounts it at `/app/artifacts`.

Check credential presence without exposing values:

```
docker compose exec ingestion python -m app.check_config
```

`configured` means a value exists; successful provider acquisition still must be verified on Sources. Do not paste secrets into chat or screenshots.
