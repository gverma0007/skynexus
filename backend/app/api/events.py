from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.series import magnitude_of

router = APIRouter()


@router.get("")
def list_events(
    region_id: UUID | None = None,
    days: int = Query(7, ge=1, le=30),
    min_magnitude: float = Query(0.0, ge=0, le=10),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    """Recent events (USGS earthquakes in live mode), newest first."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = """
        SELECT e.id::text, e.external_id, e.event_date, e.event_type, e.category, e.severity,
               e.description, r.id::text, r.name, ST_Y(e.position), ST_X(e.position), e.source
        FROM events e JOIN regions r ON r.id = e.region_id
        WHERE e.event_date >= :since {region}
        ORDER BY e.event_date DESC LIMIT :limit
    """.format(region="AND e.region_id = :rid" if region_id else "")
    params = {"since": since, "limit": limit}
    if region_id:
        params["rid"] = str(region_id)
    out = []
    for r in db.execute(text(sql), params).all():
        mag = magnitude_of(r[6], r[5])
        if mag < min_magnitude:
            continue
        out.append({
            "id": r[0], "external_id": r[1], "event_date": r[2].isoformat(), "event_type": r[3],
            "category": r[4], "severity": r[5], "description": r[6], "region_id": r[7],
            "region_name": r[8], "lat": float(r[9]), "lon": float(r[10]), "source": r[11],
            "magnitude": mag,
        })
    return out
