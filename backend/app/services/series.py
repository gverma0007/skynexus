"""Hourly per-region signal series shared by every score, chart and report.

Three queries build an 8-day hourly picture for all regions at once:

- aircraft: distinct aircraft (icao24) seen per hour. Counting distinct
  aircraft rather than rows makes the metric independent of how often the
  ingest loop runs.
- storm:    mean storm_index per hour, carried forward across hours with no
  reading (weather is a level, not a count).
- events:   event count and largest magnitude per hour.

Hours in which the ingest loop collected no aircraft anywhere are treated
as *missing* (None), not zero. Otherwise downtime would look like a global
traffic collapse.
"""

from __future__ import annotations

import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import TTLCache

WINDOW_HOURS = 8 * 24
CACHE_TTL_S = 45.0

_MAG_RE = re.compile(r"M(\d+(?:\.\d+)?)")


@dataclass
class RegionSeries:
    region_id: str
    name: str
    lat: float
    lon: float
    hours: list[datetime]
    aircraft: list[float | None]
    storm: list[float | None]
    events: list[int]
    max_mag: list[float]


@dataclass
class SeriesBundle:
    built_at: float
    now: datetime
    hours: list[datetime]
    regions: dict[str, RegionSeries] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)


_bundle_cache: TTLCache[SeriesBundle] = TTLCache(ttl_seconds=CACHE_TTL_S)


def invalidate() -> None:
    _bundle_cache.invalidate()


def magnitude_of(description: str | None, severity: str | None) -> float:
    m = _MAG_RE.search(description or "")
    if m:
        return float(m.group(1))
    return {"high": 6.0, "medium": 4.5, "low": 3.0}.get((severity or "").lower(), 3.0)


def get_series(db: Session, now: datetime | None = None) -> SeriesBundle:
    if now is None:
        cached = _bundle_cache.get()
        if cached is not None:
            return cached
    bundle = _build(db, now)
    if now is None:
        _bundle_cache.set(bundle)
    return bundle


def _build(db: Session, now: datetime | None) -> SeriesBundle:
    from app.core.config import get_settings

    mode = get_settings().DATA_MODE
    if now is None and mode == "demo":
        max_ts = db.execute(text("SELECT MAX(timestamp) FROM flight_observations WHERE source = 'demo_dataset'")).scalar()
        if max_ts:
            now = max_ts

    src_fo = "AND fo.source = 'demo_dataset'" if mode == "demo" else "AND fo.source != 'demo_dataset'"
    src_raw_fo = "AND source = 'demo_dataset'" if mode == "demo" else "AND source != 'demo_dataset'"
    src_wo = "AND source = 'demo_dataset'" if mode == "demo" else "AND source != 'demo_dataset'"
    src_ev = "AND e.source = 'demo_dataset'" if mode == "demo" else "AND e.source != 'demo_dataset'"

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=h) for h in range(WINDOW_HOURS - 1, -1, -1)]
    start = hours[0]
    index = {h: i for i, h in enumerate(hours)}

    regions = db.execute(text(
        "SELECT id::text, name, ST_Y(centroid), ST_X(centroid) FROM regions ORDER BY name"
    )).all()

    flight_rows = db.execute(text(
        f"""
        SELECT fr.region_id::text, date_trunc('hour', fo.timestamp) AS hr,
               COUNT(DISTINCT fo.icao24)
        FROM flight_observations fo
        JOIN flight_routes fr ON fr.id = fo.route_id
        WHERE fo.timestamp >= :start AND fo.timestamp <= :now AND fr.region_id IS NOT NULL {src_fo}
        GROUP BY 1, 2
        """
    ), {"start": start, "now": now}).all()

    global_hours = {
        r[0] for r in db.execute(text(
            f"""
            SELECT DISTINCT date_trunc('hour', timestamp) FROM flight_observations
            WHERE timestamp >= :start AND timestamp <= :now {src_raw_fo}
            """
        ), {"start": start, "now": now}).all()
    }

    weather_rows = db.execute(text(
        f"""
        SELECT region_id::text, date_trunc('hour', timestamp), AVG(storm_index)
        FROM weather_observations
        WHERE timestamp >= :start - interval '1 day' AND timestamp <= :now {src_wo}
        GROUP BY 1, 2 ORDER BY 2
        """
    ), {"start": start, "now": now}).all()

    event_rows = db.execute(text(
        f"""
        SELECT e.id::text, e.region_id::text, e.event_date, e.event_type, e.severity,
               e.description, ST_Y(e.position), ST_X(e.position), e.source
        FROM events e
        WHERE e.event_date >= :start AND e.event_date <= :now {src_ev}
        ORDER BY e.event_date DESC
        """
    ), {"start": start, "now": now}).all()

    bundle = SeriesBundle(built_at=time.monotonic(), now=now, hours=hours)
    for rid, name, lat, lon in regions:
        n = len(hours)
        bundle.regions[rid] = RegionSeries(
            region_id=rid, name=name, lat=float(lat), lon=float(lon), hours=hours,
            aircraft=[0.0 if h in global_hours else None for h in hours],
            storm=[None] * n, events=[0] * n, max_mag=[0.0] * n,
        )

    for rid, hr, count in flight_rows:
        rs = bundle.regions.get(rid)
        i = index.get(hr)
        if rs is not None and i is not None:
            rs.aircraft[i] = float(count)

    # weather: place readings, then carry forward (max 6 h) across gaps
    last_before: dict[str, float] = {}
    for rid, hr, avg in weather_rows:
        rs = bundle.regions.get(rid)
        if rs is None:
            continue
        i = index.get(hr)
        if i is None:
            last_before[rid] = float(avg or 0.0)
        else:
            rs.storm[i] = float(avg or 0.0)
    for rid, rs in bundle.regions.items():
        carry, age = last_before.get(rid), 0
        for i, v in enumerate(rs.storm):
            if v is not None:
                carry, age = v, 0
            elif carry is not None and age < 6:
                rs.storm[i] = carry
                age += 1

    for eid, rid, edate, etype, sev, desc, lat, lon, source in event_rows:
        mag = magnitude_of(desc, sev)
        bundle.events.append({
            "id": eid, "region_id": rid, "event_date": edate, "event_type": etype,
            "severity": sev, "description": desc, "lat": float(lat), "lon": float(lon),
            "magnitude": mag, "source": source,
        })
        rs = bundle.regions.get(rid)
        i = index.get(edate.replace(minute=0, second=0, microsecond=0))
        if rs is not None and i is not None:
            rs.events[i] += 1
            rs.max_mag[i] = max(rs.max_mag[i], mag)
    return bundle


