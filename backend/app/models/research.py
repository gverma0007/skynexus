"""Durable ingestion, authentication and research records."""
from sqlalchemy import Column, Boolean, String, DateTime, BigInteger, Integer, Text, Float, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base

class SessionRecord(Base):
    __tablename__ = 'research_sessions'
    token_hash = Column(String(64), primary_key=True)
    email = Column(String(254), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

class SourceState(Base):
    __tablename__ = 'source_states'
    id = Column(String(80), primary_key=True)
    status = Column(String(40), nullable=False, default='waiting')
    configured = Column(Boolean, nullable=True)
    last_success = Column(DateTime(timezone=True))
    last_attempt = Column(DateTime(timezone=True))
    error = Column(Text)
    records = Column(Integer, nullable=False, default=0)

class Observation(Base):
    __tablename__ = 'research_observations'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(80), nullable=False, index=True)
    external_id = Column(String(200), nullable=False)
    domain = Column(String(40), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    published_at = Column(DateTime(timezone=True))
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    kind = Column(String(20), nullable=False, default='observed')
    payload = Column(JSONB, nullable=False)
    __table_args__ = (UniqueConstraint('source', 'external_id', name='uq_research_source_external'),)

class StreamEvent(Base):
    __tablename__ = 'stream_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(40), nullable=False)
    source = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload = Column(JSONB, nullable=False)

class Experiment(Base):
    __tablename__ = 'research_experiments'
    id = Column(String(40), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    session_hash = Column(String(64), nullable=False, index=True)
    result = Column(JSONB, nullable=False)

class HourlyFeature(Base):
    __tablename__ = 'hourly_features'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(80), nullable=False)
    entity = Column(String(200), nullable=False)
    metric = Column(String(100), nullable=False)
    domain = Column(String(40), nullable=False)
    unit = Column(String(60))
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    value_sum = Column(Float, nullable=False)
    sample_count = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('source','entity','metric','timestamp',name='uq_hourly_feature'),)

class Asset(Base):
    __tablename__ = 'research_assets'
    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    asset_type = Column(String(60), nullable=False)
    geometry = Column(JSONB, nullable=False)
    properties_json = Column(JSONB, nullable=False)
    provenance_url = Column(Text, nullable=False)
    dataset_mode = Column(String(20), nullable=False, default='live')
    available_at = Column(DateTime(timezone=True), nullable=False)

class Artifact(Base):
    __tablename__ = 'research_artifacts'
    id = Column(String(40), primary_key=True)
    session_hash = Column(String(64), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    media_type = Column(String(100), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
