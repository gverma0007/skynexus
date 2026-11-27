# Public historical replay and evaluation

The eight historical studies use public archives without API keys or external accounts. They are separate from the six synthetic cases and the live-source viewer. Downloads preserve original response bytes, source URLs, retrieval timestamps and SHA-256 fingerprints. Parsed observations, labels and evaluation outputs are exportable together with a checksum manifest.

| Study | Public measurements | Native replay interval | Interpretation |
| --- | --- | --- | --- |
| Suez 2021 | [IMF PortWatch](https://portwatch.imf.org/pages/chokepoints) daily Suez transit counts and estimated transit capacity | 24 hours | AIS-derived aggregate activity; not individual ship trajectories. Capacity retains provider units. |
| Hurricane Ian 2022 | [NOAA ISD](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database), Fort Myers Page Field station 72210612835 | 1 hour | Wind, sea-level pressure and reported one-hour precipitation; not outage or damage measurements. |
| Canadian smoke 2023 | [EPA AirData](https://aqs.epa.gov/aqsweb/airdata/download_files.html), hourly parameter 88502 | 1 hour | One NYC monitor/POC chosen by pre-June coverage and held fixed. Non-reference/equivalent research measurements, not a regulatory compliance assessment. |
| Tonga 2022 | [USGS event catalogue](https://earthquake.usgs.gov/fdsnws/event/1/), bounded region and M≥4 | 6 hours | Earthquakes and volcanic events remain separate. Seismic context does not measure cable failure or connectivity. |
| Pakistan floods 2022 | NOAA ISD, Nawabshah station 41749099999 | 3 hours | Reported three-hour precipitation, wind and pressure. Station weather does not identify inundation extent or transport closure. |
| FAA ground stop 2023 | [BTS monthly flight archive](https://transtats.bts.gov/PREZIP/), January 2023 | 1 hour | JFK/LGA/EWR/BOS scheduled departures, cancellation share and mean departure delay. Local January boundaries and scheduled times are converted from America/New_York to UTC. |
| NYC taxi passenger demand | [NAB realKnownCause](https://github.com/numenta/NAB/tree/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/data/realKnownCause), originating from NYC TLC | 30 minutes | Counts are passengers, not trips. Five published anomaly windows allow several chronological events to be tested. |
| Machine temperature | Same pinned NAB realKnownCause archive | 5 minutes | Real industrial equipment telemetry. Missing or ambiguous duplicate native timestamps become null slots, not interpolated observations. The equipment archive contains a one-hour clock reversal; both readings at its 12 duplicated timestamps are excluded, retaining original bytes. |

NAB input data, published anomaly windows and the license notice are pinned to commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`. The license notice is included in NAB evaluation exports. Its timestamps lack explicit timezone metadata; the UTC-formatted replay clock is a nominal axis, not a verified timezone conversion.

The saved measured results are in [HISTORICAL_RESULTS.md](HISTORICAL_RESULTS.md), with full metadata in [HISTORICAL_RESULTS.json](HISTORICAL_RESULTS.json).

## Run and replay

Use **Enter demo** on the landing/login page, then **Historical replay**. Choose a historical case, download it if necessary, and scrub or step through its actual timestamps. Each channel retains its own units, coverage and gaps. Labels remain hidden until requested. Cached studies remain replayable without contacting their providers.

For a new installation, download and evaluate everything from the CLI:

```bash
docker compose exec backend python -u -m app.historical_cli download --all
docker compose exec backend python -u -m app.historical_cli evaluate --all
```

Or use `--case suez-2021`, `ian-2022`, `canada-smoke-2023`, `tonga-2022`, `pakistan-floods-2022`, `faa-notam-2023`, `nab-nyc-taxi` or `nab-machine-temperature`. `download --refresh` reprocesses the cached source bytes into a fresh snapshot; it does not silently replace pinned inputs with a newer revision. Raw files and parsed snapshots use the configured archive storage, shared by the local Docker services.

The EPA annual archive and BTS monthly archive are larger than the parsed study windows. Partial or failed downloads do not become replayable cases. The source directory, case API and data fingerprints distinguish available data from download requirements.

## What the evaluation measures

The six named event cases use documented event intervals as **proxy labels**. For FAA, the interval is 11:30–14:00 UTC on 11 January 2023. A bucket is positive if it overlaps the interval. These labels allow an event-window association test; they do not establish every labelled measurement as an operational anomaly. Their training and calibration segments precede the event, with the event and recovery reserved for testing.

NAB cases use separately published anomaly windows. Their chronological split is 60% training, 20% calibration and 20% testing. These are buffered benchmark annotations, not exact physical-failure onset times. Results here are SkyNexus metrics, not the official NAB score.

- Detection compares seasonal Z-score, Isolation Forest and quality-aware fusion. It reports sample precision, recall and F1, false-alert samples, event-window recall and detection delay. Normal training selection uses only supplied training labels. IF score thresholds use normal calibration observations. Missing primary-channel samples are excluded from scoring and counted separately.
- Numeric forecasting compares persistence, seasonal and recursive quantile gradient boosting models. It reports MAE/RMSE at native-step, three-hour and six-hour horizons where the cadence allows them, plus measured interval coverage. Crossed quantile bounds are expanded to include all three fitted quantiles. Daily data receives a daily horizon, not an invented hourly resolution. At most 96 uniformly selected heldout origins bound the workload; inference batches those origins at each horizon, and Docker caps native math-library threads at one; forecasts recursively use their own predicted values rather than future actuals.
- Advance warning predicts the onset of an annotated window within the next six hours, rounded up to a native step. Inputs use only earlier measurements. Currently labelled windows are excluded from onset-warning metrics so continuing an existing disturbance does not count as advance prediction. The final horizon of both training and calibration is purged to prevent targets crossing split boundaries.
- A logistic model fits training data, a separate logistic calibrator fits calibration outcomes, and the alert threshold is selected from calibration probability quantiles. Test outcomes do not choose the threshold. Outputs include Brier score against a training-prevalence baseline, Brier skill, precision/recall, event warning recall, false-warning hours, reliability bins and positive lead times before annotated onsets.

A single event with normal-only pre-event data cannot train and calibrate a warning classifier; the application reports insufficient labels. BTS delay/cancellation outcomes were released later and grouped by scheduled departure hour, so their warning assessment explicitly reports unsupported original availability. Numerical BTS backtests are retrospective outcome tests.

Historical results assess these experimental series models; they do not validate the legacy live regional composite score or infer geopolitical intent.

False-alert counts are sample counts, not independent incident counts. Event counts are small and performance is a retrospective point estimate, not proof of generalization. A model may fail to improve on simple baselines or warn any heldout event; those outcomes remain visible. Revised archives and unknown original publication times prevent claiming validated live warning capability from these results alone.

## API and artifacts

- `GET /api/cases`: availability, native cadence, attribution and limitations.
- `POST /api/cases/{id}/download`: bounded downloads from fixed public-source adapters; no arbitrary URL ingestion.
- `GET /api/cases/{id}/data`: real channels, timestamp grid, nulls, labels and matching cached evaluation.
- `POST /api/cases/{id}/evaluate`: evaluated metrics and a session-private ZIP.

The ZIP includes the complete processed observations/labels, evaluation, readable `report.md` and manifest, including dataset and method fingerprints, software versions and model parameters. Raw source bytes are additionally archived by the collector. ZIP access remains scoped to its authenticated session, including sessions created through direct demo entry.

`DEMO_DIRECT_LOGIN=true` enables the requested password-free demo entry while retaining revocable HttpOnly sessions and origin/rate checks. Local Compose enables it. The application default is false for deployments without an explicit flag; set it false to require provisioned password login.
