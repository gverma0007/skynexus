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
