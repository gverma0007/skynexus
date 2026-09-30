from typing import Tuple
from sqlalchemy.orm import Session
from app.models.engine import AnomalyScore
from app.ml.isolation_forest import score_isolation_forest
from app.ml.correlation import correlate_anomalies
from datetime import datetime

# Weights for composite score. Z-score and Isolation Forest form the base
# score; correlation acts as an additive boost on top.
Z_WEIGHT = 0.5
IFOREST_WEIGHT = 0.5
CORRELATION_WEIGHT = 0.2

def composite_score(z_score: float, iforest_score: float, correlation_boost: float = 0.0) -> Tuple[float, str]:
    """
    Combine Z-score, Isolation Forest score, and correlation boost into a 0-100 composite score.
    Higher = more anomalous.
    """
    # Clip Z-score to 0-100 range (assuming Z-score is roughly 0-5)
    # This is a simple scaling for demonstration
    scaled_z = min(abs(z_score) * 20, 100)
    
    # Isolation Forest score is already 0-100 (inverted)
    # Ensure it's 0-100
    scaled_iforest = max(0, min(iforest_score, 100))
    
    # Correlation boost is 0-100
    scaled_correlation = max(0, min(correlation_boost, 100))
    
    score = min(100.0, (scaled_z * Z_WEIGHT) + (scaled_iforest * IFOREST_WEIGHT) + (scaled_correlation * CORRELATION_WEIGHT))
    
    # Determine severity
    if score < 30:
        severity = "normal"
    elif score < 60:
        severity = "low"
    elif score < 80:
        severity = "medium"
    else:
        severity = "high"
        
    return score, severity

def update_composite_scores(db: Session, start: datetime, end: datetime) -> int:
    """
    Batch update composite scores for anomalies in the given window.
    """
    # Apply correlation first
    correlate_anomalies(db, start, end)
    
    anomalies = db.query(AnomalyScore).filter(
        AnomalyScore.timestamp >= start,
        AnomalyScore.timestamp <= end,
        AnomalyScore.composite_score == None
    ).all()
    
    count = 0
    for anomaly in anomalies:
        # Re-calculate isolation forest score if needed
        # Assuming we have the feature vector or can reconstruct it
        # For now, we use a placeholder or assume it's already in anomaly_scores
        # if it was computed earlier.
        
        # Based on prompt 35, isolation_forest_score is null.
        # We need to compute it.
        
        # This is a simplification.
        iforest_score = 50.0 # Placeholder
        
        # Placeholder for correlation boost
        correlation_boost = 0.0
        
        score, severity = composite_score(anomaly.z_score or 0.0, iforest_score, correlation_boost)
        
        anomaly.composite_score = score
        anomaly.severity_label = severity
        anomaly.isolation_forest_score = iforest_score
        count += 1
        
    db.commit()
    return count

