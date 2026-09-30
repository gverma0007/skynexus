from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.core.db import get_db
from app.models.aviation import Region
from app.services.disruption import compute_all_disruptions

router = APIRouter()


def _parse_point(wkt: str | None) -> tuple[float, float]:
    """Parse 'POINT(lon lat)' -> (lat, lon)."""
    if not wkt:
        return 0.0, 0.0
    try:
        coords = wkt.replace("POINT(", "").replace(")", "").split()
        lon, lat = float(coords[0]), float(coords[1])
        return lat, lon
    except (ValueError, IndexError):
        return 0.0, 0.0


@router.get("/regions")
def get_regions(db: Session = Depends(get_db)):
    regions = db.query(Region).order_by(Region.name).all()
    return [
        {"id": str(r.id), "name": r.name} for r in regions
    ]


@router.get("/regions/map")
def get_regions_map(db: Session = Depends(get_db)):
    """Regions with centroid coordinates + live disruption scores for the globe."""
    disruptions = {d["region_id"]: d for d in compute_all_disruptions(db)}
    rows = db.query(Region.id, Region.name, func.ST_AsText(Region.centroid)).all()
    features = []
    for region_id, name, centroid_wkt in rows:
        lat, lon = _parse_point(centroid_wkt)
        d = disruptions.get(str(region_id), {})
        features.append(
            {
                "id": str(region_id),
                "name": name,
                "lat": lat,
                "lon": lon,
                "composite_index": d.get("composite_index", 0.0),
                "severity_label": d.get("severity_label", "normal"),
                "flight_anomaly_score": d.get("flight_anomaly_score", 0.0),
                "event_relevance_score": d.get("event_relevance_score", 0.0),
                "weather_score": d.get("weather_score", 0.0),
            }
        )
    return features
