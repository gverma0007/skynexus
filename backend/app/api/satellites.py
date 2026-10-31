from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.satellites import (
    get_satellite_categories,
    get_satellite_detail,
    live_positions,
)

router = APIRouter()


@router.get("/live")
def live_satellites(category: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    """Every tracked satellite, positioned now from its TLE with SGP4."""
    sats = live_positions(db)
    if category:
        sats = [s for s in sats if s["category"] == category]
    if q:
        ql = q.lower().strip()
        sats = [s for s in sats if ql in s["name"].lower() or ql == str(s["norad_id"])]
    return sats


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return get_satellite_categories(db)


@router.get("/{norad_id}")
def satellite_detail(norad_id: int, minutes: int = Query(90, ge=10, le=300), db: Session = Depends(get_db)):
    """Identity, orbit, live position and a +/- N minute ground track."""
    try:
        detail = get_satellite_detail(db, norad_id, minutes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if detail is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return detail