def compute_region_history(bundle: SeriesBundle, region_id: str, hours: int = 48) -> dict | None:
    """Hourly aircraft, storm and event counts with a 'normal range' band.

    The band for each hour is mean +/- 1 std of the same hour of day over the
    baseline days (data older than 24 h).
    """
    rs = bundle.regions.get(region_id)
    if rs is None:
        return None
    end_idx = len(bundle.hours) - 1
    base_idx = [i for i in range(0, end_idx - 24) if rs.aircraft[i] is not None]
    by_hod: dict[int, list[float]] = {}
    for i in base_idx:
        by_hod.setdefault(rs.hours[i].hour, []).append(rs.aircraft[i])

    points = []
    for i in range(max(0, end_idx - hours), end_idx + 1):
        vals = by_hod.get(rs.hours[i].hour, [])
        band = None
        if len(vals) >= 3:
            m, sd = statistics.fmean(vals), statistics.pstdev(vals)
            band = [round(max(0.0, m - sd), 1), round(m + sd, 1)]
        points.append({
            "time": rs.hours[i].isoformat(),
            "aircraft": rs.aircraft[i],
            "partial": i == end_idx,
            "storm": None if rs.storm[i] is None else round(rs.storm[i], 1),
            "events": rs.events[i],
            "normal_range": band,
        })
    return {
        "region_id": rs.region_id,
        "region_name": rs.name,
        "points": points,
        "baseline_hours": len(base_idx),
    }


def compute_region_forecast(bundle: SeriesBundle, region_id: str, horizon_hours: int = 6) -> dict | None:
    """Linear trend on the last 12 complete hours of air traffic, with a
    +/- 1 residual-std band."""
    rs = bundle.regions.get(region_id)
    if rs is None:
        return None
    end_idx = len(bundle.hours) - 1
    pts = [(i, rs.aircraft[i]) for i in range(end_idx - 12, end_idx) if i >= 0 and rs.aircraft[i] is not None]
    if len(pts) < 3:
        return {
            "region_id": rs.region_id,
            "region_name": rs.name,
            "points": [],
            "history": [],
            "method": "insufficient data",
        }
    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = float(np.std(y - (slope * x + intercept)))
    out = []
    for h in range(0, horizon_hours + 1):
        xi = end_idx + h
        v = max(0.0, slope * xi + intercept)
        out.append({
            "time": (rs.hours[end_idx] + timedelta(hours=h)).isoformat(),
            "value": round(v, 1),
            "low": round(max(0.0, v - resid), 1),
            "high": round(v + resid, 1),
        })
    return {
        "region_id": rs.region_id,
        "region_name": rs.name,
        "history": [{"time": rs.hours[i].isoformat(), "value": v} for i, v in pts],
        "points": out,
        "trend_per_hour": round(float(slope), 2),
        "method": "linear trend, last 12 h",
    }
