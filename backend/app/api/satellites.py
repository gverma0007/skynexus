import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.aviation import Satellite, SatelliteObservation
from geoalchemy2 import functions as geo_func

router = APIRouter()


@router.get("/live")
def get_live_satellites(db: Session = Depends(get_db)):
    """Latest observation per satellite with ground-track coordinates."""
    satellites = db.query(Satellite).all()
    result = []
    for sat in satellites:
        latest = (
            db.query(SatelliteObservation)
            .filter(SatelliteObservation.satellite_id == sat.id)
            .order_by(SatelliteObservation.timestamp.desc())
            .first()
        )
        if latest is None:
            continue
        wkt = db.scalar(geo_func.ST_AsText(latest.position))
        # Handles 'POINTZ(lon lat alt)', 'POINT Z (lon lat alt)', 'POINT(lon lat)'
        try:
            nums = re.findall(r"-?\d+\.?\d*(?:e[-+]?\d+)?", wkt or "")
            lon, lat = float(nums[0]), float(nums[1])
            alt = float(nums[2]) if len(nums) > 2 else latest.altitude_km
        except (ValueError, IndexError, TypeError):
            lon, lat, alt = 0.0, 0.0, latest.altitude_km
        result.append(
            {
                "id": str(sat.id),
                "norad_id": sat.norad_id,
                "name": sat.name,
                "lat": lat,
                "lon": lon,
                "altitude_km": alt,
                "timestamp": latest.timestamp.isoformat(),
            }
        )
    return result
