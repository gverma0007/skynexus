from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class SatelliteBase(BaseModel):
    norad_id: int
    name: str

class Satellite(SatelliteBase):
    id: UUID
    class Config:
        from_attributes = True

class SatelliteObservationBase(BaseModel):
    satellite_id: UUID
    timestamp: datetime
    altitude_km: float
    source: str

class SatelliteObservation(SatelliteObservationBase):
    id: UUID
    ingested_at: datetime
    class Config:
        from_attributes = True

class WeatherObservationBase(BaseModel):
    region_id: UUID
    timestamp: datetime
    wind_speed_kt: float
    precipitation_mm: float
    storm_index: float
    source: str

class WeatherObservation(WeatherObservationBase):
    id: UUID
    ingested_at: datetime
    class Config:
        from_attributes = True

class EventBase(BaseModel):
    external_id: Optional[str] = None
    event_date: datetime
    event_type: str
    category: str
    severity: str
    region_id: UUID
    description: Optional[str] = None
    source: str

class Event(EventBase):
    id: UUID
    ingested_at: datetime
    class Config:
        from_attributes = True
