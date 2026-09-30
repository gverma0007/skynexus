from sqlalchemy.orm import Session
from app.models.engine import Baseline, AnomalyScore
from datetime import datetime

def score_observation(db: Session, entity_type: str, entity_id: int, feature_name: str, observed_value: float, region_id: int, timestamp: datetime):
    """
    Calculate Z-score for a single observation against its baseline.
    """
    baseline = db.query(Baseline).filter(
        Baseline.entity_type == entity_type,
        Baseline.entity_id == entity_id,
        Baseline.feature_name == feature_name
    ).first()
    
    if not baseline:
        return None
        
    z_score = (observed_value - baseline.mean_value) / baseline.std_value
    
    anomaly = AnomalyScore(
        entity_type=entity_type,
        entity_id=entity_id,
        region_id=region_id,
        timestamp=timestamp,
        feature_name=feature_name,
        observed_value=observed_value,
        z_score=z_score,
        computed_at=datetime.utcnow()
    )
    db.add(anomaly)
    db.commit()
    
from typing import List

def score_window(db: Session, entity_type: str, entity_id: int, feature_name: str, region_id: int, start_time: datetime, end_time: datetime):
    """
    Batch score observations within a time window.
    """
    # Placeholder for fetching observations in the window
    # and calling score_observation for each
    pass
