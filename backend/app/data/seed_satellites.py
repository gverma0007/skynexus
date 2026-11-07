"""Seed baseline satellite catalogue with valid TLEs and live orbits.

Ensures the satellites table and live orbits are always populated across
crewed stations, weather, science, navigation, earth observation, and comms,
even when external Celestrak feeds are rate-limited or unreachable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.aviation import Satellite, SatelliteObservation
from app.services.orbits import make_tle, propagate

logger = logging.getLogger("seed_satellites")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# (name prefix, category, count, inclination, mean motion rev/day, ecc, first NORAD)
BASELINE_CONSTELLATIONS = [
    ("ISS (ZARYA)", "station", 1, 51.64, 15.50, 0.0004, 25544),
    ("CSS (TIANHE)", "station", 1, 41.47, 15.60, 0.0005, 48274),
    ("NOAA", "weather", 8, 98.9, 14.13, 0.0012, 33591),
    ("METOP", "weather", 6, 98.7, 14.21, 0.0002, 38771),
    ("GOES", "weather", 4, 0.05, 1.0027, 0.0001, 51850),
    ("HUBBLE SPACE TELESCOPE", "science", 1, 28.47, 15.14, 0.0002, 20580),
    ("SWIFT", "science", 1, 20.56, 15.25, 0.0009, 28485),
    ("SARSAT", "science", 12, 98.6, 14.2, 0.0011, 40069),
    ("GPS BIIF", "nav", 24, 55.0, 2.0057, 0.009, 39166),
    ("GALILEO", "nav", 24, 56.0, 1.7048, 0.0003, 49809),
    ("FLOCK 4X", "earthobs", 40, 97.5, 15.22, 0.0008, 56170),
    ("SENTINEL", "earthobs", 12, 98.6, 14.31, 0.0001, 40697),
    ("STARLINK", "comms", 60, 53.05, 15.06, 0.0001, 57900),
    ("ONEWEB", "comms", 30, 87.9, 13.16, 0.0002, 51080),
    ("IRIDIUM", "comms", 24, 86.4, 14.34, 0.0002, 56720),
]


def upsert_baseline_satellites(db: Session) -> int:
    """Upsert baseline constellation satellites and initial ground observations."""
    now = datetime.now(timezone.utc)
    sat_records = []
    
    for prefix, category, count, inc, mm, ecc, first_norad in BASELINE_CONSTELLATIONS:
        planes = max(1, min(count, 6))
        for k in range(count):
            norad = first_norad + k
            label = prefix if count == 1 else f"{prefix}-{k + 1:02d}"
            raan = (360.0 / planes) * (k % planes)
            ma = (360.0 / max(1, count // planes)) * (k // planes)
            l1, l2 = make_tle(norad, inc, raan, ecc, 45.0, ma, mm, now)
            sat_records.append((norad, label, category, l1, l2))

    for norad, name, category, l1, l2 in sat_records:
        sat = db.query(Satellite).filter(Satellite.norad_id == norad).first()
        if sat is None:
            sat = Satellite(
                norad_id=norad, name=name, category=category,
                tle_line1=l1, tle_line2=l2,
            )
            db.add(sat)
            db.flush()
        else:
            sat.name = name
            sat.category = category
            sat.tle_line1 = l1
            sat.tle_line2 = l2
            db.flush()

        # Seed initial observation steps so ground track and overhead checks are immediately active
        for step in range(4):
            when = now + timedelta(minutes=step * 15)
            try:
                lat, lon, alt, _ = propagate(l1, l2, when)
            except ValueError:
                continue
            db.add(
                SatelliteObservation(
                    satellite_id=sat.id,
                    timestamp=when,
                    position=f"POINTZ({lon:.4f} {lat:.4f} {alt:.1f})",
                    altitude_km=alt,
                    source="baseline",
                )
            )

    db.commit()
    logger.info("Successfully seeded %d baseline satellites", len(sat_records))
    return len(sat_records)


def main():
    db = SessionLocal()
    try:
        count = upsert_baseline_satellites(db)
        print(f"[skynexus] seeded {count} baseline satellites")
    finally:
        db.close()


if __name__ == "__main__":
    main()

