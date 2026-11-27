"""Bounded observations and long-lived hourly research features."""
from alembic import op
revision='f6a7b8c9d0e1'
down_revision='e5f6a7b8c9d0'
branch_labels=None
depends_on=None

def upgrade():
    from app.models.research import HourlyFeature
    HourlyFeature.__table__.create(op.get_bind())

def downgrade():op.drop_table('hourly_features')
