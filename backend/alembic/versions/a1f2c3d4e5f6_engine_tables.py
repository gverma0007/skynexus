"""engine tables

Revision ID: a1f2c3d4e5f6
Revises: 897e3940acf9
Create Date: 2026-09-30 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '897e3940acf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('baselines',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('feature_name', sa.String(length=100), nullable=False),
    sa.Column('mean_value', sa.Float(), nullable=False),
    sa.Column('std_value', sa.Float(), nullable=False),
    sa.Column('sample_count', sa.Integer(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_baselines_entity', 'baselines', ['entity_type', 'entity_id', 'feature_name'], unique=True)
    op.create_table('anomaly_scores',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('feature_name', sa.String(length=100), nullable=False),
    sa.Column('observed_value', sa.Float(), nullable=False),
    sa.Column('z_score', sa.Float(), nullable=True),
    sa.Column('isolation_forest_score', sa.Float(), nullable=True),
    sa.Column('composite_score', sa.Float(), nullable=True),
    sa.Column('severity_label', sa.String(length=50), nullable=True),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_anomaly_scores_entity_time', 'anomaly_scores', ['entity_type', 'entity_id', 'timestamp'], unique=False)
    op.create_index('ix_anomaly_scores_region_time', 'anomaly_scores', ['region_id', 'timestamp'], unique=False)
    op.create_index('ix_anomaly_scores_composite', 'anomaly_scores', ['composite_score'], unique=False)
    op.create_table('event_correlations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('anomaly_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('temporal_proximity_score', sa.Float(), nullable=False),
    sa.Column('geographic_overlap_score', sa.Float(), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['anomaly_id'], ['anomaly_scores.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_event_correlations_anomaly', 'event_correlations', ['anomaly_id'], unique=False)
    op.create_index('ix_event_correlations_event', 'event_correlations', ['event_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_event_correlations_event', table_name='event_correlations')
    op.drop_index('ix_event_correlations_anomaly', table_name='event_correlations')
    op.drop_table('event_correlations')
    op.drop_index('ix_anomaly_scores_composite', table_name='anomaly_scores')
    op.drop_index('ix_anomaly_scores_region_time', table_name='anomaly_scores')
    op.drop_index('ix_anomaly_scores_entity_time', table_name='anomaly_scores')
    op.drop_table('anomaly_scores')
    op.drop_index('ix_baselines_entity', table_name='baselines')
    op.drop_table('baselines')
