from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.events import get_events

router = APIRouter()


@router.get("")
def list_events(
    region_id: UUID | None = None,
    days: int = Query(7, ge=1, le=30),
    min_magnitude: float = Query(0.0, ge=0, le=10),
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    """Recent events (USGS earthquakes in live mode), newest first."""
    return get_events(
        db,
        region_id=region_id,
        days=days,
        min_magnitude=min_magnitude,
        limit=limit,
    )
