"""Invalidate recomputable anomalies produced before source-isolated satellite series."""
from alembic import op
revision='a7b8c9d0e1f2'
down_revision='f6a7b8c9d0e1'
branch_labels=None
depends_on=None

def upgrade():
    # Only derived detections are invalidated; raw evidence and saved reports remain.
    op.execute('DELETE FROM event_correlations')
    op.execute('DELETE FROM anomaly_scores')

def downgrade():pass
