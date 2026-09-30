# SkyNexus Demo Script

## 1. Introduction (0:00 - 0:30)
- "Welcome to SkyNexus, our Global Activity Anomaly & Impact Intelligence System."
- "SkyNexus fuses flight traffic, satellite positions, weather, and global events into one real-time 3D operating picture."

## 2. Dashboard Overview (0:30 - 1:30)
- "The 3D globe shows live activity: flight arcs between real hub airports, satellites on their ground tracks, and event dots color-coded by severity."
- "The stats bar tracks 24h flights, satellites, active events, and the global disruption index — notice the Middle East flagged as most disrupted."
- "Hot regions pulse with warning rings; calm ones stay green."

## 3. Deep Dive: Region Inspection (1:30 - 2:30)
- "Clicking any marker — or a row in the Regional Disruption Index — opens the region drawer."
- "Each region scores 0-100 from three signals: flight volume vs its own baseline, security-event severity, and storm intensity."
- "The What Changed? modal compares the last 6, 24, or 72 hours against the previous window across all four domains."

## 4. AI Explanation & Forecast (2:30 - 3:30)
- "The AI Explainer turns those deltas into plain language — for example, Eastern Europe's 700% flight surge alongside new NOTAMs."
- "Set an ANTHROPIC_API_KEY and the narrative is generated live; otherwise a deterministic analyzer produces it."
- "The Forecast Panel projects flight volume for the next 6 hours against observed history."

## 5. Conclusion (3:30 - 4:00)
- "SkyNexus turns complex global data into actionable intelligence."
- "Everything runs from one command: docker compose up, then bootstrap."
- "Thank you for watching."
