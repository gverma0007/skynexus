from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.geo import region_for, region_shapes
from app.services.orbits import ground_track, orbit_params, propagate
from app.services.satellites import CATEGORY_LABELS, live_positions

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
    rows = db.execute(text(
        "SELECT COALESCE(category, 'other'), COUNT(*) FROM satellites GROUP BY 1 ORDER BY 2 DESC"
    )).all()
    return [{"category": c, "label": CATEGORY_LABELS.get(c, "Other"), "count": n} for c, n in rows]


@router.get("/{norad_id}")
def satellite_detail(norad_id: int, minutes: int = Query(90, ge=10, le=300), db: Session = Depends(get_db)):
    """Identity, orbit, live position and a +/- N minute ground track."""
    row = db.execute(text(
        "SELECT norad_id, name, COALESCE(category, 'other'), tle_line1, tle_line2 "
        "FROM satellites WHERE norad_id = :n"
    ), {"n": norad_id}).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    norad, name, category, l1, l2 = row
    if not (l1 and l2):
        raise HTTPException(status_code=422, detail="No orbital elements stored for this satellite")
    now = datetime.now(timezone.utc)
    try:
        lat, lon, alt, speed = propagate(l1, l2, now)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Could not propagate orbit: {exc}")
    reg = region_for(region_shapes(db), lat, lon)
    return {
        "norad_id": norad, "name": name, "category": category,
        "category_label": CATEGORY_LABELS.get(category, "Other"),
        "position": {"time": now.isoformat(), "lat": round(lat, 3), "lon": round(lon, 3),
                     "alt_km": round(alt, 1), "speed_km_s": round(speed, 2)},
        "region_name": reg["name"] if reg else None,
        "orbit": orbit_params(l1, l2),
        "track": ground_track(l1, l2, now, minutes, minutes, 2),
    }
