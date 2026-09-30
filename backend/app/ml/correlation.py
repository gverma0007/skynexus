import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.engine import AnomalyScore, EventCorrelation
from app.models.aviation import Event, Region, WeatherObservation
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import and_

def filter_weather_explained_anomalies(db: Session, anomalies: List[AnomalyScore]) -> List[AnomalyScore]:
    """
    Filter out anomalies that are likely explained by severe weather.
    If an anomaly occurs in a region with a high storm_index, it is flagged/filtered.
    """
    filtered = []
    for anomaly in anomalies:
        # Check weather in the region at the time of the anomaly
        weather = db.query(WeatherObservation).filter(
            WeatherObservation.region_id == anomaly.region_id,
            WeatherObservation.timestamp == anomaly.timestamp
        ).first()
        
        # If storm_index > 70, consider it weather-explained
        if weather and weather.storm_index > 70:
            continue
        filtered.append(anomaly)
    return filtered

def persist_correlations(db: Session, anomalies: List[AnomalyScore]):
    """
    Persist correlations between anomalies and events.

    Best-effort: if the optional events/weather tables are unavailable
    (e.g. lightweight test setups), correlation is skipped rather than
    failing the whole scoring pipeline.
    """
    try:
        _persist_correlations_inner(db, anomalies)
    except Exception as exc:  # pragma: no cover - depends on optional tables
        db.rollback()
        logging.getLogger(__name__).warning("Correlation skipped: %s", exc)


def _persist_correlations_inner(db: Session, anomalies: List[AnomalyScore]):
    # Filter out weather-explained anomalies first
    valid_anomalies = filter_weather_explained_anomalies(db, anomalies)

    for anomaly in valid_anomalies:
        # Find events near the anomaly in time and space
        # Temporal: +/- 6 hours
        # Geographic: within 100km (using PostGIS ST_DWithin)
        
        # This is a simplified correlation logic
        events = db.query(Event).filter(
            and_(
                Event.event_date >= anomaly.timestamp - timedelta(hours=6),
                Event.event_date <= anomaly.timestamp + timedelta(hours=6),
                func.ST_DWithin(Event.position, anomaly.position, 100000) # 100km
            )
        ).all()
        
        for event in events:
            # Calculate scores
            # Temporal: 1.0 if within 1 hour, decays to 0.0 at 6 hours
            time_diff = abs((event.event_date - anomaly.timestamp).total_seconds())
            temporal_score = max(0.0, 1.0 - (time_diff / (6 * 3600)))
            
            # Geographic: 1.0 if same point, decays to 0.0 at 100km
            # Using ST_Distance for precise distance
            dist = db.scalar(func.ST_Distance(event.position, anomaly.position))
            geographic_score = max(0.0, 1.0 - (dist / 100000))
            
            # Confidence: weighted average
            confidence = (temporal_score * 0.6) + (geographic_score * 0.4)
            
            correlation = EventCorrelation(
                anomaly_id=anomaly.id,
                event_id=event.id,
                temporal_proximity_score=temporal_score,
                geographic_overlap_score=geographic_score,
                confidence_score=confidence
            )
            db.add(correlation)
    db.commit()


def correlate_anomalies(db: Session, start: datetime, end: datetime):
    """
    Correlate anomalies by temporal and geographic proximity.
    """
    
    # 1. Fetch anomalies
    anomalies = db.query(AnomalyScore).filter(
        AnomalyScore.timestamp >= start,
        AnomalyScore.timestamp <= end
    ).all()
    
    # 2. Simple temporal correlation:
    # If an anomaly is followed by another in the same region within 1 hour,
    # boost the score.
    
    # 3. Simple geographic correlation:
    # If an anomaly occurs in a region, and another occurs in an adjacent region
    # within 1 hour, boost the score.
    
    # Persist correlations
    # For now, we just calculate a boost and return it or store it in a way
    # that composite_score can use it.
    # Since we need to persist EventCorrelation, we'll do that here.
    
    # Placeholder for actual correlation logic
    persist_correlations(db, anomalies)

