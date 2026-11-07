"""Alerts service: synthesize things worth a person's attention right now."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml.anomaly import describe
from app.services.disruption import compute_all_disruptions
from app.services.series import get_series

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}


def get_active_alerts(db: Session) -> list[dict]:
    """Compile active alerts from disruptions, conflict threats, anomalies, and system health."""
    now = datetime.now(timezone.utc)
    alerts: list[dict] = []

    # 1. High/Medium Disruption regions
    for d in compute_all_disruptions(db):
        if d["severity_label"] in ("medium", "high"):
            alerts.append({
                "id": f"region-{d['region_id']}-{d['severity_label']}",
                "level": "critical" if d["severity_label"] == "high" else "warning",
                "title": f"{d['region_name']} is {d['status'].lower()} ({d['composite_index']:.0f})",
                "detail": " ".join(d["explanation"][:2]),
                "region_id": d["region_id"],
                "time": now.isoformat(),
                "kind": "region",
            })

    # 2. Significant security/threat incidents (Lvl 5.5+) in last 24h
    for e in get_series(db).events:
        if e["magnitude"] >= 5.5 and e["event_date"] >= now - timedelta(hours=24):
            desc = (e["description"] or e["event_type"]).replace(" earthquake — ", ", ")
            desc = desc.replace("earthquake", "incident").replace("Earthquake", "Incident")
            alerts.append({
                "id": f"event-{e['id']}",
                "level": "critical" if e["magnitude"] >= 6.5 else "warning",
                "title": f"High severity incident (Lvl {e['magnitude']:.1f})",
                "detail": desc,
                "region_id": e["region_id"],
                "time": e["event_date"].isoformat(),
                "kind": "event",
            })

    # 3. High anomaly scores in last 6h
    rows = db.execute(text(
        """
        SELECT a.id::text, a.region_id::text, r.name, a.timestamp, a.feature_name, a.observed_value,
               a.z_score, a.composite_score, a.severity_label
        FROM anomaly_scores a JOIN regions r ON r.id = a.region_id
        WHERE a.timestamp >= now() - interval '6 hours' AND a.severity_label = 'high'
        ORDER BY a.composite_score DESC LIMIT 10
        """
    )).all()
    seen_regions: set[str] = set()
    for r in rows:
        if r[1] in seen_regions:
            continue
        seen_regions.add(r[1])
        row = {"feature_name": r[4], "observed_value": r[5], "z_score": r[6]}
        alerts.append({
            "id": f"anomaly-{r[0]}",
            "level": "warning",
            "title": f"Anomaly in {r[2]} (score {r[7]:.0f})",
            "detail": describe(row),
            "region_id": r[1],
            "time": r[3].isoformat(),
            "kind": "anomaly",
        })

    # 4. System staleness in live ingest mode
    settings = get_settings()
    if settings.DATA_MODE == "live" and settings.LIVE_INGEST:
        latest = db.execute(text("SELECT MAX(ingested_at) FROM flight_observations")).scalar()
        stale_after = timedelta(seconds=settings.LIVE_INGEST_INTERVAL_S * 3)
        if latest is None or now - latest > stale_after:
            alerts.append({
                "id": "system-stale-flights",
                "level": "info",
                "title": "Air-traffic data is not updating",
                "detail": "No new aircraft positions recently. Check the System page.",
                "region_id": None,
                "time": now.isoformat(),
                "kind": "system",
            })

    alerts.sort(key=lambda a: a["time"], reverse=True)
    alerts.sort(key=lambda a: LEVEL_ORDER[a["level"]])
    return alerts

