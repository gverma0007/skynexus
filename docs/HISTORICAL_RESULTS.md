# Historical evaluation results

Generated: 2026-11-26T23:54:45.484846+00:00. Method: `historical-chronological-v3`.

These are measured retrospective results from eight downloaded public archives. Six cases use documented event-window proxy labels; two use published NAB annotations. Proxy labels do not verify operational impact. Sample recall and detecting some part of an event window measure different outcomes. Undefined metrics remain blank rather than becoming zero.

Complete parameters, source fingerprints and software versions are in [HISTORICAL_RESULTS.json](HISTORICAL_RESULTS.json). Data acquisition and interpretation are documented in [HISTORICAL_DATA.md](HISTORICAL_DATA.md).

## Anomaly detection

| Case | Method | Precision | Sample recall | F1 | False samples | Event recall | Delay (h) |
|---|---|---:|---:|---:|---:|---:|---:|
| suez-2021 | seasonal_z_score | 0.4545 | 0.7143 | 0.5556 | 6 | 1.0000 | 24.0000 |
| suez-2021 | isolation_forest | 0.3889 | 1.0000 | 0.5600 | 11 | 1.0000 | 0.0000 |
| suez-2021 | quality_aware_fusion | 0.4286 | 0.8571 | 0.5714 | 8 | 1.0000 | 24.0000 |
| ian-2022 | seasonal_z_score | 1.0000 | 0.1613 | 0.2778 | 0 | 1.0000 | 1.0000 |
| ian-2022 | isolation_forest | 1.0000 | 0.3548 | 0.5238 | 0 | 1.0000 | 0.0000 |
| ian-2022 | quality_aware_fusion | 0.9231 | 0.3871 | 0.5455 | 1 | 1.0000 | 1.0000 |
| canada-smoke-2023 | seasonal_z_score | 0.6032 | 0.7917 | 0.6847 | 50 | 1.0000 | 1.0000 |
| canada-smoke-2023 | isolation_forest | 0.7009 | 0.7812 | 0.7389 | 32 | 1.0000 | 1.0000 |
| canada-smoke-2023 | quality_aware_fusion | 0.6032 | 0.7917 | 0.6847 | 50 | 1.0000 | 1.0000 |
| tonga-2022 | seasonal_z_score | 0.6552 | 0.5938 | 0.6230 | 10 | 1.0000 | 0.0000 |
| tonga-2022 | isolation_forest | 0.6552 | 0.5938 | 0.6230 | 10 | 1.0000 | 0.0000 |
| tonga-2022 | quality_aware_fusion | 0.6552 | 0.5938 | 0.6230 | 10 | 1.0000 | 0.0000 |
| pakistan-floods-2022 | seasonal_z_score | 1.0000 | 0.1471 | 0.2564 | 0 | 1.0000 | 39.0000 |
| pakistan-floods-2022 | isolation_forest | 1.0000 | 0.0588 | 0.1111 | 0 | 1.0000 | 102.0000 |
| pakistan-floods-2022 | quality_aware_fusion | 1.0000 | 0.1471 | 0.2564 | 0 | 1.0000 | 39.0000 |
| faa-notam-2023 | seasonal_z_score | 0.2500 | 1.0000 | 0.4000 | 9 | 1.0000 | 0.0000 |
| faa-notam-2023 | isolation_forest | 0.1333 | 0.6667 | 0.2222 | 13 | 1.0000 | 1.0000 |
| faa-notam-2023 | quality_aware_fusion | 0.0938 | 1.0000 | 0.1714 | 29 | 1.0000 | 0.0000 |
| nab-nyc-taxi | seasonal_z_score | 0.8831 | 0.1095 | 0.1948 | 9 | 1.0000 | 33.1667 |
| nab-nyc-taxi | isolation_forest | 0.5645 | 0.0564 | 0.1025 | 27 | 1.0000 | 53.8333 |
| nab-nyc-taxi | quality_aware_fusion | 0.8831 | 0.1095 | 0.1948 | 9 | 1.0000 | 33.1667 |
| nab-machine-temperature | seasonal_z_score | 0.9731 | 0.9559 | 0.9644 | 15 | 1.0000 | 0.0000 |
| nab-machine-temperature | isolation_forest | 1.0000 | 0.8765 | 0.9342 | 0 | 1.0000 | 3.4167 |
| nab-machine-temperature | quality_aware_fusion | 0.9313 | 0.9559 | 0.9434 | 40 | 1.0000 | 0.0000 |

