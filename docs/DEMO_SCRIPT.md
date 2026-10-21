# SkyNexus demo script (about 4 minutes)

Run in demo mode for a predictable walkthrough: set `DATA_MODE=demo` in `.env`, then `docker compose up --build`.

## 1. The question it answers (0:00–0:30)
"SkyNexus watches 15 regions and answers one question: where is activity unusual right now, and why? It combines aircraft positions, satellite orbits, weather and earthquakes from free public feeds."

## 2. Overview (0:30–1:30)
- Read the headline: "2 regions need attention". Point out the ranked list on the left.
- The globe is shaded by severity. Darker ink means more disruption, and red is reserved for Critical. Drag it and toggle the layers.
- Click **Red Sea**. The score is 80, Critical, up from yesterday. The bars show the drivers: air traffic about 60% above its usual level for this hour, plus an M6.1 and an M5.8 earthquake.
- The chart shows aircraft per hour against the grey usual range, with the dashed 6-hour projection.

## 3. Weather is ruled out first (1:30–2:00)
- Click **Eastern Mediterranean**. Traffic is down about 20%, but storm intensity is high, so the panel says "Bad weather may explain the drop in air traffic".
- Click **Taiwan Strait**. Traffic is down about 40% in fair weather, the pattern an airspace restriction would leave. Say clearly that the system does not claim a cause.

## 4. Evidence (2:00–3:00)
- **Events, Anomaly log:** each flagged hour shows its z-score and Isolation Forest score.
- **Satellites:** search "ISS" with Ctrl+K. Show the ground track and orbital elements. Positions are computed live with SGP4 and verified against Skyfield in the tests.
- **Regions:** compare Red Sea and Taiwan Strait side by side, then export the CSV.

## 5. Report (3:00–3:40)
- From Red Sea, click **Compare last 24 h**. Walk through before and after for each measure and read the assessment.
- Click **Print or save as PDF**. Point to the causation disclaimer.

## 6. Close (3:40–4:00)
"It runs with one command, `docker compose up`. Switch to live mode and the same pipeline runs on real feeds every 10 minutes. The System page shows each source's health."
