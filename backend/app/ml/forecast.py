import numpy as np
from typing import List, Dict, Any

def forecast_region(region_id: int, historical_metrics: List[Dict[str, Any]], horizon_hours: int = 6) -> Dict[str, Any]:
    """
    Simple statistical forecast for regional metrics.
    Uses a basic moving average/trend projection.
    """
    if not historical_metrics:
        return {"predicted_values": {}}
    
    # Extract relevant metrics (e.g., flight volume)
    values = [m.get("flight_volume", 0) for m in historical_metrics]
    
    # Simple linear trend projection
    if len(values) > 1:
        trend = values[-1] - values[-2]
    else:
        trend = 0
        
    predicted_values = {}
    for h in range(1, horizon_hours + 1):
        predicted_values[f"h+{h}"] = max(0, values[-1] + (trend * h))
        
    return {
        "region_id": region_id,
        "horizon_hours": horizon_hours,
        "predicted_values": predicted_values
    }
