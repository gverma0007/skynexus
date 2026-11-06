"""Flight data access, great-circle route modeling, and deviation tracking."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session


def great_circle_waypoints(lat1: float, lon1: float, lat2: float, lon2: float, num_points: int = 15) -> list[dict]:
    """Generate intermediate (lat, lon) coordinates along the great-circle route."""
    r_lat1, r_lon1 = math.radians(lat1), math.radians(lon1)
    r_lat2, r_lon2 = math.radians(lat2), math.radians(lon2)
    cos_d = math.sin(r_lat1) * math.sin(r_lat2) + math.cos(r_lat1) * math.cos(r_lat2) * math.cos(r_lon2 - r_lon1)
    d = math.acos(max(-1.0, min(1.0, cos_d)))
    if d < 1e-6:
        return [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}]
    sin_d = math.sin(d)
    pts = []
    for i in range(num_points):
        f = i / (num_points - 1)
        A = math.sin((1 - f) * d) / sin_d
        B = math.sin(f * d) / sin_d
        x = A * math.cos(r_lat1) * math.cos(r_lon1) + B * math.cos(r_lat2) * math.cos(r_lon2)
        y = A * math.cos(r_lat1) * math.sin(r_lon1) + B * math.cos(r_lat2) * math.sin(r_lon2)
        z = A * math.sin(r_lat1) + B * math.sin(r_lat2)
        lat = math.degrees(math.atan2(z, math.hypot(x, y)))
        lon = math.degrees(math.atan2(y, x))
        pts.append({"lat": round(lat, 4), "lon": round(lon, 4)})
    return pts


def calculate_route_deviation(lat_p: float, lon_p: float, heading: float,
                              lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Calculate cross-track distance, heading deviation, and progress along planned route."""
    R = 6371.0  # Earth radius in km
    r_lat1, r_lon1 = math.radians(lat1), math.radians(lon1)
    r_lat2, r_lon2 = math.radians(lat2), math.radians(lon2)
    r_latp, r_lonp = math.radians(lat_p), math.radians(lon_p)

    cos_d12 = math.sin(r_lat1) * math.sin(r_lat2) + math.cos(r_lat1) * math.cos(r_lat2) * math.cos(r_lon2 - r_lon1)
    total_km = math.acos(max(-1.0, min(1.0, cos_d12))) * R

    cos_d1p = math.sin(r_lat1) * math.sin(r_latp) + math.cos(r_lat1) * math.cos(r_latp) * math.cos(r_lonp - r_lon1)
    d1p_rad = math.acos(max(-1.0, min(1.0, cos_d1p)))

    y1p = math.sin(r_lonp - r_lon1) * math.cos(r_latp)
    x1p = math.cos(r_lat1) * math.sin(r_latp) - math.sin(r_lat1) * math.cos(r_latp) * math.cos(r_lonp - r_lon1)
    theta1p = math.atan2(y1p, x1p)

    y12 = math.sin(r_lon2 - r_lon1) * math.cos(r_lat2)
    x12 = math.cos(r_lat1) * math.sin(r_lat2) - math.sin(r_lat1) * math.cos(r_lat2) * math.cos(r_lon2 - r_lon1)
    theta12 = math.atan2(y12, x12)

    xt_rad = math.asin(max(-1.0, min(1.0, math.sin(d1p_rad) * math.sin(theta1p - theta12))))
    xt_km = xt_rad * R

    yp2 = math.sin(r_lon2 - r_lonp) * math.cos(r_lat2)
    xp2 = math.cos(r_latp) * math.sin(r_lat2) - math.sin(r_latp) * math.cos(r_lat2) * math.cos(r_lon2 - r_lonp)
    bearing_dest = (math.degrees(math.atan2(yp2, xp2))) % 360.0
    hdg_dev = (heading - bearing_dest + 180.0) % 360.0 - 180.0

    at_rad = math.acos(max(-1.0, min(1.0, math.cos(d1p_rad) / max(0.0001, math.cos(xt_rad)))))
    at_km = at_rad * R
    progress_pct = round(min(100.0, max(0.0, at_km / max(1.0, total_km) * 100.0)), 1)

    abs_xt = abs(xt_km)
    if abs_xt <= 50.0:
        status = "on_route"
    elif abs_xt <= 120.0:
        status = "minor_deviation"
    else:
        status = "significant_deviation"

    side = "right" if xt_km > 0 else "left"
    return {
        "cross_track_km": round(xt_km, 1),
        "cross_track_nm": round(xt_km / 1.852, 1),
        "side": side,
        "heading_deviation_deg": round(hdg_dev, 1),
        "progress_pct": progress_pct,
        "total_route_km": round(total_km, 1),
        "status": status,
    }


