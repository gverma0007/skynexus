from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.aviation import (
    Event,
    FlightObservation,
    FlightRoute,
    Region,
    SatelliteObservation,
    WeatherObservation,
)
from app.services.ai_explainer import get_ai_explanation

router = APIRouter()


def _avg_flights_per_day(db: Session, region_id, start: datetime, end: datetime) -> float:
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    total = (
        db.query(func.count(FlightObservation.id))
        .join(FlightRoute, FlightObservation.route_id == FlightRoute.id)
        .filter(
            FlightRoute.region_id == region_id,
            FlightObservation.timestamp >= start,
            FlightObservation.timestamp < end,
        )
        .scalar()
    ) or 0
    return total / days


def _avg_storm_index(db: Session, region_id, start: datetime, end: datetime) -> float:
    val = (
        db.query(func.avg(WeatherObservation.storm_index))
        .filter(
            WeatherObservation.region_id == region_id,
            WeatherObservation.timestamp >= start,
            WeatherObservation.timestamp < end,
        )
        .scalar()
    )
    return float(val or 0.0)


def _satellite_activity(db: Session, region_id, start: datetime, end: datetime) -> int:
    return (
        db.query(func.count(SatelliteObservation.id))
        .filter(
            SatelliteObservation.timestamp >= start,
            SatelliteObservation.timestamp < end,
        )
        .scalar()
    ) or 0


def _event_count(db: Session, region_id, start: datetime, end: datetime) -> int:
    return (
        db.query(func.count(Event.id))
        .filter(
            Event.region_id == region_id,
            Event.event_date >= start,
            Event.event_date < end,
        )
        .scalar()
    ) or 0


def _pct(before: float, after: float) -> float:
    if before <= 0:
        return 100.0 if after > 0 else 0.0
    return round((after - before) / before * 100.0, 1)


@router.get("/{region_id}")
async def get_what_changed(
    region_id: UUID,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Compare the last N hours against the equal-length prior window."""
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    now = datetime.now(timezone.utc)
    after_start = now - timedelta(hours=hours)
    before_start = now - timedelta(hours=hours * 2)

    flight_before = _avg_flights_per_day(db, region.id, before_start, after_start)
    flight_after = _avg_flights_per_day(db, region.id, after_start, now)
    storm_before = _avg_storm_index(db, region.id, before_start, after_start)
    storm_after = _avg_storm_index(db, region.id, after_start, now)
    sats_before = _satellite_activity(db, region.id, before_start, after_start)
    sats_after = _satellite_activity(db, region.id, after_start, now)
    events_before = _event_count(db, region.id, before_start, after_start)
    events_after = _event_count(db, region.id, after_start, now)

    metrics = {
        "region": {"id": str(region.id), "name": region.name},
        "window_hours": hours,
        "aviation_metrics": {
            "before": round(flight_before, 1),
            "after": round(flight_after, 1),
            "delta_pct": _pct(flight_before, flight_after),
            "summary": (
                f"Flight activity {'rose' if flight_after >= flight_before else 'fell'} "
                f"from {flight_before:.1f} to {flight_after:.1f} per day "
                f"({_pct(flight_before, flight_after):+.1f}%)"
            ),
        },
        "weather_metrics": {
            "before": round(storm_before, 1),
            "after": round(storm_after, 1),
            "delta_pct": _pct(storm_before, storm_after),
            "summary": (
                f"Average storm index moved from {storm_before:.1f} to {storm_after:.1f} "
                f"({_pct(storm_before, storm_after):+.1f}%)"
            ),
        },
        "satellite_metrics": {
            "before": sats_before,
            "after": sats_after,
            "delta_pct": _pct(sats_before, sats_after),
            "summary": (
                f"Satellite observations: {sats_before} -> {sats_after} "
                f"({_pct(sats_before, sats_after):+.1f}%)"
            ),
        },
        "events_metrics": {
            "before": events_before,
            "after": events_after,
            "delta_pct": _pct(events_before, events_after),
            "summary": (
                f"Security events: {events_before} -> {events_after} "
                f"({_pct(events_before, events_after):+.1f}%)"
            ),
        },
    }

    explanation = await get_ai_explanation(metrics)
    metrics["overall_assessment"] = explanation
    return metrics


@router.get("/{region_id}/forecast")
def get_region_forecast(
    region_id: UUID,
    horizon_hours: int = 6,
    db: Session = Depends(get_db),
):
    """Naive 6h flight-volume projection from the last 24h hourly trend."""
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    rows = (
        db.query(
            func.date_trunc("hour", FlightObservation.timestamp).label("hour"),
            func.count(FlightObservation.id),
        )
        .join(FlightRoute, FlightObservation.route_id == FlightRoute.id)
        .filter(
            FlightRoute.region_id == region.id,
            FlightObservation.timestamp >= start,
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    counts = [count for _, count in rows]
    if not counts:
        counts = [0]
    recent = counts[-6:]
    trend = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    last = counts[-1]

    points = []
    for h in range(1, horizon_hours + 1):
        value = max(0.0, last + trend * h)
        points.append(
            {
                "time": (now + timedelta(hours=h)).strftime("%H:%M"),
                "value": round(value, 1),
            }
        )
    return {
        "region_id": str(region.id),
        "region_name": region.name,
        "horizon_hours": horizon_hours,
        "history": [
            {
                "time": hour.strftime("%H:%M") if hour is not None else "",
                "value": count,
            }
            for hour, count in rows[-12:]
        ],
        "points": points,
    }
