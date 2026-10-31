from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.disruption import compute_all_disruptions
from app.services.geo import get_region_outlines
from app.services.satellites import get_region_overhead
from app.services.series import compute_region_forecast, compute_region_history, get_series

router = APIRouter()


def _disruption_or_404(db: Session, region_id: str) -> dict:
    for d in compute_all_disruptions(db):
        if d["region_id"] == region_id:
            return d
    raise HTTPException(status_code=404, detail="Region not found")


@router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    """Every monitored region with its current disruption score."""
    return compute_all_disruptions(db)


@router.get("/regions/outline")
def region_outlines(db: Session = Depends(get_db)):
    """Boundary rings as [lat, lon] pairs, for the globe."""
    return get_region_outlines(db)


@router.get("/regions/{region_id}")
def region_detail(region_id: UUID, db: Session = Depends(get_db)):
    return _disruption_or_404(db, str(region_id))


@router.get("/regions/{region_id}/history")
def region_history(region_id: UUID, hours: int = Query(48, ge=6, le=168), db: Session = Depends(get_db)):
    """Hourly aircraft, storm and event counts with a 'normal range' band."""
    bundle = get_series(db)
    result = compute_region_history(bundle, str(region_id), hours=hours)
    if result is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return result


@router.get("/regions/{region_id}/overhead")
def region_overhead(region_id: UUID, db: Session = Depends(get_db)):
    """Satellites whose ground point is inside the region right now."""
    return get_region_overhead(db, str(region_id))


@router.get("/regions/{region_id}/forecast")
def region_forecast(region_id: UUID, horizon_hours: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    """Linear trend on the last 12 complete hours of air traffic."""
    bundle = get_series(db)
    result = compute_region_forecast(bundle, str(region_id), horizon_hours=horizon_hours)
    if result is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return result
