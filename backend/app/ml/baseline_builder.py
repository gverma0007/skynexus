import numpy as np
from sqlalchemy.orm import Session
from app.models.aviation import FlightObservation
from app.models.weather import WeatherObservation
from app.models.satellite import SatelliteObservation
from datetime import datetime, timedelta

def compute_baseline(db: Session, entity_type: str, entity_id: int, feature_name: str, days: int = 30):
    """
    Compute mean and std for a given entity and feature over the last N days.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # This is a placeholder for the actual data fetching and computation
    # We will need to query the appropriate table based on entity_type
    
    # Example for flight observations
    if entity_type == "flight":
        data = db.query(FlightObservation.speed_kt).filter(
            FlightObservation.route_id == entity_id,
            FlightObservation.timestamp >= start_date
        ).all()
        values = [d[0] for d in data if d[0] is not None]
    else:
        values = []
        
    if not values:
        return None, None
        
from app.models.engine import Baseline
from app.core.db import SessionLocal

def upsert_baseline(db: Session, entity_type: str, entity_id: int, feature_name: str, days: int = 30):
    """
    Compute and upsert baseline into the baselines table.
    Includes epsilon guard for zero-division protection.
    """
    mean, std = compute_baseline(db, entity_type, entity_id, feature_name, days)
    
    if mean is None:
        return
        
    # Epsilon guard
    std = max(std, 1e-6)
    
    baseline = db.query(Baseline).filter(
        Baseline.entity_type == entity_type,
        Baseline.entity_id == entity_id,
        Baseline.feature_name == feature_name
    ).first()
    
    if baseline:
        baseline.mean_value = mean
        baseline.std_value = std
        baseline.computed_at = datetime.utcnow()
    else:
        baseline = Baseline(
            entity_type=entity_type,
            entity_id=entity_id,
            feature_name=feature_name,
            mean_value=mean,
            std_value=std,
            computed_at=datetime.utcnow()
        )
        db.add(baseline)
    db.commit()
