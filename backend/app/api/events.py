from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.models.aviation import Event, Region
from geoalchemy2 import functions as geo_func

router = APIRouter()


@router.get("")
def get_events(
    region_id: UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Recent events with coordinates for the globe + timeline."""
    cutoff = func.now() - timedelta(days=14)
    query = db.query(Event, Region.name).join(Region, Event.region_id == Region.id)

    if region_id:
        query = query.filter(Event.region_id == region_id)

    rows = (
        query.filter(Event.event_date >= cutoff)
        .order_by(Event.event_date.desc())
        .limit(limit)
        .all()
    )
    events = []
    for event, region_name in rows:
        wkt = db.scalar(geo_func.ST_AsText(event.position))
        try:
            parts = wkt.replace("POINT(", "").replace(")", "").split()
            lon, lat = float(parts[0]), float(parts[1])
        except (ValueError, IndexError, AttributeError):
            lon, lat = 0.0, 0.0
        events.append(
            {
                "id": str(event.id),
                "external_id": event.external_id,
                "event_date": event.event_date.isoformat(),
                "event_type": event.event_type,
                "category": event.category,
                "severity": event.severity,
                "description": event.description,
                "region_name": region_name,
                "lat": lat,
                "lon": lon,
            }
        )
    return events