def get_live_flights(db: Session, limit: int = 3000, window_minutes: int = 60) -> list[dict]:
    """Latest position of every aircraft seen in the most recent window of data,
    including general travel route endpoints and cross-track deviation metrics."""
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
               r.id::text, r.name,
               ap1.iata_code, ap1.name, ST_Y(ap1.geom), ST_X(ap1.geom),
               ap2.iata_code, ap2.name, ST_Y(ap2.geom), ST_X(ap2.geom)
        FROM flight_observations fo
        LEFT JOIN flight_routes fr ON fr.id = fo.route_id
        LEFT JOIN regions r ON r.id = fr.region_id
        LEFT JOIN airports ap1 ON ap1.id = fr.origin_airport_id
        LEFT JOIN airports ap2 ON ap2.id = fr.dest_airport_id, latest
        WHERE fo.timestamp >= latest.t - make_interval(mins => :mins)
          AND {src_filter}
        ORDER BY fo.icao24, fo.timestamp DESC
        LIMIT :limit
        """
    ), {"limit": limit, "mins": window_minutes}).all()

    out = []
    for r in rows:
        lat_p, lon_p = float(r[2]), float(r[3])
        heading = float(r[6])
        route_dict = None
        dev_dict = None

        if r[11] and r[15]:
            lat1, lon1 = float(r[13]), float(r[14])
            lat2, lon2 = float(r[17]), float(r[18])
            dev_dict = calculate_route_deviation(lat_p, lon_p, heading, lat1, lon1, lat2, lon2)
            route_dict = {
                "origin_iata": r[11],
                "origin_name": r[12],
                "dest_iata": r[15],
                "dest_name": r[16],
            }

        out.append({
            "icao24": r[0],
            "callsign": r[1],
            "lat": lat_p,
            "lon": lon_p,
            "altitude_ft": r[4],
            "speed_kt": round(float(r[5]), 0),
            "heading_deg": round(heading, 0),
            "timestamp": r[7].isoformat(),
            "source": r[8],
            "region_id": r[9],
            "region_name": r[10],
            "route": route_dict,
            "deviation": dev_dict,
        })
    return out


def get_flight_detail(db: Session, icao24: str) -> dict | None:
    """Retrieve full flight route, waypoints, trail and deviation for a specific aircraft."""
    from app.core.config import get_settings

    mode = get_settings().DATA_MODE
    src_filter = "fo.source = 'demo_dataset'" if mode == "demo" else "fo.source != 'demo_dataset'"

    obs = db.execute(text(
        f"""
        SELECT fo.icao24, fo.callsign, ST_Y(fo.position), ST_X(fo.position),
               fo.altitude_ft, fo.speed_kt, fo.heading_deg, fo.timestamp, fo.source,
               r.id::text, r.name,
               ap1.iata_code, ap1.name, ST_Y(ap1.geom), ST_X(ap1.geom),
               ap2.iata_code, ap2.name, ST_Y(ap2.geom), ST_X(ap2.geom)
        FROM flight_observations fo
        LEFT JOIN flight_routes fr ON fr.id = fo.route_id
        LEFT JOIN regions r ON r.id = fr.region_id
        LEFT JOIN airports ap1 ON ap1.id = fr.origin_airport_id
        LEFT JOIN airports ap2 ON ap2.id = fr.dest_airport_id
        WHERE fo.icao24 = :icao AND {src_filter}
        ORDER BY fo.timestamp DESC
        LIMIT 25
        """
    ), {"icao": icao24.lower().strip()}).all()

    if not obs:
        return None

    latest = obs[0]
    lat_p, lon_p = float(latest[2]), float(latest[3])
    heading = float(latest[6])

    route_info = None
    deviation = None
    waypoints = []

    if latest[11] and latest[15]:
        lat1, lon1 = float(latest[13]), float(latest[14])
        lat2, lon2 = float(latest[17]), float(latest[18])
        deviation = calculate_route_deviation(lat_p, lon_p, heading, lat1, lon1, lat2, lon2)
        waypoints = great_circle_waypoints(lat1, lon1, lat2, lon2, 20)
        route_info = {
            "origin": {"iata": latest[11], "name": latest[12], "lat": lat1, "lon": lon1},
            "dest": {"iata": latest[15], "name": latest[16], "lat": lat2, "lon": lon2},
            "waypoints": waypoints,
            "total_route_km": deviation["total_route_km"],
        }

    trail = [
        {
            "lat": float(r[2]),
            "lon": float(r[3]),
            "altitude_ft": r[4],
            "speed_kt": float(r[5]),
            "timestamp": r[7].isoformat(),
        }
        for r in obs
    ]

    summary = ""
    if route_info and deviation:
        summary = (
            f"Flying {route_info['origin']['iata']} → {route_info['dest']['iata']}. "
            f"{abs(deviation['cross_track_km'])} km {deviation['side']} of nominal route centerline "
            f"({deviation['progress_pct']}% complete). Status: {deviation['status'].replace('_', ' ').title()}."
        )

    return {
        "icao24": latest[0],
        "callsign": latest[1],
        "lat": lat_p,
        "lon": lon_p,
        "altitude_ft": latest[4],
        "speed_kt": round(float(latest[5]), 0),
        "heading_deg": round(heading, 0),
        "timestamp": latest[7].isoformat(),
        "source": latest[8],
        "region_id": latest[9],
        "region_name": latest[10],
        "route": route_info,
        "deviation": deviation,
        "summary": summary,
        "trail": trail,
    }


def get_flight_deviations(db: Session, min_deviation_km: float = 50.0, limit: int = 50) -> list[dict]:
    """Retrieve active flights deviating significantly from their general travel route."""
    all_live = get_live_flights(db, limit=1000)
    deviating = [
        f for f in all_live
        if f.get("deviation") and abs(f["deviation"].get("cross_track_km", 0.0)) >= min_deviation_km
    ]
    deviating.sort(key=lambda f: abs(f["deviation"]["cross_track_km"]), reverse=True)
    return deviating[:limit]


def get_all_region_flight_deviations(db: Session) -> dict[str, dict]:
    """Aggregate route deviations per monitored region to feed disruption scoring."""
    all_live = get_live_flights(db, limit=1000)
    by_region: dict[str, dict] = {}
    for f in all_live:
        rid = f.get("region_id")
        if not rid:
            continue
        entry = by_region.setdefault(rid, {
            "count": 0,
            "deviating_count": 0,
            "minor_count": 0,
            "significant_count": 0,
            "max_km": 0.0,
            "total_km": 0.0,
            "dev_score": 0.0,
            "avg_km": 0.0,
        })
        dev = f.get("deviation")
        if not dev:
            continue
        entry["count"] += 1
        xt_km = abs(float(dev.get("cross_track_km", 0.0)))
        if xt_km >= 50.0:
            entry["deviating_count"] += 1
            if xt_km > entry["max_km"]:
                entry["max_km"] = round(xt_km, 1)
            entry["total_km"] += xt_km
            if dev.get("status") == "significant_deviation" or xt_km >= 120.0:
                entry["significant_count"] += 1
            else:
                entry["minor_count"] += 1

    for d in by_region.values():
        if d["deviating_count"] > 0:
            d["avg_km"] = round(d["total_km"] / d["deviating_count"], 1)
            # Route deviation intensity score (0-100)
            score = min(100.0, d["significant_count"] * 30.0 + d["minor_count"] * 12.0 + max(0.0, d["max_km"] - 50.0) / 4.0)
            d["dev_score"] = round(score, 1)

    return by_region



