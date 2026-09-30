"""Region disruption scoring shared by API endpoints.

Computes a 0-100 composite disruption score per region from:
- flight volume vs its own 7-day baseline
- recent security/event severity
- weather storm intensity
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.models.aviation import (
    Airport,
    Event,
    FlightObservation,
    FlightRoute,
    Region,
    WeatherObservation,
)

_SEVERITY_WEIGHTS = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _flight_anomaly_score(db: Session, region_id, now: datetime) -> float:
    """Current 24h flight count vs the average daily count of the prior 7 days."""
    route_region = aliased(FlightRoute)
    current = (
        db.query(func.count(FlightObservation.id))
        .join(route_region, FlightObservation.route_id == route_region.id)
        .filter(
            route_region.region_id == region_id,
            FlightObservation.timestamp >= now - timedelta(hours=24),
        )
        .scalar()
    ) or 0

    baseline_start = now - timedelta(days=8)
    baseline_end = now - timedelta(days=1)
    weekly_total = (
        db.query(func.count(FlightObservation.id))
        .join(route_region, FlightObservation.route_id == route_region.id)
        .filter(
            route_region.region_id == region_id,
            FlightObservation.timestamp >= baseline_start,
            FlightObservation.timestamp < baseline_end,
        )
        .scalar()
    ) or 0
    baseline = weekly_total / 7.0

    if baseline <= 0:
        return 60.0 if current > 0 else 0.0
    ratio = current / baseline
    return _clamp((ratio - 1.0) * 50.0)


def _event_relevance_score(db: Session, region_id, now: datetime) -> float:
    """Max event severity in the region over the last 24h, scaled to 0-100."""
    latest = (
        db.query(Event)
        .filter(
            Event.region_id == region_id,
            Event.event_date >= now - timedelta(hours=24),
        )
        .all()
    )
    if not latest:
        return 0.0
    weight = max(
        _SEVERITY_WEIGHTS.get((e.severity or "").lower(), 0.5) for e in latest
    )
    return _clamp(weight * 100.0)


def _weather_score(db: Session, region_id, now: datetime) -> float:
    avg_storm = (
        db.query(func.avg(WeatherObservation.storm_index))
        .filter(
            WeatherObservation.region_id == region_id,
            WeatherObservation.timestamp >= now - timedelta(hours=24),
        )
        .scalar()
    )
    return _clamp(float(avg_storm or 0.0))


def _severity_label(score: float) -> str:
    """Bands from Settings — tunable via SEVERITY_* env vars."""
    s = get_settings()
    if score < s.severity_low:
        return "normal"
    if score < s.severity_medium:
        return "low"
    if score < s.severity_high:
        return "medium"
    return "high"


def compute_region_disruption(db: Session, region: Region, now: datetime | None = None) -> dict:
    """Composite disruption metrics for one region."""
    now = now or datetime.now(timezone.utc)
    flight_score = _flight_anomaly_score(db, region.id, now)
    event_score = _event_relevance_score(db, region.id, now)
    weather_score = _weather_score(db, region.id, now)

    composite = (
        flight_score * 0.4 + event_score * 0.35 + weather_score * 0.25
    )
    return {
        "region_id": str(region.id),
        "region_name": region.name,
        "flight_anomaly_score": round(flight_score, 1),
        "event_relevance_score": round(event_score, 1),
        "weather_score": round(weather_score, 1),
        "composite_index": round(composite, 1),
        "severity_label": _severity_label(composite),
    }


def compute_all_disruptions(db: Session) -> list[dict]:
    regions = db.query(Region).all()
    now = datetime.now(timezone.utc)
    return [compute_region_disruption(db, r, now) for r in regions]
