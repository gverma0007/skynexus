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
from sqlalchemy.orm import relationship

from app.core.db import Base


class Baseline(Base):
    __tablename__ = "baselines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    feature_name = Column(String(100), nullable=False)
    mean_value = Column(Float, nullable=False)
    std_value = Column(Float, nullable=False)
    sample_count = Column(Integer, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_baselines_entity", "entity_type", "entity_id", "feature_name", unique=True),
    )


class AnomalyScore(Base):
    __tablename__ = "anomaly_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    region_id = Column(UUID(as_uuid=True), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    feature_name = Column(String(100), nullable=False)
    observed_value = Column(Float, nullable=False)
    z_score = Column(Float, nullable=True)
    isolation_forest_score = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)
    severity_label = Column(String(50), nullable=True)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_anomaly_scores_entity_time", "entity_type", "entity_id", "timestamp"),
        Index("ix_anomaly_scores_region_time", "region_id", "timestamp"),
        Index("ix_anomaly_scores_composite", "composite_score"),
    )


class EventCorrelation(Base):
    __tablename__ = "event_correlations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomaly_scores.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    temporal_proximity_score = Column(Float, nullable=False)
    geographic_overlap_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_event_correlations_anomaly", "anomaly_id"),
        Index("ix_event_correlations_event", "event_id"),
    )