## Numeric forecasts

| Case | Target | Horizon (h) | Method | MAE | RMSE | Targets |
|---|---|---:|---|---:|---:|---:|
| suez-2021 | Suez vessel transits (vessels/day) | 24.0000 | persistence | 12.2917 | 16.6896 | 24 |
| suez-2021 | Suez vessel transits (vessels/day) | 24.0000 | quantile_gradient_boosting | 21.3119 | 26.3352 | 24 |
| suez-2021 | Suez vessel transits (vessels/day) | 24.0000 | seasonal | 33.4583 | 40.7006 | 24 |
| ian-2022 | Reported 1-hour precipitation (mm) | 6.0000 | persistence | 0.4605 | 2.0856 | 54 |
| ian-2022 | Reported 1-hour precipitation (mm) | 6.0000 | quantile_gradient_boosting | 0.5324 | 2.4524 | 54 |
| ian-2022 | Reported 1-hour precipitation (mm) | 6.0000 | seasonal | 0.6431 | 2.5796 | 54 |
| canada-smoke-2023 | NYC fixed-monitor PM2.5 (micrograms/m³) | 6.0000 | persistence | 20.8226 | 46.0037 | 62 |
| canada-smoke-2023 | NYC fixed-monitor PM2.5 (micrograms/m³) | 6.0000 | quantile_gradient_boosting | 39.1883 | 72.9095 | 62 |
| canada-smoke-2023 | NYC fixed-monitor PM2.5 (micrograms/m³) | 6.0000 | seasonal | 47.6774 | 80.4310 | 62 |
| tonga-2022 | Regional catalogued earthquakes M≥4 (events/6h) | 6.0000 | persistence | 1.1912 | 1.5765 | 68 |
| tonga-2022 | Regional catalogued earthquakes M≥4 (events/6h) | 6.0000 | quantile_gradient_boosting | 1.6029 | 2.2524 | 68 |
| tonga-2022 | Regional catalogued earthquakes M≥4 (events/6h) | 6.0000 | seasonal | 1.3235 | 1.7905 | 68 |
| pakistan-floods-2022 | Reported 3-hour precipitation (mm) | 6.0000 | persistence | 2.8571 | 7.6718 | 14 |
| pakistan-floods-2022 | Reported 3-hour precipitation (mm) | 6.0000 | quantile_gradient_boosting | 4.5714 | 13.7061 | 14 |
| pakistan-floods-2022 | Reported 3-hour precipitation (mm) | 6.0000 | seasonal | 5.6429 | 14.8541 | 14 |
| faa-notam-2023 | Mean departure delay by scheduled departure hour (minutes) | 6.0000 | persistence | 13.1278 | 20.3154 | 50 |
| faa-notam-2023 | Mean departure delay by scheduled departure hour (minutes) | 6.0000 | quantile_gradient_boosting | 13.0817 | 20.7159 | 50 |
| faa-notam-2023 | Mean departure delay by scheduled departure hour (minutes) | 6.0000 | seasonal | 18.5743 | 28.0628 | 50 |
| nab-nyc-taxi | Taxi passengers per half hour (passengers/30min) | 6.0000 | persistence | 8420.5104 | 10338.6121 | 96 |
| nab-nyc-taxi | Taxi passengers per half hour (passengers/30min) | 6.0000 | quantile_gradient_boosting | 3267.0673 | 4323.9741 | 96 |
| nab-nyc-taxi | Taxi passengers per half hour (passengers/30min) | 6.0000 | seasonal | 3249.2292 | 5027.5354 | 96 |
| nab-machine-temperature | Equipment temperature (provider temperature units) | 6.0000 | persistence | 5.2347 | 9.9835 | 96 |
| nab-machine-temperature | Equipment temperature (provider temperature units) | 6.0000 | quantile_gradient_boosting | 6.2708 | 10.0943 | 96 |
| nab-machine-temperature | Equipment temperature (provider temperature units) | 6.0000 | seasonal | 13.5169 | 22.3865 | 96 |

