from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


@router.get("/live")
def live_flights(limit: int = Query(1500, le=5000), db: Session = Depends(get_db)):
    """Latest position of every aircraft seen in the most recent 20 minutes
    of data (one row per aircraft)."""
    rows = db.execute(text(
        """
        WITH latest AS (SELECT MAX(timestamp) AS t FROM flight_observations)
        SELECT DISTINCT ON (fo.icao24)
               fo.icao24, fo.callsign, ST_Y(fo.position), ST_X(fo.position),
               fo.altitude_ft, fo.speed_kt, fo.heading_deg, fo.timestamp, fo.source,
               r.id::text, r.name
        FROM flight_observations fo
        LEFT JOIN flight_routes fr ON fr.id = fo.route_id
        LEFT JOIN regions r ON r.id = fr.region_id, latest
        WHERE fo.timestamp >= latest.t - interval '20 minutes'
        ORDER BY fo.icao24, fo.timestamp DESC
        LIMIT :limit
        """
    ), {"limit": limit}).all()
    return [
        {"icao24": r[0], "callsign": r[1], "lat": float(r[2]), "lon": float(r[3]),
         "altitude_ft": r[4], "speed_kt": round(float(r[5]), 0), "heading_deg": round(float(r[6]), 0),
         "timestamp": r[7].isoformat(), "source": r[8], "region_id": r[9], "region_name": r[10]}
        for r in rows
    ]
