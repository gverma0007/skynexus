"""Remove unsupported historical route and conflict interpretations."""
from alembic import op
revision='e5f6a7b8c9d0'
down_revision='d4e5f6a7b8c9'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("UPDATE flight_observations SET route_id=NULL WHERE source!='demo_dataset'")
    op.execute("UPDATE anomaly_scores SET feature_name='unexplained_compound_change' WHERE feature_name IN ('war_conflict_early_warning','airspace_conflict_evasion','orbital_reconnaissance_surge')")

def downgrade():
    # Source evidence cannot reconstruct the unsupported old assertions.
    pass
