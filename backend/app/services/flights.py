"""Flight data access and query service."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_live_flights(db: Session, limit: int = 3000, window_minutes: int = 60) -> list[dict]:
    """Latest position of every aircraft seen in the most recent window
    of data (one row per aircraft)."""
    from app.core.config import get_settings

    mode = get_settings().DATA_MODE
    src_filter = "fo.source = 'demo_dataset'" if mode == "demo" else "fo.source != 'demo_dataset'"
    latest_filter = "source = 'demo_dataset'" if mode == "demo" else "source != 'demo_dataset'"

    rows = db.execute(text(
        f"""
        WITH latest AS (
            SELECT COALESCE(MAX(timestamp), now()) AS t
            FROM flight_observations
            WHERE {latest_filter}
        )
        SELECT DISTINCT ON (fo.icao24)
               fo.icao24, fo.callsign, ST_Y(fo.position), ST_X(fo.position),
               fo.altitude_ft, fo.speed_kt, fo.heading_deg, fo.timestamp, fo.source,
               r.id::text, r.name
        FROM flight_observations fo
        LEFT JOIN flight_routes fr ON fr.id = fo.route_id
        LEFT JOIN regions r ON r.id = fr.region_id, latest
        WHERE fo.timestamp >= latest.t - make_interval(mins => :mins)
          AND {src_filter}
        ORDER BY fo.icao24, fo.timestamp DESC
        LIMIT :limit
        """
    ), {"limit": limit, "mins": window_minutes}).all()
    return [
        {
            "icao24": r[0],
            "callsign": r[1],
            "lat": float(r[2]),
            "lon": float(r[3]),
            "altitude_ft": r[4],
            "speed_kt": round(float(r[5]), 0),
            "heading_deg": round(float(r[6]), 0),
            "timestamp": r[7].isoformat(),
            "source": r[8],
            "region_id": r[9],
            "region_name": r[10],
        }
        for r in rows
    ]

