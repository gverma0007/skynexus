from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.services.disruption import compute_all_disruptions
from app.services.satellites import catalog

router = APIRouter()


@router.get("")
def stats(db: Session = Depends(get_db)):
    """Headline numbers for the top strip."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    aircraft_now = db.execute(text(
        """
        SELECT COUNT(DISTINCT icao24) FROM flight_observations
        WHERE timestamp >= (SELECT MAX(timestamp) FROM flight_observations) - interval '20 minutes'
        """
    )).scalar() or 0
    events_24h = db.execute(text(
        "SELECT COUNT(*) FROM events WHERE event_date >= :t"
    ), {"t": now - timedelta(hours=24)}).scalar() or 0
    last_update = db.execute(text("SELECT MAX(ingested_at) FROM flight_observations")).scalar()

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
        "severity_bands": {"low": settings.severity_low, "medium": settings.severity_medium,
                           "high": settings.severity_high},
    }
