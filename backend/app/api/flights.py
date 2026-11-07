from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.flights import get_flight_detail, get_flight_deviations, get_live_flights

router = APIRouter()


@router.get("/live")
def live_flights(limit: int = Query(3000, le=10000), db: Session = Depends(get_db)):
    """Latest position of every aircraft seen in the most recent window of data,
    including general travel route endpoints and cross-track deviation."""
    return get_live_flights(db, limit=limit)


@router.get("/deviations")
def flight_deviations(min_km: float | None = Query(None, ge=0.0), limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    """All live flights with cross-track deviation exceeding min_km from general travel route."""
    return get_flight_deviations(db, min_deviation_km=min_km, limit=limit)


@router.get("/{icao24}/route")
def flight_route_detail(icao24: str, db: Session = Depends(get_db)):
    """General travel route vs current position, waypoints, trail and deviation for an aircraft."""
    detail = get_flight_detail(db, icao24)
    if detail is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return detail
