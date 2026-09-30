"""Live data connectors for SkyNexus.

Sources (all free, no API keys):
- Flights:    adsb.lol v2 REST (military + civil point queries)
- Satellites: Celestrak TLEs + SGP4 propagation
- Weather:    Open-Meteo current conditions per region centroid
- Events:     USGS significant earthquakes (always on) — GDELT stays a
              future option since it 403s from many datacenter IPs.

Every connector is best-effort: failures are logged and skipped so the
scheduler keeps running.
"""

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
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

logger = logging.getLogger("connectors")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

UA = {"User-Agent": "SkyNexus-Prototype/1.0 (contact: demo@skynexus.local)"}
CACHE_DIR = Path("/tmp/skynexus_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Celestrak group catalogs -> how many to track from each, mapped to the
# satellite's functional category so the globe can group/filter by mission.
SATELLITE_GROUPS: dict[str, tuple[int, str]] = {
    "stations": (20, "station"),
    "weather": (20, "weather"),
    "science": (20, "science"),
    "gps-ops": (15, "nav"),
    "galileo": (15, "nav"),
    "planet": (30, "earthobs"),
    "starlink": (30, "comms"),
    "oneweb": (15, "comms"),
    "iridium-NEXT": (15, "comms"),
}

CATEGORY_LABELS: dict[str, str] = {
    "station": "Crewed station",
    "weather": "Weather",
    "science": "Science",
    "nav": "Navigation",
    "earthobs": "Earth observation",
    "comms": "Communications",
}

# Legacy list kept for TLE cache naming of the old five.
TRACKED_SATELLITES = [25544, 48274, 43205, 29155, 37849]

# Regions likely to have live traffic; used for the adsb point queries.
# Multiple probe points per region widen coverage of each search circle.
REGION_QUERY_POINTS: dict[str, list[tuple[float, float]]] = {
    "Middle East": [
        (25.0, 47.5), (25.2, 55.3), (29.2, 47.9),
        (21.5, 39.2),   # Jeddah
        (32.0, 34.9),   # Tel Aviv
    ],
    "Eastern Europe": [
        (50.0, 32.5), (52.1, 20.9), (44.4, 26.1),
        (47.4, 19.3),   # Budapest
        (50.4, 30.5),   # Kyiv
    ],
    "South China Sea": [
        (12.5, 112.5), (1.36, 103.99), (22.3, 113.9),
        (14.5, 121.0),  # Manila
        (13.7, 100.5),  # Bangkok
    ],
    "North Atlantic": [
        (45.0, -25.0), (51.47, -0.45), (63.98, -22.6),
        (40.64, -73.78),  # New York
        (38.7, -9.1),     # Lisbon
    ],
    "Pacific": [
        (0.0, -170.0), (21.3, -157.9), (35.77, 140.39),
        (-33.94, 151.18),  # Sydney
        (37.5, 126.9),     # Seoul
    ],
}

# ADS-B search radius (nm) and per-region aircraft cap.
ADSB_RADIUS_NM = 400
ADSB_MAX_PER_REGION = 40

# Nearest major airport per region — ADS-B gives positions, not routes, so
# live observations are attached to routes from these hubs.
ROUTE_ANCHOR_IATA: dict[str, str] = {
    "Middle East": "DXB",
    "Eastern Europe": "WAW",
    "South China Sea": "SIN",
    "North Atlantic": "LHR",
    "Pacific": "HNL",
}


def _nearest_airport(db: Session, region: Region) -> Airport | None:
    anchor_iata = ROUTE_ANCHOR_IATA.get(region.name)
    if anchor_iata:
        airport = db.query(Airport).filter(Airport.iata_code == anchor_iata).first()
        if airport:
            return airport
    return db.query(Airport).filter(Airport.region_id == region.id).first()


def _route_for(db: Session, region: Region) -> FlightRoute | None:
    route = (
        db.query(FlightRoute).filter(FlightRoute.region_id == region.id).first()
    )
    if route:
        return route
    origin = _nearest_airport(db, region)
    if origin is None:
        return None
    dest = (
        db.query(Airport)
        .filter(Airport.id != origin.id, Airport.region_id == region.id)
        .first()
    )
    if dest is None:
        return None
    route = FlightRoute(
        origin_airport_id=origin.id, dest_airport_id=dest.id, region_id=region.id
    )
    db.add(route)
    db.commit()
    return route


def _point_to_wkt(lon: float, lat: float) -> str:
    return f"POINT({lon} {lat})"


# ---------------------------------------------------------------- flights --
def fetch_live_flights(db: Session, max_per_region: int = ADSB_MAX_PER_REGION) -> int:
    """Pull live ADS-B positions per region and store the fastest climbers."""
    total = 0
    client = httpx.Client(timeout=20, headers=UA)
    try:
        for region in db.query(Region).all():
            points = REGION_QUERY_POINTS.get(region.name)
            if not points:
                continue
            route = _route_for(db, region)
            if route is None:
                continue

            # Probe several points per region, dedup by aircraft hex.
            aircraft_by_hex: dict[str, dict] = {}
            primary = points[0]
            for lat, lon in points:
                try:
                    res = client.get(
                        f"https://api.adsb.lol/v2/point/{lat}/{lon}/{ADSB_RADIUS_NM}"
                    )
                    if res.status_code == 200:
                        for ac in res.json().get("ac", []) or []:
                            hex_id = (ac.get("hex") or "").strip()
                            if hex_id:
                                aircraft_by_hex[hex_id] = ac
                except Exception as exc:
                    logger.warning("adsb.lol point %s failed: %s", (lat, lon), exc)

            # Fallback: military traffic feed (global, always on)
            if not aircraft_by_hex:
                try:
                    lat, lon = primary
                    res = client.get("https://api.adsb.lol/v2/mil")
                    if res.status_code == 200:
                        aircraft_by_hex = {
                            (ac.get("hex") or "").strip(): ac
                            for ac in (res.json().get("ac", []) or [])
                            if _haversine_km(
                                lat, lon, float(ac.get("lat", 0)), float(ac.get("lon", 0))
                            )
                            < 1500
                        }
                except Exception as exc:
                    logger.warning("adsb.lol mil failed: %s", exc)

            now = datetime.now(timezone.utc)
            for ac in list(aircraft_by_hex.values())[:max_per_region]:
                try:
                    db.add(
                        FlightObservation(
                            route_id=route.id,
                            callsign=(ac.get("flight") or ac.get("r") or "UNKNOWN").strip()[:64],
                            icao24=(ac.get("hex") or "000000").strip()[:64],
                            timestamp=now,
                            position=_point_to_wkt(float(ac["lon"]), float(ac["lat"])),
                            altitude_ft=int(ac.get("alt_baro", 30000))
                            if isinstance(ac.get("alt_baro"), int)
                            else 30000,
                            speed_kt=float(ac.get("gs", 0)) or 450.0,
                            heading_deg=float(ac.get("track", 0)) or 0.0,
                            source="adsb.lol",
                        )
                    )
                    total += 1
                except (KeyError, ValueError, TypeError):
                    continue
            db.commit()
    finally:
        client.close()
    return total


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ------------------------------------------------------------- satellites --
def _tle_cache_path(norad: int) -> Path:
    return CACHE_DIR / f"tle_{norad}.txt"


def _fetch_group_tles(
    max_per_group: dict[str, tuple[int, str]]
) -> list[tuple[str, int, str, str, str]]:
    """Fetch (name, norad, l1, l2, category) from Celestrak groups, cached 12h."""
    combined: list[tuple[str, int, str, str, str]] = []
    seen: set[int] = set()
    client = httpx.Client(timeout=30, headers=UA)
    try:
        for group, (take, category) in max_per_group.items():
            cache = CACHE_DIR / f"group_{group}.txt"
            lines: list[str] = []
            if cache.exists() and (
                datetime.now().timestamp() - cache.stat().st_mtime
            ) < 12 * 3600:
                lines = cache.read_text().splitlines()
            else:
                try:
                    res = client.get(
                        f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=TLE"
                    )
                    if res.status_code == 200 and "1 " in res.text:
                        lines = res.text.splitlines()
                        cache.write_text("\n".join(lines))
                    else:
                        logger.warning(
                            "Celestrak group %s -> HTTP %s", group, res.status_code
                        )
                except Exception as exc:
                    logger.warning("Celestrak group %s failed: %s", group, exc)

            # Parse 3-line records: name / line1 / line2
            taken = 0
            i = 0
            while i + 2 < len(lines) and taken < take:
                name = lines[i].strip()
                l1 = lines[i + 1].strip()
                l2 = lines[i + 2].strip()
                i += 3
                if not l1.startswith("1 ") or not l2.startswith("2 "):
                    continue
                try:
                    norad = int(l1[2:7])
                except ValueError:
                    continue
                if norad in seen or not name:
                    continue
                seen.add(norad)
                combined.append((name[:200], norad, l1, l2, category))
                taken += 1
    finally:
        client.close()
    return combined


def _gmst_deg(dt: datetime) -> float:
    """Greenwich mean sidereal time (approx, degrees)."""
    jd = (
        dt.timetuple().tm_yday
        + dt.hour / 24
        + dt.minute / 1440
        + dt.second / 86400
    )
    year = dt.year
    # JD at 0h UT (Fliegel-Van Flandern, adequate for a prototype)
    a = year // 100
    b = 2 - a + a // 4
    jd0 = (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * 1)
        + 2
        + b
        - 41845.0
        + 1720994.5
    )
    d = jd0 + jd - 2451545.0
    return (280.46061837 + 360.98564736629 * d) % 360


