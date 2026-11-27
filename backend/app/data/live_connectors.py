"""Live data connectors for SkyNexus.

Sources (all free, no API keys):
- Flights:    adsb.lol v2 REST (military + civil point queries)
- Satellites: Celestrak TLEs + SGP4 propagation
- Weather:    Open-Meteo current conditions per region centroid
- Events:     USGS significant security & threat feeds (always on) — GDELT stays a
              future option since it 403s from many datacenter IPs.

Every connector is best-effort: failures are logged and skipped so the
scheduler keeps running.
"""

import json
import logging

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.geo import point_to_wkt
from app.services.satellites import CATEGORY_LABELS
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

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
CACHE_DIR = Path("/tmp/skynexus_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Celestrak group catalogs -> streamlined core constellations for fast,
# rate-limit-free tracking of ~200 real, active satellites across all missions.
SATELLITE_GROUPS: dict[str, tuple[int, str]] = {
    "stations": (20, "station"),
    "weather": (40, "weather"),
    "gps-ops": (32, "nav"),
    "galileo": (30, "nav"),
    "resource": (40, "earthobs"),
    "visual": (50, "science"),
}

# Regions likely to have live traffic; used for the adsb point queries.
# Multiple probe points per region widen coverage of each search circle.
REGION_QUERY_POINTS: dict[str, list[tuple[float, float]]] = {
    "Black Sea": [(44.0, 34.0), (42.0, 31.0), (43.5, 39.0)],
    "Red Sea": [(20.0, 38.5), (26.0, 35.5), (14.0, 42.5)],
    "Taiwan Strait": [(24.0, 120.0), (22.5, 120.5), (25.5, 121.5)],
    "Korean Peninsula": [(38.0, 127.5), (35.5, 128.5), (37.5, 126.8)],
    "Eastern Mediterranean": [(34.0, 30.0), (35.5, 34.0), (32.5, 34.5)],
    "Baltic Sea": [(57.0, 20.0), (55.0, 16.0), (59.0, 21.0)],
    "Horn of Africa": [(10.0, 46.0), (11.5, 43.0), (8.0, 48.0)],
    "Bay of Bengal": [(13.0, 88.0), (17.5, 84.0), (10.0, 92.0)],
    "Caribbean": [(18.0, -73.0), (14.0, -68.0), (22.0, -78.0)],
    "Gulf of Guinea": [(3.0, 5.0), (5.5, 0.0), (2.0, 8.5)],
    "India-Pakistan Border": [(31.5, 74.3), (28.6, 77.1), (33.6, 73.0)],
    "Middle East": [
        (25.0, 47.5), (25.2, 55.3), (29.2, 47.9),
        (21.5, 39.2),   # Jeddah
        (32.0, 34.9),   # Tel Aviv
        (33.3, 44.4),   # Baghdad
        (35.7, 51.4),   # Tehran
        (40.4, 49.9),   # Baku
    ],
    "Eastern Europe": [
        (50.0, 32.5), (52.1, 20.9), (44.4, 26.1),
        (47.4, 19.3),   # Budapest
        (50.4, 30.5),   # Kyiv
        (54.7, 25.3),   # Vilnius
        (46.0, 21.9),   # Timisoara
        (59.4, 24.8),   # Tallinn
    ],
    "South China Sea": [
        (14.5, 120.5),  # Manila
        (10.8, 106.7),  # Ho Chi Minh
        (16.0, 108.2),  # Da Nang
        (12.5, 112.5), (1.36, 103.99), (22.3, 113.9),
    ],
    "North Atlantic": [
        (53.0, -9.5),   # West Ireland / Shannon
        (38.7, -27.2),  # Azores
        (46.2, -60.2),  # Nova Scotia
        (45.0, -25.0), (63.98, -22.6),
    ],
    "Pacific": [
        (21.3, -157.9),   # Honolulu
        (19.7, -155.1),   # Hilo
        (8.0, -165.0),    # zone centre
    ],
}

# ADS-B search radius (nm, max 250 for adsb.fi & adsb.lol v2) and per-region cap.
ADSB_RADIUS_NM = 250
ADSB_MAX_PER_REGION = 500

# Nearest major airport per region — ADS-B gives positions, not routes, so
# live observations are attached to routes from these hubs.
ROUTE_ANCHOR_IATA: dict[str, str] = {
    "Middle East": "DXB",
    "Eastern Europe": "WAW",
    "South China Sea": "SIN",
    "North Atlantic": "LHR",
    "Pacific": "HNL",
}

# Nearest hub per extended zone - route context for live aircraft there.
ZONE_ANCHOR_IATA: dict[str, str] = {
    "Black Sea": "WAW",
    "Red Sea": "DXB",
    "Taiwan Strait": "SIN",
    "Korean Peninsula": "NRT",
    "Eastern Mediterranean": "DXB",
    "Baltic Sea": "WAW",
    "Horn of Africa": "DXB",
    "Bay of Bengal": "SIN",
    "Caribbean": "JFK",
    "Gulf of Guinea": "LHR",
    "India-Pakistan Border": "DEL",
}


def _nearest_airport(db: Session, region: Region) -> Airport | None:
    anchor_iata = ROUTE_ANCHOR_IATA.get(region.name) or ZONE_ANCHOR_IATA.get(
        region.name
    )
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


# ---------------------------------------------------------------- flights --
_opensky_token: str | None = None
_opensky_token_expiry: float = 0.0


def _get_opensky_auth_header() -> dict[str, str]:
    global _opensky_token, _opensky_token_expiry
    from app.core.config import get_settings
    st = get_settings()
    client_id = st.OPENSKY_CLIENT_ID or st.OPENSKY_USERNAME
    client_secret = st.OPENSKY_CLIENT_SECRET or st.OPENSKY_PASSWORD
    if not client_id or not client_secret:
        return {}
    now = time.time()
    if _opensky_token and now < _opensky_token_expiry:
        return {"Authorization": f"Bearer {_opensky_token}"}
    try:
        res = httpx.post(
            "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        if res.status_code == 200:
            data = res.json()
            _opensky_token = data.get("access_token")
            expires_in = data.get("expires_in", 1800)
            _opensky_token_expiry = now + max(60, expires_in - 120)
            return {"Authorization": f"Bearer {_opensky_token}"}
        logger.warning("OpenSky OAuth token rejected: HTTP %s", res.status_code)
    except Exception as exc:
        logger.warning("OpenSky OAuth token error: %s", exc)
    return {}


def _collect_adsb_items(
    aircraft_by_hex: dict[str, dict],
    items: list[dict],
    source: str,
    shapes: list[dict],
    default_callsign: str = "",
) -> int:
    """Parse adsb.lol / adsb.fi aircraft dicts into aircraft_by_hex."""
    from app.services.geo import region_for

    added = 0
    for ac in items:
        hex_id = (ac.get("hex") or "").strip().lower()
        if not hex_id or "lat" not in ac or "lon" not in ac or hex_id in aircraft_by_hex:
            continue
        reg = region_for(shapes, float(ac["lat"]), float(ac["lon"]))
        if not reg:
            continue
        alt = ac.get("alt_baro")
        aircraft_by_hex[hex_id] = {
            "lat": float(ac["lat"]),
            "lon": float(ac["lon"]),
            "callsign": (ac.get("flight") or ac.get("r") or "").strip() or default_callsign,
            "alt_ft": int(alt) if isinstance(alt, (int, float)) else 0,
            "speed_kt": float(ac.get("gs") or 0.0),
            "heading_deg": float(ac.get("track") or 0.0),
            "source": source,
            "region_id": reg["id"],
                    "observed_at": datetime.fromtimestamp(s[3], timezone.utc) if isinstance(s[3], (int, float)) else now,
        }
        added += 1
    return added


def fetch_live_flights(db: Session, max_per_region: int = ADSB_MAX_PER_REGION) -> int:
    """Pull live aircraft positions from OpenSky Network (worldwide coverage),
    falling back to adsb.fi / adsb.lol across all monitored regions."""
    from app.services.geo import region_for, region_shapes

    shapes = region_shapes(db)
    aircraft_by_hex: dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    client = httpx.Client(timeout=35, headers=UA)
    auth_header = _get_opensky_auth_header()
    req_headers = {**UA, **auth_header} if auth_header else UA

    # 1. Primary: OpenSky Network worldwide snapshot (5,000-10,000+ live planes in 1 call)
    opensky_count = 0
    try:
        res = client.get("https://opensky-network.org/api/states/all", headers=req_headers)
        if res.status_code == 200:
            states = res.json().get("states", []) or []
            for s in states:
                if len(s) < 11:
                    continue
                hex_id = (s[0] or "").strip().lower()
                lon, lat = s[5], s[6]
                if not hex_id or lat is None or lon is None:
                    continue
                reg = region_for(shapes, float(lat), float(lon))
                if not reg:
                    continue
                alt_m = s[7]
                alt_ft = int(alt_m * 3.28084) if isinstance(alt_m, (int, float)) else 0
                spd_ms = s[9]
                spd_kt = round(float(spd_ms) * 1.94384, 1) if isinstance(spd_ms, (int, float)) else 0.0
                track = float(s[10]) if isinstance(s[10], (int, float)) else 0.0
                aircraft_by_hex[hex_id] = {
                    "lat": float(lat),
                    "lon": float(lon),
                    "callsign": (s[1] or "").strip(),
                    "alt_ft": alt_ft,
                    "speed_kt": spd_kt,
                    "heading_deg": track,
                    "source": "opensky",
                    "region_id": reg["id"],
                }
                opensky_count += 1
            logger.info("OpenSky tracked %d aircraft across monitored regions", opensky_count)
        else:
            logger.warning("OpenSky API returned HTTP %s", res.status_code)
    except Exception as exc:
        logger.warning("OpenSky fetch failed: %s", exc)

    # No uncontrolled multi-provider fanout: preserve free-provider daily quotas.
    if opensky_count == 0:
        res.raise_for_status() if 'res' in locals() else None
    client.close()

    per_region: dict[str, int] = {}
    new_obs: list[FlightObservation] = []
    for hex_id, ac in aircraft_by_hex.items():
        reg_id = ac.get("region_id")
        if not reg_id:
            continue
        if per_region.get(reg_id, 0) >= max_per_region:
            continue
        route = None  # A regional hub is not a verified aircraft route.
        new_obs.append(FlightObservation(
            route_id=route.id if route else None,
            callsign=ac["callsign"][:64] or "UNKNOWN",
            icao24=hex_id[:64],
            timestamp=ac.get("observed_at", now),
            position=point_to_wkt(ac["lon"], ac["lat"]),
            altitude_ft=ac["alt_ft"],
            speed_kt=ac["speed_kt"],
            heading_deg=ac["heading_deg"],
            source=ac.get("source", "opensky"),
        ))
        per_region[reg_id] = per_region.get(reg_id, 0) + 1
    if new_obs:
        db.add_all(new_obs)
    db.commit()
    total = len(new_obs)
    logger.info("Total live flights stored: %d across %d regions", total, len(per_region))
    return total


# ------------------------------------------------------------- satellites --
def _fetch_group_tles(
    max_per_group: dict[str, tuple[int, str]]
) -> list[tuple[str, int, str, str, str]]:
    """Fetch modern GP CSV records, cached for two hours; never truncate catalogue IDs."""
    import csv, io, json
    combined, seen = [], set()
    with httpx.Client(timeout=20, headers=UA) as client:
        for group, (take, category) in max_per_group.items():
            cache = CACHE_DIR / f"group_{group}.csv"
            if cache.exists() and datetime.now().timestamp()-cache.stat().st_mtime < 7200:
                content=cache.read_text()
            else:
                response=client.get('https://celestrak.org/NORAD/elements/gp.php',params={'GROUP':group,'FORMAT':'csv'})
                response.raise_for_status()
                content=response.text
                cache.write_text(content)
            count=0
            for row in csv.DictReader(io.StringIO(content)):
                norad=int(row['NORAD_CAT_ID'])
                if norad in seen: continue
                seen.add(norad)
                combined.append((row.get('OBJECT_NAME','Unknown')[:200],norad,json.dumps(row),'OMM',category))
                count+=1
                if count>=take: break
    return combined


def propagate_tle(tle_line1: str, tle_line2: str, when: datetime) -> tuple[float, float, float]:
    """SGP4 -> sub-satellite (lat, lon, alt_km), with a correct GMST rotation."""
    from app.services.orbits import propagate

    lat, lon, alt, _ = propagate(tle_line1, tle_line2, when)
    return lat, lon, alt


def fetch_satellite_positions(db: Session, steps: int = 3, step_minutes: int = 10) -> int:
    """Propagate the tracked constellation and store ground-track observations."""
    from sgp4.api import Satrec

    catalog = _fetch_group_tles(SATELLITE_GROUPS)
    if not catalog:
        stored = db.execute(text("SELECT name, norad_id, tle_line1, tle_line2, COALESCE(category, 'other') FROM satellites s WHERE EXISTS (SELECT 1 FROM satellite_observations o WHERE o.satellite_id=s.id AND o.source='celestrak')")).all()
        catalog = [(r[0], r[1], r[2], r[3], r[4]) for r in stored if r[2] and r[3]]
        logger.info("Celestrak offline or empty; fell back to %d stored satellites", len(catalog))
    else:
        logger.info("Tracking %d satellites from %d groups", len(catalog), len(SATELLITE_GROUPS))

    now = datetime.now(timezone.utc)
    # Preload existing satellites in one query to eliminate per-satellite roundtrips
    existing_sats = {s.norad_id: s for s in db.query(Satellite).all()}

    # Clear previous forecast window in one single bulk delete
    db.query(SatelliteObservation).filter(
        SatelliteObservation.timestamp >= now - timedelta(minutes=step_minutes),
        SatelliteObservation.source == "celestrak",
    ).delete(synchronize_session=False)

    new_obs = []
    for name, norad, l1, l2, category in catalog:
        sat = existing_sats.get(norad)
        if sat is None:
            sat = Satellite(
                norad_id=norad, name=name, category=category,
                tle_line1=l1, tle_line2=l2,
            )
            db.add(sat)
            db.flush()
            existing_sats[norad] = sat
        else:
            sat.name, sat.category = name, category
            sat.tle_line1, sat.tle_line2 = l1, l2

        try:
            __import__("app.services.orbits", fromlist=["satrec"]).satrec(l1, l2)
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
            new_obs.append(
                SatelliteObservation(
                    satellite_id=sat.id,
                    timestamp=when,
                    position=f"POINTZ({lon:.4f} {lat:.4f} {alt:.1f})",
                    altitude_km=alt,
                    source="celestrak",
                )
            )

    if new_obs:
        db.add_all(new_obs)
    db.commit()
    logger.info("Satellite propagation completed: %d observations stored", len(new_obs))
    return len(new_obs)


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
    from app.services.geo import region_shapes

    shapes = region_shapes(db)
    if not shapes:
        return 0

    total = 0
    client = httpx.Client(timeout=20, headers=UA)
    now = datetime.now(timezone.utc)
    try:
        lats = ",".join(f"{s['lat']:.4f}" for s in shapes)
        lons = ",".join(f"{s['lon']:.4f}" for s in shapes)
        res = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lats,
                "longitude": lons,
                "current": "wind_speed_10m,precipitation,wind_gusts_10m",
            },
        )
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else [data]
            obs = []
            for s, item in zip(shapes, items):
                cur = item.get("current", {})
                wind_kmh = float(cur.get("wind_speed_10m", 0) or 0)
                gust_kmh = float(cur.get("wind_gusts_10m", 0) or 0)
                precip = float(cur.get("precipitation", 0) or 0)
                obs.append(
                    WeatherObservation(
                        region_id=s["id"],
                        timestamp=now,
                        position=point_to_wkt(s["lon"], s["lat"]),
                        wind_speed_kt=wind_kmh * 0.539957,
                        precipitation_mm=precip,
                        storm_index=_storm_index(wind_kmh, gust_kmh, precip),
                        source="open-meteo",
                    )
                )
            if obs:
                db.add_all(obs)
            db.commit()
            total = len(obs)
            logger.info("Open-Meteo recorded %d live weather observations", total)
        else:
            logger.warning("Open-Meteo batch returned status %s", res.status_code)
    except Exception as exc:
        logger.warning("Open-Meteo batch fetch failed: %s", exc)
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
    "significant": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
    "M2.5_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson",
    "all_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
}


