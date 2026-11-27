"""Research platform, durable sessions and ingestion outbox."""
from alembic import op
import sqlalchemy as sa
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

def upgrade():
    from app.models.research import SessionRecord, SourceState, Observation, StreamEvent, Experiment
    bind = op.get_bind()
    for model in (SessionRecord, SourceState, Observation, StreamEvent, Experiment):
        model.__table__.create(bind)
    op.alter_column('satellites', 'tle_line1', type_=sa.Text(), existing_type=sa.String(200))
    op.add_column('what_changed_reports', sa.Column('owner_session', sa.String(64), nullable=True))
    op.execute("UPDATE events SET event_type='Earthquake', category='Natural hazard', description=regexp_replace(description, '^Security alert \\(Lvl ([0-9.]+)\\) — ', 'M\\1 earthquake — ') WHERE source='usgs'")

def downgrade():
    op.drop_column('what_changed_reports', 'owner_session')
    for table in ('research_experiments', 'stream_events', 'research_observations', 'source_states', 'research_sessions'):
        op.drop_table(table)