def propagate_tle(tle_line1: str, tle_line2: str, when: datetime) -> tuple[float, float, float]:
    """SGP4 -> sub-satellite (lat, lon, alt_km)."""
    from sgp4.api import Satrec, jday

    sat = Satrec.twoline2rv(tle_line1, tle_line2)
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, when.second)
    error, position_km, _ = sat.sgp4(jd, fr)
    if error != 0:
        raise ValueError(f"SGP4 error {error}")
    r = math.sqrt(sum(c * c for c in position_km))
    lat = math.degrees(math.asin(position_km[2] / r))
    ra = math.degrees(math.atan2(position_km[1], position_km[0]))
    lon = (ra - _gmst_deg(when) + 180) % 360 - 180
    return lat, lon, r - 6371.0


def fetch_satellite_positions(db: Session, steps: int = 6, step_minutes: int = 10) -> int:
    """Propagate the tracked constellation and store ground-track observations."""
    from sgp4.api import Satrec

    catalog = _fetch_group_tles(SATELLITE_GROUPS)
    logger.info("Tracking %d satellites from %d groups", len(catalog), len(SATELLITE_GROUPS))

    total = 0
    now = datetime.now(timezone.utc)
    for name, norad, l1, l2, category in catalog:
        sat = db.query(Satellite).filter(Satellite.norad_id == norad).first()
        if sat is None:
            sat = Satellite(
                norad_id=norad, name=name, category=category,
                tle_line1=l1, tle_line2=l2,
            )
            db.add(sat)
            db.flush()
        else:
            sat.name, sat.category = name, category
            sat.tle_line1, sat.tle_line2 = l1, l2

        try:
            satrec = Satrec.twoline2rv(l1, l2)
        except Exception as exc:
            logger.warning("Bad TLE for %s: %s", name, exc)
            continue

        # Spacecraft in view now + near-future ground track steps
        for step in range(steps):
            when = now + timedelta(minutes=step * step_minutes)
            try:
                lat, lon, alt = propagate_tle(l1, l2, when)
            except ValueError:
                continue
            db.add(
                SatelliteObservation(
                    satellite_id=sat.id,
                    timestamp=when,
                    position=f"POINTZ({lon} {lat} {alt})",
                    altitude_km=alt,
                    source=f"celestrak:{satrec.satnum}"[:50],
                )
            )
            total += 1
        db.commit()
    return total


