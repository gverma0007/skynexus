from sklearn.ensemble import IsolationForest
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.models.aviation import FlightObservation
from app.models.engine import AnomalyScore
from datetime import datetime

def train_isolation_forest(db: Session, route_id: int, days: int = 30):
    """
    Train an Isolation Forest model for a given route.
    """
    # Fetch data for the last N days
    # This is a placeholder for actual data fetching
    data = db.query(FlightObservation).filter(
        FlightObservation.route_id == route_id
    ).all()
    
    if not data:
        return None
        
    df = pd.DataFrame([
        {'speed': d.speed_kt, 'altitude': d.altitude_ft} 
        for d in data if d.speed_kt is not None and d.altitude_ft is not None
    ])
    
    if df.empty:
        return None
        
    model = IsolationForest(contamination=0.05)
    model.fit(df)
    
    return model

def score_isolation_forest(model, speed: float, altitude: float) -> float:
    """
    Score a single observation using the trained Isolation Forest model.
    Returns the anomaly score (negative = anomaly).
    """
    if model is None:
        return 0.0
        
    df = pd.DataFrame({'speed': [speed], 'altitude': [altitude]})
    score = model.decision_function(df)[0]
    return score
