"""Region shapes cached in memory for fast point-in-region lookups."""

from __future__ import annotations

import json

from shapely.geometry import Point, shape
from shapely.prepared import prep
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import TTLCache

TTL_S = 300.0
_cache: TTLCache[list[dict]] = TTLCache(ttl_seconds=TTL_S)


def point_to_wkt(lon: float, lat: float) -> str:
    """Format coordinates into WKT Point string (POINT(lon lat))."""
    return f"POINT({lon:.4f} {lat:.4f})"


def region_shapes(db: Session) -> list[dict]:
    cached = _cache.get()
    if cached is not None:
        return cached

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
    _cache.set(shapes)
    return shapes


def region_for(shapes: list[dict], lat: float, lon: float) -> dict | None:
    p = Point(lon, lat)
    for s in shapes:
        minx, miny, maxx, maxy = s["bounds"]
        if minx <= lon <= maxx and miny <= lat <= maxy and s["prepared"].covers(p):
            return s
    return None


def get_region_outlines(db: Session) -> list[dict]:
    """Boundary rings as [lat, lon] pairs, for the globe."""
    rows = db.execute(text("SELECT id::text, name, ST_AsGeoJSON(geom) FROM regions")).all()
    return [
        {"id": rid, "name": name,
         "ring": [[float(lat), float(lon)] for lon, lat in json.loads(gj)["coordinates"][0]]}
        for rid, name, gj in rows
    ]


def invalidate() -> None:
    _cache.invalidate()
