"""Satellite catalogue with live positions computed from stored TLEs."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.geo import region_for, region_shapes
from app.services.orbits import positions_now

CATEGORY_LABELS = {
    "station": "Crewed station",
    "weather": "Weather",
    "science": "Science",
    "nav": "Navigation",
    "earthobs": "Earth observation",
    "comms": "Communications",
    "other": "Other",
}

_lock = threading.Lock()
_catalog: tuple[float, list[tuple]] | None = None


def catalog(db: Session) -> list[tuple]:
    """[(norad, name, category, l1, l2)] cached for 60 s."""
    global _catalog
    with _lock:
        if _catalog and time.monotonic() - _catalog[0] < 60:
            return _catalog[1]
    rows = [tuple(r) for r in db.execute(text(
        "SELECT norad_id, name, COALESCE(category, 'other'), tle_line1, tle_line2 FROM satellites"
    )).all()]
    with _lock:
        _catalog = (time.monotonic(), rows)
    return rows


def invalidate() -> None:
    global _catalog
    with _lock:
        _catalog = None


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
