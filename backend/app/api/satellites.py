import math
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
                "category": sat.category or "other",
                "lat": lat,
                "lon": lon,
                "altitude_km": alt,
                "timestamp": latest.timestamp.isoformat(),
            }
        )
    return result



def _orbit_from_tle(l1: str, l2: str) -> dict:
    """Derive human-readable orbital parameters from TLE lines."""
    def num(line: str, start: int, end: int, default: float = 0.0) -> float:
        try:
            return float(line[start:end].strip() or default)
        except ValueError:
            return default

    inclination = num(l2, 8, 16)
    raan = num(l2, 17, 25)
    eccentricity = float(f"0.{l2[26:33].strip() or '0'}")
    arg_perigee = num(l2, 34, 42)
    mean_anomaly = num(l2, 43, 51)
    mean_motion = num(l2, 52, 63)  # revs / day
    period_min = 1440.0 / mean_motion if mean_motion > 0 else 0.0
    semi_major = ((398600.4418 / ((2 * math.pi * mean_motion) / 86400) ** 2)) ** (1 / 3) if mean_motion > 0 else 0.0
    perigee_alt = semi_major * (1 - eccentricity) - 6371.0
    apogee_alt = semi_major * (1 + eccentricity) - 6371.0
    epoch_str = l1[18:32].strip()  # YYDDD.DDDDDDDD
    try:
        yy, ddd = epoch_str[:2], epoch_str[2:]
        epoch = datetime.strptime(
            f"{2000 + int(yy)} {ddd}", "%Y %j.%f"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        epoch = None

    return {
        "inclination_deg": round(inclination, 2),
        "raan_deg": round(raan, 2),
        "eccentricity": eccentricity,
        "arg_perigee_deg": round(arg_perigee, 2),
        "mean_anomaly_deg": round(mean_anomaly, 2),
        "mean_motion_revs_per_day": round(mean_motion, 4),
        "period_minutes": round(period_min, 1),
        "perigee_alt_km": round(perigee_alt, 0),
        "apogee_alt_km": round(apogee_alt, 0),
        "epoch": epoch.isoformat() if epoch else None,
        "tle_line1": l1,
        "tle_line2": l2,
    }


@router.get("/{norad_id}")
def get_satellite_detail(norad_id: int, db: Session = Depends(get_db)):
    """Full satellite dossier: identity, orbit, latest position, recent track."""
    sat = db.query(Satellite).filter(Satellite.norad_id == norad_id).first()
    if sat is None:
        raise HTTPException(status_code=404, detail="Satellite not found")

    latest = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.satellite_id == sat.id)
        .order_by(SatelliteObservation.timestamp.desc())
        .first()
    )
    track_rows = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.satellite_id == sat.id)
        .order_by(SatelliteObservation.timestamp.asc())
        .limit(48)
        .all()
    )

    track = []
    for obs in track_rows:
        wkt = db.scalar(geo_func.ST_AsText(obs.position))
        try:
            nums = re.findall(r"-?\d+\.?\d*(?:e[-+]?\d+)?", wkt or "")
            track.append(
                {
                    "time": obs.timestamp.isoformat(),
                    "lat": float(nums[1]),
                    "lon": float(nums[0]),
                    "alt_km": float(nums[2]) if len(nums) > 2 else obs.altitude_km,
                }
            )
        except (ValueError, IndexError, TypeError):
            continue

    position = track[-1] if track else None

    return {
        "norad_id": sat.norad_id,
        "name": sat.name,
        "category": sat.category or "other",
        "position": position,
        "observations": len(track_rows),
        "orbit": _orbit_from_tle(sat.tle_line1 or "", sat.tle_line2 or "")
        if sat.tle_line1 and sat.tle_line2
        else None,
        "track": track,
    }


