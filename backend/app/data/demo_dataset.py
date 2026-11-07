"""Generate an offline 8-day demo world for SkyNexus.

Everything the live connectors would produce, but synthetic and
reproducible (seeded):

- Hourly aircraft snapshots for all 15 regions with a day/night rhythm by
  local time, plus four scripted scenarios in the last hours:
    Red Sea              traffic surge (+60%, last 8 h) and M6.1 + M5.8 quakes
    Taiwan Strait        sharp traffic drop (-45%, last 6 h), the pattern of
                         an airspace restriction, with moderate quakes
    Eastern Mediterranean storm building to ~60 and traffic dipping 20%
                         (the weather-explained case)
    Korean Peninsula     mild surge (+18%) and an M4.2 quake
- Hourly weather per region, background conflict & threat events in conflict-prone zones.
- ~180 satellites with valid TLEs (realistic constellations), propagated
  with the same SGP4 code as live mode.

Rows are tagged source="demo_dataset". Run:
    python -m app.data.demo_dataset --reset
"""

from __future__ import annotations

import argparse
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from psycopg2.extras import execute_values
from sqlalchemy import text

from app.core.db import engine
from app.data.seed_airports import upsert_airports
from app.data.seed_regions import REGIONS, upsert_regions
from app.services.orbits import make_tle, propagate

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("demo_dataset")

HOURS = 8 * 24
SRC = "demo_dataset"

# Mean aircraft per hour at the daily peak, base storm level, quake activity.
PROFILE = {
    "Middle East": (240, 8, 0.15), "Eastern Europe": (170, 10, 0.05),
    "South China Sea": (210, 18, 0.20), "North Atlantic": (260, 22, 0.05),
    "Pacific": (60, 12, 0.25), "Black Sea": (90, 12, 0.08), "Red Sea": (100, 9, 0.10),
    "Taiwan Strait": (150, 14, 0.40), "Korean Peninsula": (170, 10, 0.20),
    "Eastern Mediterranean": (120, 14, 0.22), "Baltic Sea": (110, 16, 0.02),
    "Horn of Africa": (50, 8, 0.08), "Bay of Bengal": (100, 20, 0.06),
    "Caribbean": (130, 15, 0.16), "Gulf of Guinea": (70, 12, 0.02),
    "India-Pakistan Border": (180, 10, 0.20),
}

# (region, hours_back_start, multiplier) applied to traffic for the latest hours
TRAFFIC_SCENARIOS = {
    "Red Sea": (8, 1.6),
    "Taiwan Strait": (6, 0.55),
    "Eastern Mediterranean": (12, 0.80),
    "Korean Peninsula": (6, 1.18),
}
STORM_SCENARIOS = {"Eastern Mediterranean": (12, 60.0)}
SCRIPTED_QUAKES = [
    ("Red Sea", 1.5, 6.1, "110 km NE of Massawa, Eritrea", 16.4, 40.2),
    ("Red Sea", 3.2, 5.8, "62 km W of Jizan, Saudi Arabia", 16.95, 42.0),
    ("Red Sea", 9.0, 4.6, "southern Red Sea", 15.6, 41.2),
    ("Red Sea", 15.0, 4.1, "central Red Sea", 19.8, 38.9),
    ("Taiwan Strait", 5.0, 4.9, "31 km E of Hualien City, Taiwan", 23.98, 121.9),
    ("Taiwan Strait", 20.0, 4.3, "Taiwan Strait", 24.2, 119.6),
    ("Korean Peninsula", 7.0, 4.2, "Sea of Japan, 80 km E of Pohang", 36.0, 130.3),
]
QUAKE_PLACES = {
    "Taiwan Strait": (23.8, 121.6), "Korean Peninsula": (35.9, 129.6),
    "Eastern Mediterranean": (35.2, 26.5), "Pacific": (19.4, -155.3),
    "Caribbean": (18.3, -66.9), "South China Sea": (13.5, 119.8),
    "Black Sea": (40.9, 30.8), "Middle East": (27.5, 54.0), "Red Sea": (17.5, 40.8),
    "Horn of Africa": (11.6, 43.1), "Bay of Bengal": (20.5, 92.5),
    "India-Pakistan Border": (31.5, 74.3),
}

