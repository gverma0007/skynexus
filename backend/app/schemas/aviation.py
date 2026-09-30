from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class RegionBase(BaseModel):
    name: str

class Region(RegionBase):
    id: UUID
    class Config:
        from_attributes = True

class AirportBase(BaseModel):
    iata_code: str
    name: str
    region_id: Optional[UUID] = None

class Airport(AirportBase):
    id: UUID
    class Config:
        from_attributes = True

class FlightRouteBase(BaseModel):
    origin_airport_id: UUID
    dest_airport_id: UUID
    region_id: Optional[UUID] = None

class FlightRoute(FlightRouteBase):
    id: UUID
    class Config:
        from_attributes = True

class FlightObservationBase(BaseModel):
    route_id: Optional[UUID] = None
    callsign: str
    icao24: str
    timestamp: datetime
    altitude_ft: float
    speed_kt: float
    heading_deg: float
    source: str

class FlightObservation(FlightObservationBase):
    id: UUID
    ingested_at: datetime
    class Config:
        from_attributes = True
