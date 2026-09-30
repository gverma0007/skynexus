from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class BaselineBase(BaseModel):
    entity_type: str
    entity_id: int
    feature_name: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    mean_value: float
    std_value: float
    sample_count: int

class Baseline(BaselineBase):
    id: UUID
    computed_at: datetime
    class Config:
        from_attributes = True

class AnomalyScoreBase(BaseModel):
    entity_type: str
    entity_id: int
    region_id: UUID
    timestamp: datetime
    feature_name: str
    observed_value: float
    z_score: Optional[float] = None
    isolation_forest_score: Optional[float] = None
    composite_score: Optional[float] = None
    severity_label: Optional[str] = None

class AnomalyScore(AnomalyScoreBase):
    id: UUID
    computed_at: datetime
    class Config:
        from_attributes = True

class EventCorrelationBase(BaseModel):
    anomaly_id: UUID
    event_id: UUID
    temporal_proximity_score: float
    geographic_overlap_score: float
    confidence_score: float

class EventCorrelation(EventCorrelationBase):
    id: UUID
    computed_at: datetime
    class Config:
        from_attributes = True

class DisruptionIndexBase(BaseModel):
    region_id: UUID
    window_start: datetime
    window_end: datetime
    flight_anomaly_score: float
    event_relevance_score: float
    airspace_score: float
    airport_activity_score: float
    satellite_score: float
    weather_score: float
    composite_index: float
    severity_label: str
    confidence_pct: float

class DisruptionIndex(DisruptionIndexBase):
    id: UUID
    computed_at: datetime
    class Config:
        from_attributes = True

class WhatChangedReportBase(BaseModel):
    region_id: UUID
    event_id: UUID
    before_start: datetime
    before_end: datetime
    after_start: datetime
    after_end: datetime
    metrics_json: dict
    ai_explanation: str
    confidence_pct: float

class WhatChangedReport(WhatChangedReportBase):
    id: UUID
    generated_at: datetime
    class Config:
        from_attributes = True

class ForecastBase(BaseModel):
    region_id: UUID
    horizon_hours: int
    metric_name: str
    predicted_values: dict

class Forecast(ForecastBase):
    id: UUID
    generated_at: datetime
    class Config:
        from_attributes = True
