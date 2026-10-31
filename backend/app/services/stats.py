"""Stats service: headline summary numbers for the top strip."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.disruption import compute_all_disruptions
from app.services.satellites import catalog


def get_system_stats(db: Session) -> dict:
    """Headline numbers for the top strip."""
    settings = get_settings()
    mode = settings.DATA_MODE
    now = datetime.now(timezone.utc)
    src_fo = "source = 'demo_dataset'" if mode == "demo" else "source != 'demo_dataset'"
    src_ev = "source = 'demo_dataset'" if mode == "demo" else "source != 'demo_dataset'"

    aircraft_now = db.execute(text(
        f"""
        SELECT COUNT(DISTINCT icao24) FROM flight_observations
        WHERE timestamp >= (SELECT COALESCE(MAX(timestamp), now()) FROM flight_observations WHERE {src_fo}) - interval '60 minutes'
          AND {src_fo}
        """
    )).scalar() or 0

    if mode == "demo":
        max_ev = db.execute(text("SELECT MAX(event_date) FROM events WHERE source = 'demo_dataset'")).scalar()
        ev_t = (max_ev - timedelta(hours=24)) if max_ev else (now - timedelta(hours=24))
    else:
        ev_t = now - timedelta(hours=24)

    events_24h = db.execute(text(
        f"SELECT COUNT(*) FROM events WHERE event_date >= :t AND {src_ev}"
    ), {"t": ev_t}).scalar() or 0

    last_update = db.execute(text(f"SELECT MAX(ingested_at) FROM flight_observations WHERE {src_fo}")).scalar()

    disruptions = compute_all_disruptions(db)
    counts = {"Calm": 0, "Watch": 0, "Elevated": 0, "Critical": 0}
    for d in disruptions:
        counts[d["status"]] += 1
    worst = disruptions[0] if disruptions else None
    global_index = round(sum(d["composite_index"] for d in disruptions) / len(disruptions), 1) if disruptions else 0.0
    return {
        "aircraft_now": aircraft_now,
        "satellites_tracked": len(catalog(db)),
        "events_24h": events_24h,
        "regions_monitored": len(disruptions),
        "status_counts": counts,
        "needs_attention": counts["Elevated"] + counts["Critical"],
        "global_disruption_index": global_index,
        "most_disrupted_region": worst["region_name"] if worst else None,
        "most_disrupted_index": worst["composite_index"] if worst else 0.0,
        "last_update": last_update.isoformat() if last_update else None,
        "data_mode": settings.DATA_MODE,
        "ingest_interval_s": settings.LIVE_INGEST_INTERVAL_S if settings.LIVE_INGEST else None,
        "severity_bands": {
            "low": settings.severity_low,
            "medium": settings.severity_medium,
            "high": settings.severity_high,
        },
    }