# ---------------------------------------------------------------- weather --
def _region_latlon(db: Session, region: Region) -> tuple[float, float] | None:
    row = db.execute(
        text("SELECT ST_AsText(centroid) FROM regions WHERE id = :id"),
        {"id": str(region.id)},
    ).scalar()
    if not row:
        return None
    import re

    nums = re.findall(r"-?\d+\.?\d*", row)
    lon, lat = float(nums[0]), float(nums[1])
    return lat, lon


def fetch_live_weather(db: Session) -> int:
    """Current conditions at each region centroid -> storm index."""
    total = 0
    client = httpx.Client(timeout=20, headers=UA)
    try:
        for region in db.query(Region).all():
            point = _region_latlon(db, region)
            if not point:
                continue
            lat, lon = point
            try:
                res = client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "wind_speed_10m,precipitation,wind_gusts_10m",
                    },
                )
                res.raise_for_status()
                cur = res.json().get("current", {})
                wind_kmh = float(cur.get("wind_speed_10m", 0) or 0)
                gust_kmh = float(cur.get("wind_gusts_10m", 0) or 0)
                precip = float(cur.get("precipitation", 0) or 0)
                wind_kt = wind_kmh * 0.539957
                storm = _storm_index(wind_kmh, gust_kmh, precip)
                db.add(
                    WeatherObservation(
                        region_id=region.id,
                        timestamp=datetime.now(timezone.utc),
                        position=_point_to_wkt(lon, lat),
                        wind_speed_kt=wind_kt,
                        precipitation_mm=precip,
                        storm_index=storm,
                        source="open-meteo",
                    )
                )
                total += 1
            except Exception as exc:
                logger.warning("Open-Meteo failed for %s: %s", region.name, exc)
        db.commit()
    finally:
        client.close()
    return total


