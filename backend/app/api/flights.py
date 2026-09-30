from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.core.db import get_db
from app.models.aviation import (
    Airport,
    FlightObservation,
    FlightRoute,
    Region,
)
from geoalchemy2 import functions as geo_func

router = APIRouter()


@router.get("/live")
def get_live_flights(db: Session = Depends(get_db)):
    """Latest position per aircraft with its route context for the globe."""
    # Latest observation per (route, callsign, icao24) — i.e. per aircraft.
    # Postgres DISTINCT ON picks the newest row per group.
    observations = (
        db.query(FlightObservation)
        .distinct(
            FlightObservation.route_id,
            FlightObservation.callsign,
            FlightObservation.icao24,
        )
        .order_by(
            FlightObservation.route_id,
            FlightObservation.callsign,
            FlightObservation.icao24,
            FlightObservation.timestamp.desc(),
        )
        .all()
    )
    observations.sort(key=lambda o: o.timestamp, reverse=True)
    observations = observations[:200]

    flights = []
    for obs in observations:
        route = db.get(FlightRoute, obs.route_id) if obs.route_id else None
        if route is None:
            continue
        origin = db.get(Airport, route.origin_airport_id)
        dest = db.get(Airport, route.dest_airport_id)
        if not origin or not dest:
            continue

        origin_pos = db.scalar(geo_func.ST_AsText(origin.geom))
        dest_pos = db.scalar(geo_func.ST_AsText(dest.geom))
        olon, olat = _coords(origin_pos)
        dlon, dlat = _coords(dest_pos)

        # Aircraft's actual current position
        pos_wkt = db.scalar(geo_func.ST_AsText(obs.position))
        plon, plat = _coords(pos_wkt)

        # Progress = fraction along origin->destination by longitude span
        # (good-enough visual proxy for a great-circle projection).
        if dlon != olon:
            progress = (plon - olon) / (dlon - olon)
        else:
            progress = 0.0
        progress = max(0.0, min(1.0, progress))

        region = db.get(Region, route.region_id) if route.region_id else None
        flights.append(
            {
                "id": str(obs.id),
                "callsign": obs.callsign,
                "icao24": obs.icao24,
                "position": {"lat": plat, "lon": plon},
                "origin": {"name": origin.name, "lat": olat, "lon": olon},
                "destination": {"name": dest.name, "lat": dlat, "lon": dlon},
                "progress": round(progress, 3),
                "altitude_ft": obs.altitude_ft,
                "speed_kt": obs.speed_kt,
                "heading_deg": obs.heading_deg,
                "timestamp": obs.timestamp.isoformat(),
                "source": obs.source,
                "region_name": region.name if region else None,
            }
        )
    return flights


def _coords(wkt: str | None) -> tuple[float, float]:
    """'POINT(lon lat)' -> (lon, lat)."""
    if not wkt:
        return 0.0, 0.0
    try:
        parts = wkt.replace("POINT(", "").replace(")", "").split()
        return float(parts[0]), float(parts[1])
    except (ValueError, IndexError):
        return 0.0, 0.0
