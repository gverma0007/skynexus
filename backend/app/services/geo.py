"""Region shapes cached in memory for fast point-in-region lookups."""

from __future__ import annotations

import json
import threading
import time

from shapely.geometry import Point, shape
from shapely.prepared import prep
from sqlalchemy import text
from sqlalchemy.orm import Session

_lock = threading.Lock()
_cache: tuple[float, list[dict]] | None = None
TTL_S = 300.0


def region_shapes(db: Session) -> list[dict]:
    global _cache
    with _lock:
        if _cache and time.monotonic() - _cache[0] < TTL_S:
            return _cache[1]
    rows = db.execute(text(
        "SELECT id::text, name, ST_AsGeoJSON(geom), ST_Y(centroid), ST_X(centroid) FROM regions"
    )).all()
    shapes = []
    for rid, name, gj, lat, lon in rows:
        geom = shape(json.loads(gj))
        shapes.append({"id": rid, "name": name, "geom": geom, "prepared": prep(geom),
                       "bounds": geom.bounds, "lat": float(lat), "lon": float(lon)})
    # Smaller zones first so overlapping zones resolve to the most specific one.
    shapes.sort(key=lambda s: s["geom"].area)
    with _lock:
        _cache = (time.monotonic(), shapes)
    return shapes


def region_for(shapes: list[dict], lat: float, lon: float) -> dict | None:
    p = Point(lon, lat)
    for s in shapes:
        minx, miny, maxx, maxy = s["bounds"]
        if minx <= lon <= maxx and miny <= lat <= maxy and s["prepared"].covers(p):
            return s
    return None


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None
