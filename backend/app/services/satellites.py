"""Satellite catalogue with live positions computed from stored TLEs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import TTLCache
from app.services.geo import region_for, region_shapes
from app.services.orbits import ground_track, orbit_params, positions_now, propagate

CATEGORY_LABELS = {
    "station": "Crewed station",
    "weather": "Weather",
    "science": "Science",
    "nav": "Navigation",
    "earthobs": "Earth observation",
    "comms": "Communications",
    "other": "Other",
}

_catalog_cache: TTLCache[list[tuple]] = TTLCache(ttl_seconds=60.0)


def catalog(db: Session) -> list[tuple]:
    """[(norad, name, category, l1, l2)] cached for 60 s."""
    cached = _catalog_cache.get()
    if cached is not None:
        return cached

    rows = [tuple(r) for r in db.execute(text(
        "SELECT norad_id, name, COALESCE(category, 'other'), tle_line1, tle_line2 FROM satellites"
    )).all()]
    _catalog_cache.set(rows)
    return rows


def invalidate() -> None:
    _catalog_cache.invalidate()


def live_positions(db: Session, when: datetime | None = None) -> list[dict]:
    when = when or datetime.now(timezone.utc)
    cat = catalog(db)
    pos = positions_now([(norad, l1, l2) for norad, _, _, l1, l2 in cat], when)
    shapes = region_shapes(db)
    out = []
    for norad, name, category, l1, l2 in cat:
        p = pos.get(norad)
        if p is None:
            continue
        lat, lon, alt, speed = p
        reg = region_for(shapes, lat, lon)
        out.append({
            "norad_id": norad, "name": name, "category": category,
            "category_label": CATEGORY_LABELS.get(category, "Other"),
            "lat": round(lat, 3), "lon": round(lon, 3), "altitude_km": round(alt, 1),
            "speed_km_s": round(speed, 2),
            "region_id": reg["id"] if reg else None,
            "region_name": reg["name"] if reg else None,
            "timestamp": when.isoformat(),
        })
    return out


def get_region_overhead(db: Session, region_id: str) -> dict:
    """Satellites whose ground point is inside the region right now."""
    sats = [s for s in live_positions(db) if s["region_id"] == region_id]
    by_cat: dict[str, int] = {}
    for s in sats:
        by_cat[s["category_label"]] = by_cat.get(s["category_label"], 0) + 1
    sats.sort(key=lambda s: (s["category"] != "station", s["altitude_km"]))
    return {"region_id": region_id, "count": len(sats), "by_category": by_cat, "satellites": sats[:50]}


def get_all_region_overhead(db: Session) -> dict[str, dict]:
    """Map of region_id -> satellite overhead, orbital distribution (LEO/MEO/GEO), and density."""
    shapes = region_shapes(db)
    shape_areas = {s["id"]: max(1.0, float(s.get("geom").area)) for s in shapes}
    positions = live_positions(db)
    by_region: dict[str, dict] = {
        s["id"]: {
            "count": 0,
            "by_category": {},
            "by_orbit": {"leo": 0, "meo": 0, "geo": 0},
            "satellites": [],
            "leo_earthobs": 0,
            "gnss_nav": 0,
            "density": 0.0,
            "area_sq_deg": shape_areas[s["id"]],
        }
        for s in shapes
    }
    for sat in positions:
        rid = sat.get("region_id")
        if not rid or rid not in by_region:
            continue
        entry = by_region[rid]
        entry["count"] += 1
        alt = sat.get("altitude_km", 0.0)
        orbit = "leo" if alt < 2000 else "meo" if alt < 35700 else "geo"
        entry["by_orbit"][orbit] += 1
        cat_lbl = sat.get("category_label", "Other")
        entry["by_category"][cat_lbl] = entry["by_category"].get(cat_lbl, 0) + 1
        if sat.get("category") == "earthobs" and orbit == "leo":
            entry["leo_earthobs"] += 1
        if sat.get("category") == "nav" and orbit == "meo":
            entry["gnss_nav"] += 1
        entry["satellites"].append(sat)

    for rid, entry in by_region.items():
        entry["density"] = round(entry["count"] / entry["area_sq_deg"] * 100.0, 2)
        entry["satellites"].sort(key=lambda s: (s["category"] != "station", s["altitude_km"]))
        entry["satellites"] = entry["satellites"][:50]
    return by_region


def get_satellite_categories(db: Session) -> list[dict]:
    """Summary of satellite counts by functional category."""
    rows = db.execute(text(
        "SELECT COALESCE(category, 'other'), COUNT(*) FROM satellites GROUP BY 1 ORDER BY 2 DESC"
    )).all()
    return [{"category": c, "label": CATEGORY_LABELS.get(c, "Other"), "count": n} for c, n in rows]


def get_satellite_detail(db: Session, norad_id: int, minutes: int = 90) -> dict | None:
    """Identity, orbit, live position and ground track for a satellite."""
    row = db.execute(text(
        "SELECT norad_id, name, COALESCE(category, 'other'), tle_line1, tle_line2 "
        "FROM satellites WHERE norad_id = :n"
    ), {"n": norad_id}).first()
    if row is None:
        return None
    norad, name, category, l1, l2 = row
    if not (l1 and l2):
        raise ValueError("No orbital elements stored for this satellite")
    now = datetime.now(timezone.utc)
    lat, lon, alt, speed = propagate(l1, l2, now)
    reg = region_for(region_shapes(db), lat, lon)
    return {
        "norad_id": norad, "name": name, "category": category,
        "category_label": CATEGORY_LABELS.get(category, "Other"),
        "position": {"time": now.isoformat(), "lat": round(lat, 3), "lon": round(lon, 3),
                     "alt_km": round(alt, 1), "speed_km_s": round(speed, 2)},
        "region_name": reg["name"] if reg else None,
        "orbit": orbit_params(l1, l2),
        "track": ground_track(l1, l2, now, minutes, minutes, 2),
    }
