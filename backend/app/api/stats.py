from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import get_settings
from app.models.aviation import (
    Event,
    FlightObservation,
    Region,
    SatelliteObservation,
)
from app.services.disruption import compute_all_disruptions

router = APIRouter()


@router.get("")
def get_stats_summary(db: Session = Depends(get_db)):
    """Global dashboard stats."""
    cutoff = func.now() - timedelta(days=1)
    total_flights = (
        db.query(func.count(FlightObservation.id))
        .filter(FlightObservation.timestamp >= cutoff)
        .scalar()
    ) or 0
    total_satellites = (
        db.query(func.count(func.distinct(SatelliteObservation.satellite_id))).scalar()
    ) or 0
    active_events = (
        db.query(func.count(Event.id))
        .filter(Event.event_date >= cutoff)
        .scalar()
    ) or 0
    region_count = db.query(func.count(Region.id)).scalar() or 0

    disruptions = compute_all_disruptions(db)
    global_index = (
        sum(d["composite_index"] for d in disruptions) / len(disruptions)
        if disruptions
        else 0.0
    )
    worst = max(disruptions, key=lambda d: d["composite_index"], default=None)

    settings = get_settings()
    return {
        "flights_24h": total_flights,
        "satellites_tracked": total_satellites,
        "active_events": active_events,
        "regions_monitored": region_count,
        "global_disruption_index": round(global_index, 1),
        "most_disrupted_region": worst["region_name"] if worst else None,
        "most_disrupted_index": worst["composite_index"] if worst else 0.0,
        "severity_bands": {
            "low": settings.severity_low,
            "medium": settings.severity_medium,
            "high": settings.severity_high,
        },
    }
