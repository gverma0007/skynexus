"""initial

Revision ID: 897e3940acf9
Revises: 
Create Date: 2026-09-29 19:38:30.912608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '897e3940acf9'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Core tables ---
    # NOTE: GIST indexes on geometry columns are created automatically by
    # GeoAlchemy2 (spatial_index=True default), so they are NOT created here.
    op.create_table('disruption_index',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('flight_anomaly_score', sa.Float(), nullable=False),
    sa.Column('event_relevance_score', sa.Float(), nullable=False),
    sa.Column('airspace_score', sa.Float(), nullable=False),
    sa.Column('airport_activity_score', sa.Float(), nullable=False),
    sa.Column('satellite_score', sa.Float(), nullable=False),
    sa.Column('weather_score', sa.Float(), nullable=False),
    sa.Column('composite_index', sa.Float(), nullable=False),
    sa.Column('severity_label', sa.String(length=50), nullable=False),
    sa.Column('confidence_pct', sa.Float(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_disruption_index_region_id', 'disruption_index', ['region_id'], unique=False)
    op.create_table('forecasts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('horizon_hours', sa.Integer(), nullable=False),
    sa.Column('metric_name', sa.String(length=100), nullable=False),
    sa.Column('predicted_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('regions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('centroid', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('satellites',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('norad_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('tle_line1', sa.String(length=200), nullable=True),
    sa.Column('tle_line2', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('norad_id')
    )
    op.create_table('what_changed_reports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('before_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('before_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('after_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('after_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('metrics_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('ai_explanation', sa.Text(), nullable=False),
    sa.Column('confidence_pct', sa.Float(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('airports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('iata_code', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('iata_code')
    )
    op.create_table('events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(length=100), nullable=True),
    sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('severity', sa.String(length=50), nullable=False),
    sa.Column('position', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_events_region_id_event_date', 'events', ['region_id', 'event_date'], unique=False)
    op.create_table('satellite_observations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('satellite_id', sa.UUID(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('position', geoalchemy2.types.Geometry(geometry_type='POINTZ', srid=4326, dimension=3, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('altitude_km', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('weather_observations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('position', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('wind_speed_kt', sa.Float(), nullable=False),
    sa.Column('precipitation_mm', sa.Float(), nullable=False),
    sa.Column('storm_index', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('flight_routes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('origin_airport_id', sa.UUID(), nullable=False),
    sa.Column('dest_airport_id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['dest_airport_id'], ['airports.id'], ),
    sa.ForeignKeyConstraint(['origin_airport_id'], ['airports.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_flight_routes_region_id', 'flight_routes', ['region_id'], unique=False)
    op.create_table('flight_observations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('route_id', sa.UUID(), nullable=True),
    sa.Column('callsign', sa.String(length=64), nullable=False),
    sa.Column('icao24', sa.String(length=64), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('position', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('altitude_ft', sa.Integer(), nullable=False),
    sa.Column('speed_kt', sa.Float(), nullable=False),
    sa.Column('heading_deg', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['route_id'], ['flight_routes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_flight_observations_route_id', 'flight_observations', ['route_id'], unique=False)
    op.create_index('ix_flight_observations_timestamp', 'flight_observations', ['timestamp'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_flight_observations_timestamp', table_name='flight_observations')
    op.drop_index('ix_flight_observations_route_id', table_name='flight_observations')
    op.drop_table('flight_observations')
    op.drop_index('ix_flight_routes_region_id', table_name='flight_routes')
    op.drop_table('flight_routes')
    op.drop_table('weather_observations')
    op.drop_table('satellite_observations')
    op.drop_index('ix_events_region_id_event_date', table_name='events')
    op.drop_table('events')
    op.drop_table('airports')
    op.drop_table('what_changed_reports')
    op.drop_table('satellites')
    op.drop_table('regions')
    op.drop_table('forecasts')
    op.drop_index('ix_disruption_index_region_id', table_name='disruption_index')
    op.drop_table('disruption_index')
