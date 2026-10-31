"""Events service: retrieve and filter external events (e.g. USGS earthquakes)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.series import magnitude_of


def get_events(
    db: Session,
    region_id: UUID | None = None,
    days: int = 7,
    min_magnitude: float = 0.0,
    limit: int = 500,
) -> list[dict]:
    """Recent events (USGS earthquakes in live mode), newest first."""
    from app.core.config import get_settings

    mode = get_settings().DATA_MODE
    src_clause = "AND e.source = 'demo_dataset'" if mode == "demo" else "AND e.source != 'demo_dataset'"
    if mode == "demo":
        max_d = db.execute(text("SELECT MAX(event_date) FROM events WHERE source = 'demo_dataset'")).scalar()
        since = (max_d - timedelta(days=days)) if max_d else (datetime.now(timezone.utc) - timedelta(days=days))
    else:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    sql = f"""
        SELECT e.id::text, e.external_id, e.event_date, e.event_type, e.category, e.severity,
               e.description, r.id::text, r.name, ST_Y(e.position), ST_X(e.position), e.source
        FROM events e JOIN regions r ON r.id = e.region_id
        WHERE e.event_date >= :since {src_clause} {{region}}
        ORDER BY e.event_date DESC LIMIT :limit
    """.format(region="AND e.region_id = :rid" if region_id else "")
    params: dict = {"since": since, "limit": limit}
    if region_id:
        params["rid"] = str(region_id)

    out = []
    for r in db.execute(text(sql), params).all():
        mag = magnitude_of(r[6], r[5])
        if mag < min_magnitude:
            continue
        out.append({
            "id": r[0],
            "external_id": r[1],
            "event_date": r[2].isoformat(),
            "event_type": r[3],
            "category": r[4],
            "severity": r[5],
            "description": r[6],
            "region_id": r[7],
            "region_name": r[8],
            "lat": float(r[9]),
            "lon": float(r[10]),
            "source": r[11],
            "magnitude": mag,
        })
    return out