def _storm_index(wind_kmh: float, gust_kmh: float, precip_mm: float) -> float:
    wind = min(max(wind_kmh - 20, 0) * 1.2, 45)
    gust = min(max(gust_kmh - 35, 0) * 0.6, 25)
    rain = min(precip_mm * 6, 30)
    return round(min(100.0, wind + gust + rain), 1)


# ----------------------------------------------------------------- events --
USGS_FEEDS = {
    "significant": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
    "M2.5+": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
}


def _quake_region(db: Session, lat: float, lon: float) -> Region | None:
    """Point-in-polygon match, else nearest region centroid within 4000 km."""
    row = db.execute(
        text(
            """
            SELECT id FROM regions r
            WHERE ST_Contains(r.geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    ).first()
    if row:
        return db.get(Region, row[0])

    nearest = (
        db.query(Region)
        .order_by(
            func.ST_Distance(
                Region.centroid,
                func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
            )
        )
        .first()
    )
    if nearest is None:
        return None
    dist_m = db.scalar(
        func.ST_Distance(
            nearest.centroid,
            func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
        )
    )
    # centroids stored in degrees (4326): ~111km per degree
    if dist_m is not None and dist_m * 111.0 <= 4000:
        return nearest
    return None


def fetch_live_events(db: Session) -> int:
    """USGS quakes -> events (region-matched via PostGIS point-in-polygon)."""
    total = 0
    client = httpx.Client(timeout=20, headers=UA)
    try:
        seen = set(
            eid[0]
            for eid in db.query(Event.external_id)
            .filter(Event.source == "usgs")
            .all()
        )
        for feed_url in USGS_FEEDS.values():
            try:
                res = client.get(feed_url)
                res.raise_for_status()
                data = res.json()
            except Exception as exc:
                logger.warning("USGS feed failed: %s", exc)
                continue
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [])
                if len(coords) < 2:
                    continue
                lon, lat = float(coords[0]), float(coords[1])
                external_id = f"usgs-{feature.get('id', '')}"
                if external_id in seen:
                    continue
                region = _quake_region(db, lat, lon)
                if region is None:
                    continue  # outside monitored regions
                mag = float(props.get("mag") or 0)
                db.add(
                    Event(
                        external_id=external_id,
                        event_date=datetime.fromtimestamp(
                            props.get("time", 0) / 1000, tz=timezone.utc
                        ),
                        event_type="Earthquake",
                        category="Natural Hazard",
                        severity="High" if mag >= 5.5 else "Medium" if mag >= 4 else "Low",
                        position=_point_to_wkt(lon, lat),
                        region_id=region.id,
                        description=f"M{mag:.1f} earthquake — {props.get('place', 'unknown location')}",
                        source="usgs",
                    )
                )
                seen.add(external_id)
                total += 1
        db.commit()
    finally:
        client.close()
    return total


# -------------------------------------------------------------- entrypoint --
def prune_old_observations(days: int = 7) -> int:
    """Delete observations older than the retention window."""
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                DELETE FROM flight_observations
                WHERE timestamp < NOW() - INTERVAL ':days days'
                """.replace(":days", str(days))
            )
        )
        db.execute(
            text(
                """
                DELETE FROM satellite_observations
                WHERE timestamp < NOW() - INTERVAL ':days days'
                """.replace(":days", str(days))
            )
        )
        db.execute(
            text(
                """
                DELETE FROM weather_observations
                WHERE timestamp < NOW() - INTERVAL ':days days'
                """.replace(":days", str(days))
            )
        )
        db.commit()
        return result.rowcount or 0
    finally:
        db.close()


def run_live_ingestion(steps: int = 6) -> dict:
    """Run every connector once. Returns per-source counts."""
    db = SessionLocal()
    summary: dict[str, int] = {}
    try:
        summary["flights"] = fetch_live_flights(db)
        summary["satellite_obs"] = fetch_satellite_positions(db, steps=steps)
        summary["weather"] = fetch_live_weather(db)
        summary["events"] = fetch_live_events(db)
    finally:
        db.close()
    try:
        summary["pruned"] = prune_old_observations()
    except Exception as exc:
        logger.warning("Retention prune failed: %s", exc)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run one live ingestion cycle")
    parser.add_argument("--steps", type=int, default=6, help="satellite forecast steps")
    args = parser.parse_args()
    result = run_live_ingestion(steps=args.steps)
    print("Live ingestion summary:", json.dumps(result, indent=2))
