import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    func,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship, foreign

from app.core.db import Base


class Region(Base):
    __tablename__ = "regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    geom = Column(
        Geometry("POLYGON", srid=4326), nullable=False
    )
    centroid = Column(
        Geometry("POINT", srid=4326), nullable=False
    )

    airports = relationship("Airport", back_populates="region")
    flight_routes_origin = relationship(
        "FlightRoute", back_populates="origin_region", primaryjoin="Region.id == foreign(FlightRoute.origin_airport_id)"
    )
    flight_routes_dest = relationship(
        "FlightRoute", back_populates="dest_region", primaryjoin="Region.id == foreign(FlightRoute.dest_airport_id)"
    )

    __table_args__ = (
        Index("ix_regions_geom", "geom", postgresql_using="gist"),
        Index("ix_regions_centroid", "centroid", postgresql_using="gist"),
    )


class Airport(Base):
    __tablename__ = "airports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iata_code = Column(String(10), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regions.id"),
        nullable=True,
    )

    region = relationship("Region", back_populates="airports")

    __table_args__ = (
        Index("ix_airports_geom", "geom", postgresql_using="gist"),
    )


class Satellite(Base):
    __tablename__ = "satellites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    norad_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    category = Column(String(40))  # station/weather/science/nav/earthobs/comms
    tle_line1 = Column(String(200))
    tle_line2 = Column(String(200))


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id = Column(UUID(as_uuid=True), ForeignKey("satellites.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    position = Column(Geometry("POINTZ", srid=4326), nullable=False)
    altitude_km = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_satellite_observations_position", "position", postgresql_using="gist"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    position = Column(Geometry("POINT", srid=4326), nullable=False)
    wind_speed_kt = Column(Float, nullable=False)
    precipitation_mm = Column(Float, nullable=False)
    storm_index = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_weather_observations_position", "position", postgresql_using="gist"),
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(100), nullable=True)
    event_date = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    position = Column(Geometry("POINT", srid=4326), nullable=False)
    region_id = Column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(50), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_events_region_id_event_date", "region_id", "event_date"),
        Index("ix_events_position", "position", postgresql_using="gist"),
    )


class FlightRoute(Base):
    __tablename__ = "flight_routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin_airport_id = Column(
        UUID(as_uuid=True), ForeignKey("airports.id"), nullable=False
    )
    dest_airport_id = Column(
        UUID(as_uuid=True), ForeignKey("airports.id"), nullable=False
    )
    region_id = Column(
        UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True
    )

    origin_region = relationship(
        "Region",
        foreign_keys=[origin_airport_id],
        primaryjoin="FlightRoute.origin_airport_id == Region.id",
        back_populates="flight_routes_origin",
    )
    dest_region = relationship(
        "Region",
        foreign_keys=[dest_airport_id],
        primaryjoin="FlightRoute.dest_airport_id == Region.id",
        back_populates="flight_routes_dest",
    )

    __table_args__ = (
        Index(
            "ix_flight_routes_region_id",
            "region_id",
        ),
    )


class FlightObservation(Base):
    __tablename__ = "flight_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id = Column(
        UUID(as_uuid=True), ForeignKey("flight_routes.id"), nullable=True
    )
    callsign = Column(String(64), nullable=False)
    icao24 = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    position = Column(Geometry("POINT", srid=4326), nullable=False)
    altitude_ft = Column(Integer, nullable=False)
    speed_kt = Column(Float, nullable=False)
    heading_deg = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, default="demo_dataset")
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_flight_observations_timestamp",
            "timestamp",
        ),
        Index(
            "ix_flight_observations_route_id",
            "route_id",
        ),
        Index(
            "ix_flight_observations_position",
            "position",
            postgresql_using="gist",
        ),
    )


class DisruptionIndex(Base):
    __tablename__ = "disruption_index"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(UUID(as_uuid=True), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    flight_anomaly_score = Column(Float, nullable=False)
    event_relevance_score = Column(Float, nullable=False)
    airspace_score = Column(Float, nullable=False)
    airport_activity_score = Column(Float, nullable=False)
    satellite_score = Column(Float, nullable=False)
    weather_score = Column(Float, nullable=False)
    composite_index = Column(Float, nullable=False)
    severity_label = Column(String(50), nullable=False)
    confidence_pct = Column(Float, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_disruption_index_region_id", "region_id"),
    )


class WhatChangedReport(Base):
    __tablename__ = "what_changed_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(UUID(as_uuid=True), nullable=False)
    event_id = Column(UUID(as_uuid=True), nullable=False)
    before_start = Column(DateTime(timezone=True), nullable=False)
    before_end = Column(DateTime(timezone=True), nullable=False)
    after_start = Column(DateTime(timezone=True), nullable=False)
    after_end = Column(DateTime(timezone=True), nullable=False)
    metrics_json = Column(JSONB, nullable=False)
    ai_explanation = Column(Text, nullable=False)
    confidence_pct = Column(Float, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(UUID(as_uuid=True), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    horizon_hours = Column(Integer, nullable=False)
    metric_name = Column(String(100), nullable=False)
    predicted_values = Column(JSONB, nullable=False)