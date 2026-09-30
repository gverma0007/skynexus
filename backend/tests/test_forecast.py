import pytest
from unittest.mock import MagicMock
from app.ml.forecast import forecast_region

def test_forecast_region():
    historical_metrics = [{"flight_volume": 100}, {"flight_volume": 110}]
    forecast = forecast_region(1, historical_metrics, horizon_hours=2)
    
    assert forecast["region_id"] == 1
    assert forecast["horizon_hours"] == 2
    assert "h+1" in forecast["predicted_values"]
    assert "h+2" in forecast["predicted_values"]
    assert forecast["predicted_values"]["h+1"] == 120
    assert forecast["predicted_values"]["h+2"] == 130
