"""Generate a geo-realistic SkyNexus demo dataset.

Creates real airports per region, plausible great-circle routes, staged
flight observations that animate along those routes, varied weather
(storms in some regions), security events in hotspots and satellites
with inclined ground tracks. Everything is positioned where it should
be on the globe so the dashboard looks alive.
"""

import argparse
import logging
import math
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from geoalchemy2.shape import to_shape
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.data.seed_regions import REGIONS, upsert_regions
from app.models.aviation import (
    Airport,
    Event,
    FlightObservation,
    FlightRoute,
    Region,
    Satellite,
    SatelliteObservation,
    WeatherObservation,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("demo_dataset")

random.seed(42)

# Per-region scenario knobs: storm level, event pressure, traffic weight.
SCENARIO = {
    "Middle East": {"storm": 65.0, "events": 3, "traffic": 3},
    "Eastern Europe": {"storm": 10.0, "events": 1, "traffic": 2},
    "South China Sea": {"storm": 35.0, "events": 2, "traffic": 2},
    "North Atlantic": {"storm": 20.0, "events": 0, "traffic": 3},
    "Pacific": {"storm": 5.0, "events": 0, "traffic": 1},
}

# Plausible hub airports: (iata, name, lat, lon) per region name.
AIRPORTS = {
    "Middle East": [
        ("DXB", "Dubai Intl", 25.2532, 55.3657),
        ("DOH", "Hamad Intl", 25.2731, 51.6081),
        ("RUH", "King Khalid Intl", 24.9576, 46.6988),
    ],
    "Eastern Europe": [
        ("WAW", "Warsaw Chopin", 52.1657, 20.9671),
        ("OTP", "Bucharest Henri Coanda", 44.5711, 26.0850),
        ("BUD", "Budapest Ferenc Liszt", 47.4369, 19.2556),
    ],
    "South China Sea": [
        ("SIN", "Singapore Changi", 1.3644, 103.9915),
        ("HKG", "Hong Kong Intl", 22.3080, 113.9185),
        ("MNL", "Manila Ninoy Aquino", 14.5086, 121.0198),
    ],
    "North Atlantic": [
        ("JFK", "New York JFK", 40.6413, -73.7781),
        ("LHR", "London Heathrow", 51.4700, -0.4543),
        ("KEF", "Keflavik Intl", 63.9850, -22.6056),
    ],
    "Pacific": [
        ("HNL", "Honolulu Daniel K. Inouye", 21.3187, -157.9224),
        ("NRT", "Tokyo Narita", 35.7719, 140.3929),
        ("SYD", "Sydney Kingsford Smith", -33.9399, 151.1753),
    ],
}

EVENT_TEMPLATES = [
    ("Airspace Restriction", "Security", "High", "Emergency airspace restriction (NOTAM) issued"),
    ("Military Exercise", "Military", "Medium", "Live-fire exercise area active — overflights rerouted"),
    ("GPS Jamming Report", "Cyber", "Medium", "Multiple GNSS interference reports from civil aviation"),
    ("Airport Closure", "Infrastructure", "High", "Runway closed for emergency repairs"),
    ("Diplomatic Tension", "Political", "Low", "Border tensions elevate regional risk assessment"),
]

SATELLITES = [
    (25544, "ISS (ZARYA)", 51.6),
    (48274, "STARLINK-1130", 53.0),
    (43205, "SENTINEL-6A", 66.0),
    (29155, "NOAA-19", 99.0),
    (37849, "TERRA", 98.2),
]


def lat_lon_to_wkt(lat: float, lon: float) -> str:
    return f"POINT({lon} {lat})"


def jitter_point(lat: float, lon: float, spread_deg: float) -> tuple[float, float]:
    return (
        max(-85.0, min(85.0, lat + random.uniform(-spread_deg, spread_deg))),
        (lon + random.uniform(-spread_deg, spread_deg) + 180) % 360 - 180,
    )


def great_circle_point(
    lat1: float, lon1: float, lat2: float, lon2: float, f: float
) -> tuple[float, float]:
    """Interpolate along the great circle between two points."""
    phi1, lam1, phi2, lam2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = (
        2
        * math.asin(
            math.sqrt(
                math.sin((phi2 - phi1) / 2) ** 2
                + math.cos(phi1) * math.cos(phi2) * math.sin((lam2 - lam1) / 2) ** 2
            )
        )
    )
    if d == 0:
        return lat1, lon1
    a = math.sin((1 - f) * d) / math.sin(d)
    b = math.sin(f * d) / math.sin(d)
    x = a * math.cos(phi1) * math.cos(lam1) + b * math.cos(phi2) * math.cos(lam2)
    y = a * math.cos(phi1) * math.sin(lam1) + b * math.cos(phi2) * math.sin(lam2)
    z = a * math.sin(phi1) + b * math.sin(phi2)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def reset_database():
    logger.info("Clearing demo data (schema is managed by alembic)...")
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                TRUNCATE flight_observations, flight_routes, weather_observations,
                         satellite_observations, events, airports, satellites,
                         disruption_index, forecasts, what_changed_reports
                RESTART IDENTITY CASCADE
                """
            )
        )
        db.commit()
        logger.info("Data tables cleared.")
    finally:
        db.close()


def seed_airports_and_routes(db: Session) -> dict[str, list[Airport]]:
    logger.info("Seeding airports and routes...")
    region_map = {r.name: r for r in db.query(Region).all()}
    region_airports: dict[str, list[Airport]] = {}

    for region_name, hubs in AIRPORTS.items():
        region = region_map.get(region_name)
        if region is None:
            continue
        airports = []
        for iata, name, lat, lon in hubs:
            airport = (
                db.query(Airport).filter(Airport.iata_code == iata).first()
            )
            if airport is None:
                airport = Airport(
                    iata_code=iata,
                    name=name,
                    geom=lat_lon_to_wkt(lat, lon),
                    region_id=region.id,
                )
                db.add(airport)
            airports.append(airport)
        region_airports[region_name] = airports
    db.commit()
    return region_airports


def generate_flights(db: Session, region_airports: dict[str, list[Airport]]):
    logger.info("Generating flight routes and observations...")
    now = datetime.now(timezone.utc)

    for region_name, airports in region_airports.items():
        region = db.query(Region).filter(Region.name == region_name).first()
        if region is None or len(airports) < 2:
            continue
        scenario = SCENARIO.get(region_name, {"traffic": 1})

        # hub routes: first airport to each other airport
        for dest in airports[1:]:
            route = FlightRoute(
                origin_airport_id=airports[0].id,
                dest_airport_id=dest.id,
                region_id=region.id,
            )
            db.add(route)
            db.flush()

            o = db.get(Airport, route.origin_airport_id)
            d = db.get(Airport, route.dest_airport_id)
            n_flights = scenario["traffic"]
            for i in range(n_flights):
                progress = random.uniform(0.15, 0.85)
                t0 = now - timedelta(hours=6) + timedelta(minutes=15 * i)
                for step in range(8):
                    p = min(1.0, progress + step * 0.02)
                    lat_s, lon_s = great_circle_point(
                        _airport_lat(o), _airport_lon(o), _airport_lat(d), _airport_lon(d), p
                    )
                    db.add(
                        FlightObservation(
                            route_id=route.id,
                            callsign=f"SKY{random.randint(100,999)}",
                            icao24=f"{random.randint(0, 0xFFFFFF):06X}",
                            timestamp=t0 + timedelta(minutes=5 * step),
                            position=lat_lon_to_wkt(lat_s, lon_s),
                            altitude_ft=random.randint(30000, 41000),
                            speed_kt=random.uniform(430, 510),
                            heading_deg=random.uniform(0, 360),
                            source="demo_dataset",
                        )
                    )
        db.commit()

    # Backfill a 7-day low-volume baseline so anomaly scoring has signal,
    # concentrating extra flights in the last 24h in "high traffic" regions.
    for region_name, airports in region_airports.items():
        region = db.query(Region).filter(Region.name == region_name).first()
        routes = (
            db.query(FlightRoute).filter(FlightRoute.region_id == region.id).all()
            if region
            else []
        )
        if not routes:
            continue
        for day in range(7, 0, -1):
            for route in routes:
                o = db.get(Airport, route.origin_airport_id)
                d = db.get(Airport, route.dest_airport_id)
                for _ in range(2):
                    lat, lon = great_circle_point(
                        _airport_lat(o), _airport_lon(o), _airport_lat(d), _airport_lon(d),
                        random.uniform(0.1, 0.9),
                    )
                    db.add(
                        FlightObservation(
                            route_id=route.id,
                            callsign=f"SKY{random.randint(100,999)}",
                            icao24=f"{random.randint(0, 0xFFFFFF):06X}",
                            timestamp=now - timedelta(days=day, hours=random.randint(0, 20)),
                            position=lat_lon_to_wkt(lat, lon),
                            altitude_ft=random.randint(30000, 41000),
                            speed_kt=random.uniform(430, 510),
                            heading_deg=random.uniform(0, 360),
                            source="demo_dataset",
                        )
                    )
    db.commit()


def _airport_lat(airport: Airport) -> float:
    return float(to_shape(airport.geom).y)


def _airport_lon(airport: Airport) -> float:
    return float(to_shape(airport.geom).x)


def generate_weather(db: Session):
    logger.info("Generating weather observations...")
    now = datetime.now(timezone.utc)
    regions = db.query(Region).all()
    for region in regions:
        storm = SCENARIO.get(region.name, {"storm": 10.0})["storm"]
        centroid_wkt = db.execute(
            text("SELECT ST_AsText(centroid) FROM regions WHERE id = :id"),
            {"id": str(region.id)},
        ).scalar()
        try:
            lon_s, lat_s = (
                centroid_wkt.replace("POINT(", "").replace(")", "").split()
            )
            base_lat, base_lon = float(lat_s), float(lon_s)
        except (ValueError, AttributeError):
            base_lat, base_lon = 0.0, 0.0

        for day in range(8):
            for _ in range(6):
                lat, lon = jitter_point(base_lat, base_lon, 6.0)
                ts = now - timedelta(days=day, hours=random.randint(0, 12))
                # Recent hours in stormy regions get a rising storm index so
                # the what-changed comparison shows a weather escalation.
                boost = 1.0 if day > 0 else random.uniform(1.0, 1.6)
                db.add(
                    WeatherObservation(
                        region_id=region.id,
                        timestamp=ts,
                        position=lat_lon_to_wkt(lat, lon),
                        wind_speed_kt=max(
                            0.0, random.gauss(12 + storm * 0.25, 4)
                        ),
                        precipitation_mm=max(
                            0.0, random.gauss(storm * 0.3, 2.0)
                        ),
                        storm_index=max(
                            0.0, random.gauss(storm * boost, storm * 0.15 + 1)
                        ),
                        source="demo_dataset",
                    )
                )
    db.commit()


def generate_events(db: Session):
    logger.info("Generating events...")
    now = datetime.now(timezone.utc)
    regions = db.query(Region).all()
    for region in regions:
        count = SCENARIO.get(region.name, {"events": 0})["events"]
        centroid_wkt = db.execute(
            text("SELECT ST_AsText(centroid) FROM regions WHERE id = :id"),
            {"id": str(region.id)},
        ).scalar()
        try:
            lon_s, lat_s = centroid_wkt.replace("POINT(", "").replace(")", "").split()
            base_lat, base_lon = float(lat_s), float(lon_s)
        except (ValueError, AttributeError):
            base_lat, base_lon = 0.0, 0.0

        for i in range(count):
            etype, category, severity, description = random.choice(EVENT_TEMPLATES)
            lat, lon = jitter_point(base_lat, base_lon, 5.0)
            db.add(
                Event(
                    external_id=f"DEMO-{region.name[:3].upper()}-{i:02d}",
                    event_date=now - timedelta(hours=random.randint(2, 30)),
                    event_type=etype,
                    category=category,
                    severity=severity,
                    position=lat_lon_to_wkt(lat, lon),
                    region_id=region.id,
                    description=description,
                    source="demo_dataset",
                )
            )
    db.commit()


def generate_satellites(db: Session):
    logger.info("Generating satellites and ground tracks...")
    now = datetime.now(timezone.utc)
    for norad, name, inclination in SATELLITES:
        sat = db.query(Satellite).filter(Satellite.norad_id == norad).first()
        if sat is None:
            sat = Satellite(
                norad_id=norad,
                name=name,
                tle_line1=f"1 {norad}U 58002B   26273.51782528  .00016717  00000-0  10270-3 0  9993",
                tle_line2=f"2 {norad}  {inclination:8.4f} 143.7260 852874.3649 13.56868233 295.49316902 15.54240726284500",
            )
            db.add(sat)
            db.flush()

        altitude_km = 420.0 if norad == 25544 else random.uniform(500, 850)
        for step in range(24):
            t = now + timedelta(minutes=4 * step)
            lat = inclination * math.sin(math.radians(step * 15))
            lon = ((step * 15) * 1.5 - 180) % 360 - 180
            db.add(
                SatelliteObservation(
                    satellite_id=sat.id,
                    timestamp=t,
                    position=f"POINTZ({lon} {lat} {altitude_km})",
                    altitude_km=altitude_km + random.uniform(-2, 2),
                    source="demo_dataset",
                )
            )
    db.commit()


def main():
    parser = argparse.ArgumentParser(description="Generate SkyNexus demo dataset")
    parser.add_argument("--reset", action="store_true", help="Clear existing data first")
    parser.add_argument("--seed-regions", action="store_true", help="Also (re)seed regions")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    if args.seed_regions or args.reset:
        upsert_regions()

    db = SessionLocal()
    try:
        region_airports = seed_airports_and_routes(db)
        generate_flights(db, region_airports)
        generate_weather(db)
        generate_events(db)
        generate_satellites(db)

        print("Demo dataset summary:")
        print(f"  Airports:   {db.query(Airport).count()}")
        print(f"  Routes:     {db.query(FlightRoute).count()}")
        print(f"  Flights:    {db.query(FlightObservation).count()}")
        print(f"  Satellites: {db.query(Satellite).count()}")
        print(f"  Sat obs:    {db.query(SatelliteObservation).count()}")
        print(f"  Weather:    {db.query(WeatherObservation).count()}")
        print(f"  Events:     {db.query(Event).count()}")
    finally:
        db.close()
    logger.info("Demo dataset generation complete.")


if __name__ == "__main__":
    main()
