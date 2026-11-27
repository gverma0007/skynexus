"""Correct derived weather attribution without changing source observations."""
from alembic import op
revision='e1f2a3b4c5d6'
down_revision='d0e1f2a3b4c5'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""UPDATE anomaly_scores SET
        feature_name=replace(feature_name,'weather-explained','weather-coincident'),
        severity_label=CASE WHEN composite_score>=80 THEN 'high'
                            WHEN composite_score>=65 THEN 'medium'
                            WHEN composite_score>=40 THEN 'low' ELSE 'normal' END
        WHERE feature_name LIKE '%weather-explained%'""")

def downgrade():
    # A schema downgrade must not restore an unsupported causal attribution.
    pass