# (name prefix, category, count, inclination, mean motion rev/day, ecc, first NORAD)
CONSTELLATIONS = [
    ("ISS (ZARYA)", "station", 1, 51.64, 15.50, 0.0004, 25544),
    ("CSS (TIANHE)", "station", 1, 41.47, 15.60, 0.0005, 48274),
    ("NOAA", "weather", 16, 98.9, 14.13, 0.0012, 33591),
    ("METOP", "weather", 12, 98.7, 14.21, 0.0002, 38771),
    ("GOES", "weather", 8, 0.05, 1.0027, 0.0001, 51850),
    ("HUBBLE SPACE TELESCOPE", "science", 1, 28.47, 15.14, 0.0002, 20580),
    ("SWIFT", "science", 1, 20.56, 15.25, 0.0009, 28485),
    ("SARSAT", "science", 24, 98.6, 14.2, 0.0011, 40069),
    ("GPS BIIF", "nav", 32, 55.0, 2.0057, 0.009, 39166),
    ("GALILEO", "nav", 30, 56.0, 1.7048, 0.0003, 49809),
    ("FLOCK 4X", "earthobs", 180, 97.5, 15.22, 0.0008, 56170),
    ("SENTINEL", "earthobs", 24, 98.6, 14.31, 0.0001, 40697),
    ("STARLINK", "comms", 600, 53.05, 15.06, 0.0001, 57900),
    ("ONEWEB", "comms", 120, 87.9, 13.16, 0.0002, 51080),
    ("IRIDIUM", "comms", 66, 86.4, 14.34, 0.0002, 56720),
]


def _bbox(polygon):
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return min(lats), max(lats), min(lons), max(lons)


def _diurnal(hour_utc: int, lon: float) -> float:
    local = (hour_utc + lon / 15.0) % 24
    # quiet ~03:00 local, busy ~14:00 local
    return 0.55 + 0.45 * max(0.0, math.sin((local - 5.0) / 24.0 * 2 * math.pi)) ** 0.8


def reset_database():
    logger.info("Clearing observation data (schema and regions are kept)...")
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE flight_observations, weather_observations, satellite_observations, events, "
            "satellites, anomaly_scores, event_correlations, disruption_index, forecasts, "
            "what_changed_reports RESTART IDENTITY CASCADE"
        ))


def _route_per_region(conn) -> dict[str, str]:
    rows = conn.execute(text(
        "SELECT DISTINCT ON (r.name) r.name, fr.id::text FROM flight_routes fr "
        "JOIN regions r ON r.id = fr.region_id ORDER BY r.name, fr.id"
    )).all()
    return {name: rid for name, rid in rows}