## Advance warning

| Case | Status | Brier | Prevalence Brier | Brier skill | Warning precision | Recall | Warned / onsets | Lead (h) | False-warning h |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| suez-2021 | insufficient_labels | — | — | — | — | — | — | — | — |
| ian-2022 | insufficient_labels | — | — | — | — | — | — | — | — |
| canada-smoke-2023 | insufficient_labels | — | — | — | — | — | — | — | — |
| tonga-2022 | insufficient_labels | — | — | — | — | — | — | — | — |
| pakistan-floods-2022 | insufficient_labels | — | — | — | — | — | — | — | — |
| faa-notam-2023 | unsupported_source_availability | — | — | — | — | — | — | — | — |
| nab-nyc-taxi | heldout_evaluated | 0.0248 | 0.0251 | 0.0086 | 0.0178 | 0.1389 | 2 / 3 | 3.5000 | 138.0000 |
| nab-machine-temperature | heldout_evaluated | 0.0151 | 0.0182 | 0.1670 | 0.9701 | 0.9028 | 1 / 1 | 5.5000 | 0.1667 |

A small Brier improvement can coexist with poor warning precision or no useful alarms. Warning metrics exclude already labelled windows and purge targets crossing split boundaries. Lead time refers to the annotated window onset, whose physical timing is uncertain. Few heldout events and unavailable original publication vintages prevent a validated live prediction claim. Historical experimental models do not validate the legacy regional composite score.

## Data quality and reproduction

- `suez-2021`: 105 native slots at 24 hours; train/calibration/test 64/17/24; fingerprint `3219287fc768813b90bcd184cac8eba78e70118e25154af59c3135b88c84d8f0`.
- `ian-2022`: 2568 native slots at 1 hours; train/calibration/test 1708/428/432; fingerprint `402ea4fb65032442215b5fe189f2573d51b4e591cf6b66970b1fc3e321158b50`.
- `canada-smoke-2023`: 1920 native slots at 1 hours; train/calibration/test 1267/317/336; fingerprint `53fb79e4124743fe0f73652e4b7c6f0aef0897dfef8bae2a5a5c9205f37b650e`.
- `tonga-2022`: 312 native slots at 6 hours; train/calibration/test 195/49/68; fingerprint `26269319c16ff6270a564a9d59b49234ac67a9a9055dc129cb8cdcf25281e618`.
- `pakistan-floods-2022`: 856 native slots at 3 hours; train/calibration/test 320/80/456; fingerprint `ea3b9b1aea160ab5f89e3103a9845d7c330e6d204d8f5fe2461d8a09c5d6bdf9`.
- `faa-notam-2023`: 744 native slots at 1 hours; train/calibration/test 196/50/498; fingerprint `6905aac9354d6a23516aceb6a212c3583b3f7262357d75d832656204a71ae8a0`.
- `nab-nyc-taxi`: 10320 native slots at 0.5000 hours; train/calibration/test 6192/2064/2064; fingerprint `a2e5811c6972a27ea7563723161b534d89f10aca623902b8a2f936be9b50fa81`.
- `nab-machine-temperature`: 22683 native slots at 0.0833 hours; train/calibration/test 13609/4537/4537; fingerprint `bc10773970aa4ea2f45b10465a93d67c788032026bcb831088f5f5d40cfed5c8`.

Regenerate with the historical CLI; the in-app evaluation ZIP additionally contains the complete processed observations and labels, a readable per-case report, evaluated predictions and checksum manifest. Machine-clock duplicates are excluded as ambiguous; source bytes remain archived.
