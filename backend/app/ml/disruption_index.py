from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.engine import AnomalyScore, EventCorrelation
from app.models.aviation import Region, Airport, SatelliteObservation, DisruptionIndex, WeatherObservation
from datetime import datetime, timedelta
from typing import Dict, Any, NamedTuple, List

# Weights for Disruption Index
WEIGHTS = {
    "flight_anomaly": 0.25,
    "event_relevance": 0.20,
    "airspace": 0.20,
    "airport_activity": 0.15,
    "satellite": 0.10,
    "weather": 0.10
}

# Severity thresholds
SEVERITY_THRESHOLDS = {
    "normal": 40,
    "low": 70,
    "medium": 80,
    "high": 100
}

class DisruptionIndexResult(NamedTuple):
    composite_index: float
    severity_label: str
    confidence_pct: float

def get_weather_explanation_score(db: Session, region_id: str, at: datetime) -> float:
    """
    Look up weather_observations for that region/time and compare
    storm_index against that region's own weather baseline, scaled to 0-100.
    """
    # Placeholder: In a real implementation, we'd fetch the baseline for the region's weather
    # and compare the current storm_index.
    weather = db.query(WeatherObservation).filter(
        WeatherObservation.region_id == region_id,
        WeatherObservation.timestamp == at
    ).first()
    
    if not weather:
        return 0.0
        
    # Simple scaling: 0-100
    return min(weather.storm_index, 100.0)

def gather_disruption_components(db: Session, region_id: str, window_start: datetime, window_end: datetime) -> Dict[str, float]:
    """
    Gather the six raw component values for the Disruption Index.
    """
    # 1. flight_anomaly_score: mean composite_score of flight-route anomalies in the region
    flight_anomalies = db.query(AnomalyScore).filter(
        AnomalyScore.region_id == region_id,
        AnomalyScore.timestamp >= window_start,
        AnomalyScore.timestamp <= window_end,
        AnomalyScore.entity_type == "flight"
    ).all()
    
    flight_anomaly_score = 0.0
    if flight_anomalies:
        flight_anomaly_score = sum(a.composite_score or 0.0 for a in flight_anomalies) / len(flight_anomalies)
        
    # 2. event_relevance_score: mean confidence_score of event_correlations tied to those anomalies
    anomaly_ids = [a.id for a in flight_anomalies]
    correlations = db.query(EventCorrelation).filter(
        EventCorrelation.anomaly_id.in_(anomaly_ids)
    ).all()
    
    event_relevance_score = 0.0
    if correlations:
        event_relevance_score = sum(c.confidence_score or 0.0 for c in correlations) / len(correlations)
        
    # 3. airspace_score: share of flights with route deviation above a configurable threshold, scaled to 0-100
    # Placeholder: Need to implement flight route deviation logic
    airspace_score = 0.0
    
    # 4. airport_activity_score: |% change in hourly flight volume vs baseline|, scaled to 0-100
    # Placeholder: Need to implement flight volume baseline logic
    airport_activity_score = 0.0
    
    # 5. satellite_score: mean composite_score of satellite anomalies whose ground track passes through the region
    satellite_anomalies = db.query(AnomalyScore).filter(
        AnomalyScore.region_id == region_id,
        AnomalyScore.timestamp >= window_start,
        AnomalyScore.timestamp <= window_end,
        AnomalyScore.entity_type == "satellite"
    ).all()
    
    satellite_score = 0.0
    if satellite_anomalies:
        satellite_score = sum(a.composite_score or 0.0 for a in satellite_anomalies) / len(satellite_anomalies)
        
    # 6. weather_score: output of weather_explanation_score
    # Use the midpoint of the window for weather check
    midpoint = window_start + (window_end - window_start) / 2
    weather_score = get_weather_explanation_score(db, region_id, midpoint)
    
    return {
        "flight_anomaly_score": flight_anomaly_score,
        "event_relevance_score": event_relevance_score,
        "airspace_score": airspace_score,
        "airport_activity_score": airport_activity_score,
        "satellite_score": satellite_score,
        "weather_score": weather_score
    }

def compute_disruption_index(db: Session, region_id: str, window_start: datetime, window_end: datetime) -> DisruptionIndexResult:
    """
    Combine component scores into final Disruption Index with severity classification.
    """
    components = gather_disruption_components(db, region_id, window_start, window_end)
    
    composite_index = (
        components["flight_anomaly_score"] * WEIGHTS["flight_anomaly"] +
        components["event_relevance_score"] * WEIGHTS["event_relevance"] +
        components["airspace_score"] * WEIGHTS["airspace"] +
        components["airport_activity_score"] * WEIGHTS["airport_activity"] +
        components["satellite_score"] * WEIGHTS["satellite"] +
        components["weather_score"] * WEIGHTS["weather"]
    )
    
    # Determine severity
    if composite_index < SEVERITY_THRESHOLDS["normal"]:
        severity = "normal"
    elif composite_index < SEVERITY_THRESHOLDS["low"]:
        severity = "low"
    elif composite_index < SEVERITY_THRESHOLDS["medium"]:
        severity = "medium"
    else:
        severity = "high"
        
    # Confidence: placeholder for sample size logic
    confidence_pct = 100.0
    
    return DisruptionIndexResult(composite_index, severity, confidence_pct)

def persist_disruption_index(db: Session, region_id: str, window_start: datetime, window_end: datetime):
    """
    Persist disruption index into the disruption_index table.
    """
    components = gather_disruption_components(db, region_id, window_start, window_end)
    result = compute_disruption_index(db, region_id, window_start, window_end)
    
    index_entry = DisruptionIndex(
        region_id=region_id,
        window_start=window_start,
        window_end=window_end,
        flight_anomaly_score=components["flight_anomaly_score"],
        event_relevance_score=components["event_relevance_score"],
        airspace_score=components["airspace_score"],
        airport_activity_score=components["airport_activity_score"],
        satellite_score=components["satellite_score"],
        weather_score=components["weather_score"],
        composite_index=result.composite_index,
        severity_label=result.severity_label,
        confidence_pct=result.confidence_pct
    )
    db.add(index_entry)
    db.commit()

def recompute_rolling_disruption_index(db: Session, region_ids: List[str], window_hours: int = 24):
    """
    Recompute the index for all regions over a rolling window.
    """
    end = datetime.utcnow()
    start = end - timedelta(hours=window_hours)
    
    for region_id in region_ids:
        persist_disruption_index(db, region_id, start, end)


