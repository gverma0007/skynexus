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
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

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


_cache: SeriesBundle | None = None
_lock = threading.Lock()


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def magnitude_of(description: str | None, severity: str | None) -> float:
    m = _MAG_RE.search(description or "")
    if m:
        return float(m.group(1))
    return {"high": 6.0, "medium": 4.5, "low": 3.0}.get((severity or "").lower(), 3.0)


def get_series(db: Session, now: datetime | None = None) -> SeriesBundle:
    global _cache
    with _lock:
        if now is None and _cache is not None and time.monotonic() - _cache.built_at < CACHE_TTL_S:
            return _cache
    bundle = _build(db, now)
    if now is None:
        with _lock:
            _cache = bundle
    return bundle


def _build(db: Session, now: datetime | None) -> SeriesBundle:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=h) for h in range(WINDOW_HOURS - 1, -1, -1)]
    start = hours[0]
    index = {h: i for i, h in enumerate(hours)}

    regions = db.execute(text(
        "SELECT id::text, name, ST_Y(centroid), ST_X(centroid) FROM regions ORDER BY name"
    )).all()

    flight_rows = db.execute(text(
        """
        SELECT fr.region_id::text, date_trunc('hour', fo.timestamp) AS hr,
               COUNT(DISTINCT fo.icao24)
        FROM flight_observations fo
        JOIN flight_routes fr ON fr.id = fo.route_id
        WHERE fo.timestamp >= :start AND fo.timestamp <= :now AND fr.region_id IS NOT NULL
        GROUP BY 1, 2
        """
    ), {"start": start, "now": now}).all()

    global_hours = {
        r[0] for r in db.execute(text(
            """
            SELECT DISTINCT date_trunc('hour', timestamp) FROM flight_observations
            WHERE timestamp >= :start AND timestamp <= :now
            """
        ), {"start": start, "now": now}).all()
    }

    weather_rows = db.execute(text(
        """
        SELECT region_id::text, date_trunc('hour', timestamp), AVG(storm_index)
        FROM weather_observations
        WHERE timestamp >= :start - interval '1 day' AND timestamp <= :now
        GROUP BY 1, 2 ORDER BY 2
        """
    ), {"start": start, "now": now}).all()

    event_rows = db.execute(text(
        """
        SELECT e.id::text, e.region_id::text, e.event_date, e.event_type, e.severity,
               e.description, ST_Y(e.position), ST_X(e.position), e.source
        FROM events e
        WHERE e.event_date >= :start AND e.event_date <= :now
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
