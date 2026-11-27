# SkyNexus academic demo (about six minutes)

Run `docker compose up -d --build`, open http://localhost:5173 and select **Enter demo**. The current installation has all eight public historical datasets cached. For a new installation, use each case’s Download public data button or run the commands in [HISTORICAL_DATA.md](HISTORICAL_DATA.md).

## 1. The research question (0:00–0:40)

Can public observations help identify unusual regional activity, and do evaluated predictors provide useful warning before an independently annotated change? Show the source catalogue and distinguish native streams, provider polling, historical archives and synthetic cases.

## 2. Replay a documented event (0:40–1:40)

Open Historical replay and select Suez 2021. Show the real daily vessel counts, source attribution and daily step size. Scrub through the March blockage and recovery. Reveal the event-window labels and explain that a documented event interval is a coarse association target, not independent measurement-level operational ground truth.

## 3. Inspect coverage and scientific meaning (1:40–2:30)

Open Hurricane Ian or the smoke case. Inspect the units and a missing measurement. Missing sensor data stays unavailable. The smoke case uses one fixed NYC monitor selected by pre-event coverage. Weather and pollution observations do not prove airport closure or infrastructure damage. Tonga’s available series measures seismic context, not internet connectivity.

## 4. Evaluate real labelled data (2:30–4:15)

Select NYC taxi passenger demand. The measurements and anomaly windows come from the pinned public NAB archive. Open the evaluated result: training, calibration and test are separate and chronological. Compare seasonal Z-score, Isolation Forest and quality-aware fusion. Point out the difference between per-sample recall and detecting some part of an event window.

Inspect numeric forecast MAE/RMSE against persistence and seasonal baselines. Then inspect the onset-warning probabilities, Brier score, warning precision, positive lead time and false-warning hours. A small Brier improvement can coexist with poor warning precision; read the actual result rather than presenting all detection as useful prediction. Source clocks and buffered annotation windows limit the interpretation of lead time.

## 5. Explain refusal and quality controls (4:15–5:10)

Show insufficient warning labels for a single-event case. FAA delay outcomes were released later, so the tool does not claim live advance-warning validity from them. The equipment case has a real clock reversal: duplicate timestamps are excluded instead of guessing between conflicting readings. Explain that the displayed native sample axis and source limitations remain inspectable.

## 6. Reproduce the result (5:10–6:00)

Download a historical evaluation ZIP. It contains processed observations and labels, evaluated outputs, a readable study report, checksums and method metadata. NAB exports also include its license notice. Separate synthetic tests remain available for controlled outages and compound scenarios. Finish with the globe modes and realtime/pause control, distinguishing incoming live observations from historical replay.