def generate(rng: random.Random) -> dict:
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=h) for h in range(HOURS - 1, -1, -1)]
    counts = {"flights": 0, "weather": 0, "events": 0, "satellites": 0, "satellite_obs": 0}

    raw = engine.raw_connection()
    try:
        with engine.connect() as conn:
            routes = _route_per_region(conn)
            region_ids = dict(conn.execute(text("SELECT name, id::text FROM regions")).all())
        cur = raw.cursor()
        flights, weather, events = [], [], []

        for reg in REGIONS:
            name = reg["name"]
            if name not in routes:
                continue
            peak, storm_base, quake_rate = PROFILE.get(name, (40, 12, 0.05))
            lat0, lat1, lon0, lon1 = _bbox(reg["polygon"])
            clat, clon = reg["centroid"]
            storm = storm_base
            for idx, h in enumerate(hours):
                hours_back = HOURS - 1 - idx
                is_current = idx == len(hours) - 1
                rate = peak * _diurnal(h.hour, clon) * rng.gauss(1.0, 0.06)
                sc = TRAFFIC_SCENARIOS.get(name)
                if sc and hours_back < sc[0]:
                    ramp = min(1.0, (sc[0] - hours_back) / 2.0)
                    rate *= 1 + (sc[1] - 1) * ramp
                if is_current:
                    rate *= max(0.15, now.minute / 60.0)  # partial hour
                n = max(0, int(round(rate)))
                ts = now - timedelta(minutes=2) if is_current else h + timedelta(minutes=rng.randint(5, 55))
                for _ in range(n):
                    lat = rng.uniform(lat0, lat1)
                    lon = rng.uniform(lon0, lon1)
                    flights.append((
                        routes[name], f"{rng.choice(['UAE', 'QTR', 'SIA', 'BAW', 'DLH', 'THY', 'KAL', 'EVA', 'ETH', 'AAL'])}{rng.randint(10, 9999)}",
                        f"{rng.randint(0, 0xFFFFFF):06x}", ts, f"POINT({lon:.4f} {lat:.4f})",
                        rng.choice([0, 3000]) if rng.random() < 0.05 else rng.randint(24000, 41000),
                        rng.uniform(380, 520), rng.uniform(0, 360), SRC,
                    ))

                # weather: mean-reverting random walk + storm scenario
                storm += (storm_base - storm) * 0.15 + rng.gauss(0, 3.0)
                s_val = storm
                ss = STORM_SCENARIOS.get(name)
                if ss and hours_back < ss[0]:
                    s_val = storm + (ss[1] - storm) * min(1.0, (ss[0] - hours_back) / 8.0)
                s_val = max(0.0, min(100.0, s_val))
                weather.append((region_ids[name], h + timedelta(minutes=10), f"POINT({clon} {clat})",
                                max(0.0, 8 + s_val * 0.4 + rng.gauss(0, 2)),
                                max(0.0, s_val / 12 + rng.gauss(0, 0.5)), round(s_val, 1), SRC))

                # background quakes (Gutenberg-Richter-ish magnitudes)
                if not is_current and rng.random() < quake_rate / 4:
                    qlat, qlon = QUAKE_PLACES.get(name, (clat, clon))
                    mag = min(5.4, 2.5 + rng.expovariate(2.3))
                    events.append(_quake(region_ids[name], h + timedelta(minutes=rng.randint(0, 59)),
                                         mag, f"near {name}", qlat + rng.gauss(0, 0.6),
                                         qlon + rng.gauss(0, 0.6), rng))

        for name, hours_ago, mag, place, lat, lon in SCRIPTED_QUAKES:
            events.append(_quake(region_ids[name], now - timedelta(hours=hours_ago), mag, place, lat, lon, rng))

        logger.info("Inserting %d aircraft positions...", len(flights))
        execute_values(cur, """
            INSERT INTO flight_observations (id, route_id, callsign, icao24, timestamp, position,
                altitude_ft, speed_kt, heading_deg, source, ingested_at)
            VALUES %s""", flights,
            template="(gen_random_uuid(), %s::uuid, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, now())",
            page_size=5000)
        execute_values(cur, """
            INSERT INTO weather_observations (id, region_id, timestamp, position, wind_speed_kt,
                precipitation_mm, storm_index, source, ingested_at) VALUES %s""", weather,
            template="(gen_random_uuid(), %s::uuid, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, now())")
        execute_values(cur, """
            INSERT INTO events (id, external_id, event_date, event_type, category, severity, position,
                region_id, description, source, ingested_at) VALUES %s""", events,
            template="(gen_random_uuid(), %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s::uuid, %s, %s, now())")
        counts["flights"], counts["weather"], counts["events"] = len(flights), len(weather), len(events)

        # satellites
        sat_rows, obs_rows = [], []
        for prefix, category, n, inc, mm, ecc, first in CONSTELLATIONS:
            planes = max(1, min(n, 6))
            for k in range(n):
                norad = first + k
                label = prefix if n == 1 else f"{prefix}-{k + 1:02d}" if prefix not in ("STARLINK", "ONEWEB") \
                    else f"{prefix}-{norad % 10000:04d}"
                raan = (360.0 / planes) * (k % planes) + rng.uniform(-3, 3)
                ma = (360.0 / max(1, n // planes)) * (k // planes) + rng.uniform(0, 30)
                l1, l2 = make_tle(norad, inc, raan, ecc, rng.uniform(0, 360), ma, mm, now)
                sat_rows.append((norad, label, category, l1, l2))
        execute_values(cur, """
            INSERT INTO satellites (id, norad_id, name, category, tle_line1, tle_line2) VALUES %s
            ON CONFLICT (norad_id) DO UPDATE
            SET name = EXCLUDED.name, category = EXCLUDED.category,
                tle_line1 = EXCLUDED.tle_line1, tle_line2 = EXCLUDED.tle_line2
            """, sat_rows, template="(gen_random_uuid(), %s, %s, %s, %s, %s)")
        raw.commit()
        cur.execute("SELECT norad_id, id::text FROM satellites")
        sat_ids = dict(cur.fetchall())
        step = timedelta(minutes=30)
        t = now - timedelta(hours=6)
        times = []
        while t <= now + timedelta(minutes=60):
            times.append(t)
            t += step
        for norad, _, _, l1, l2 in sat_rows:
            for when in times:
                try:
                    lat, lon, alt, _ = propagate(l1, l2, when)
                except ValueError:
                    continue
                obs_rows.append((sat_ids[norad], when, f"POINTZ({lon:.4f} {lat:.4f} {alt:.1f})", alt, SRC))
        execute_values(cur, """
            INSERT INTO satellite_observations (id, satellite_id, timestamp, position, altitude_km, source,
                ingested_at) VALUES %s""", obs_rows,
            template="(gen_random_uuid(), %s::uuid, %s, ST_GeomFromText(%s, 4326), %s, %s, now())",
            page_size=5000)
        raw.commit()
        counts["satellites"], counts["satellite_obs"] = len(sat_rows), len(obs_rows)
    finally:
        raw.close()
    return counts


def _quake(region_id, when, mag, place, lat, lon, rng):
    sev = "High" if mag >= 5.5 else "Medium" if mag >= 4.0 else "Low"
    return (f"demo-{rng.randint(0, 10**9)}", when, "Conflict Incident", "Geopolitical / Security Threat", sev,
            f"POINT({lon:.3f} {lat:.3f})", region_id, f"Security alert (Lvl {mag:.1f}) — {place}", SRC)


def main():
    parser = argparse.ArgumentParser(description="Generate the SkyNexus demo dataset")
    parser.add_argument("--reset", action="store_true", help="Clear existing observations first")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    upsert_regions()
    upsert_airports()
    if args.reset:
        reset_database()
    counts = generate(random.Random(args.seed))
    print("Demo dataset summary:", counts)

    from app.services.ingest import refresh_analysis

    print("Anomalies flagged:", refresh_analysis())


if __name__ == "__main__":
    main()
