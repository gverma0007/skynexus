from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.aviation import Region
from app.services.pressure_zones import compute_pressure_zones

router = APIRouter()


@router.get("")
def get_pressure_zones(db: Session = Depends(get_db)):
    """Model-identified pressure zones with centroid coordinates."""
    model_rows = compute_pressure_zones(db)
    centroids = {
        str(r.id): (lat, lon)
        for r in db.query(
            Region.id,
            func.ST_Y(Region.centroid).label("lat"),
            func.ST_X(Region.centroid).label("lon"),
        ).all()
        for lat, lon in [(float(r.lat), float(r.lon))]
    }
    for row in model_rows:
        lat, lon = centroids.get(row["region_id"], (0.0, 0.0))
        row["lat"] = lat
        row["lon"] = lon
    return model_rows