def _quake_region(db: Session, lat: float, lon: float) -> Region | None:
    """Region whose polygon contains the epicentre (smallest zone wins)."""
    from app.services.geo import region_for, region_shapes

    reg = region_for(region_shapes(db), lat, lon)
    return db.get(Region, reg["id"]) if reg else None


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
                        category="Natural hazard",
                        severity="High" if mag >= 5.5 else "Medium" if mag >= 4 else "Low",
                        position=point_to_wkt(lon, lat),
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
def prune_old_observations(days: int | None = None) -> int:
    """Archive a bounded batch before pruning live observations."""
    from app.core.config import get_settings

    days = int(days or get_settings().RETENTION_DAYS)
    db = SessionLocal()
    try:
        from app.services.retention import archive_legacy
        removed=archive_legacy(db,datetime.now(timezone.utc)-timedelta(days=days))
        db.commit()
        return removed
    finally:
        db.close()


def run_live_ingestion(steps: int = 6) -> dict:
    """Run every connector once. Returns per-source counts."""
    db = SessionLocal()
    summary: dict[str, int] = {}
    steps_map = (
        ("flights", lambda: fetch_live_flights(db)),
        ("satellite_obs", lambda: fetch_satellite_positions(db, steps=steps)),
        ("weather", lambda: fetch_live_weather(db)),
        ("events", lambda: fetch_live_events(db)),
    )
    try:
        for name, fn in steps_map:
            try:
                summary[name] = fn()
            except Exception as exc:  # one failing source must not stop the others
                db.rollback()
                logger.warning("%s connector failed: %s", name, exc)
                summary[name] = -1
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
    from app.services.ingest import run_cycle

    result = run_cycle(steps=args.steps)
    print("Live ingestion summary:", json.dumps(result, indent=2))
