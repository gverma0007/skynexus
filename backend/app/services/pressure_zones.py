"""Pressure-zone model.

Identifies regions under elevated activity pressure by comparing each
zone's recent signal against its own baseline:

- flights: current 24h count vs the average daily count of the prior week
- events:  current 24h event count vs prior-week daily average
- weather: latest storm_index vs prior-week average

The z-score per driver is (recent - baseline) / max(baseline_std, eps),
converted to a 0-100 pressure contribution, combined into a composite
pressure index, and classified (CALM -> CRITICAL) with the top drivers
named so the UI can explain *why* a zone is under pressure.
"""

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.models.aviation import (
    Event,
    FlightObservation,
    FlightRoute,
    Region,
    WeatherObservation,
)

_EPS = 1e-9


def _z_to_pressure(z: float) -> float:
    """Map a z-score to a 0-100 pressure scale (z=0 -> 0, z=3 -> ~100)."""
    if z <= 0:
        return 0.0
    return min(100.0, (z / 3.0) * 100.0)


def _baseline_stats(values: list[float]) -> tuple[float, float]:
    """Mean and (robust-ish) std of the baseline window."""
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


def _flight_pressure(db: Session, region_id, now: datetime) -> dict | None:
    route = aliased(FlightRoute)
    # Hourly counts for the last 8 days
    hour_bucket = func.date_trunc("hour", FlightObservation.timestamp).label("hour")
    rows = (
        db.query(
            hour_bucket,
            func.count(FlightObservation.id),
        )
        .join(route, FlightObservation.route_id == route.id)
        .filter(
            route.region_id == region_id,
            FlightObservation.timestamp >= now - timedelta(days=8),
        )
        .group_by(hour_bucket)
        .all()
    )
    by_hour = {ts: n for ts, n in rows}

    baseline_hours = [by_hour[ts] for ts in by_hour if ts < now - timedelta(days=1)]
    recent = [n for ts, n in by_hour.items() if ts >= now - timedelta(hours=24)]

    base_mean, base_std = _baseline_stats([float(v) for v in baseline_hours])
    if not recent:
        return None
    recent_mean = statistics.fmean([float(v) for v in recent])
    z = (recent_mean - base_mean) / max(base_std, _EPS)
    return {
        "z": round(z, 2),
        "pressure": _z_to_pressure(z),
        "recent": round(recent_mean, 1),
        "baseline": round(base_mean, 1),
    }


def _event_pressure(db: Session, region_id, now: datetime) -> dict | None:
    # Daily counts over 8 days
    day_bucket = func.date_trunc("day", Event.event_date).label("day")
    rows = (
        db.query(
            day_bucket,
            func.count(Event.id),
        )
        .filter(
            Event.region_id == region_id,
            Event.event_date >= now - timedelta(days=8),
        )
        .group_by(day_bucket)
        .all()
    )
    by_day = {ts: n for ts, n in rows}
    baseline = [float(n) for ts, n in by_day.items() if ts < now - timedelta(days=1)]
    recent = float(by_day.get(now.replace(hour=0, minute=0), 0.0))

    base_mean, base_std = _baseline_stats(baseline)
    z = (recent - base_mean) / max(base_std, _EPS)
    return {
        "z": round(z, 2),
        "pressure": _z_to_pressure(z),
        "recent": recent,
        "baseline": base_mean,
    }


def _weather_pressure(db: Session, region_id, now: datetime) -> dict | None:
    wx_day = func.date_trunc("day", WeatherObservation.timestamp).label("wx_day")
    rows = (
        db.query(
            wx_day,
            func.avg(WeatherObservation.storm_index),
        )
        .filter(
            WeatherObservation.region_id == region_id,
            WeatherObservation.timestamp >= now - timedelta(days=8),
        )
        .group_by(wx_day)
        .all()
    )
    by_day = {ts: float(v or 0) for ts, v in rows}
    baseline = [v for ts, v in by_day.items() if ts < now - timedelta(days=1)]
    recent = by_day.get(now.replace(hour=0, minute=0))
    if recent is None and by_day:
        recent = max(by_day.values())
    if recent is None:
        return None

    base_mean, base_std = _baseline_stats(baseline)
    z = (recent - base_mean) / max(base_std, _EPS)
    return {
        "z": round(z, 2),
        "pressure": _z_to_pressure(z),
        "recent": round(recent, 1),
        "baseline": round(base_mean, 1),
    }


def _classification(index: float) -> tuple[str, str]:
    """(label, description) for a composite pressure index."""
    s = get_settings()
    if index >= s.severity_high:
        return "CRITICAL", "sustained, multi-driver deviation"
    if index >= s.severity_medium:
        return "ELEVATED", "clear deviation from baseline"
    if index >= s.severity_low:
        return "WATCH", "early signs of pressure building"
    return "CALM", "within normal bounds"


def compute_pressure_zones(db: Session) -> list[dict]:
    """Pressure assessment for every monitored region, sorted by intensity."""
    now = datetime.now(timezone.utc)
    results = []

    for region in db.query(Region).all():
        flight = _flight_pressure(db, region.id, now)
        event = _event_pressure(db, region.id, now)
        weather = _weather_pressure(db, region.id, now)

        drivers = []
        weighted = []
        # Weight flights 0.45, events 0.35, weather 0.20
        if flight:
            weighted.append((flight["pressure"], 0.45))
            if flight["pressure"] >= 15:
                drivers.append((flight["pressure"], "flight surge"))
        if event:
            weighted.append((event["pressure"], 0.35))
            if event["pressure"] >= 15:
                drivers.append((event["pressure"], "event spike"))
        if weather:
            weighted.append((weather["pressure"], 0.20))
            if weather["pressure"] >= 15:
                drivers.append((weather["pressure"], "storm buildup"))

        if weighted:
            index = sum(p * w for p, w in weighted) / sum(w for _, w in weighted)
        else:
            index = 0.0

        label, description = _classification(index)
        drivers.sort(reverse=True)

        results.append(
            {
                "region_id": str(region.id),
                "region_name": region.name,
                "lat": None,
                "lon": None,
                "pressure_index": round(index, 1),
                "classification": label,
                "description": description,
                "drivers": [d for _, d in drivers[:3]],
                "signals": {
                    "flights": flight,
                    "events": event,
                    "weather": weather,
                },
            }
        )

    results.sort(key=lambda r: r["pressure_index"], reverse=True)
    return results
