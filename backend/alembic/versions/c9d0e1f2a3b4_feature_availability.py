"""Availability watermark for aggregate buckets."""
from alembic import op
import sqlalchemy as sa
revision='c9d0e1f2a3b4'
down_revision='b8c9d0e1f2a3'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('hourly_features',sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))

def downgrade():op.drop_column('hourly_features','updated_at')
