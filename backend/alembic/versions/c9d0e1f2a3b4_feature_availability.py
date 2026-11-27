"""Availability watermark for aggregate buckets."""
from alembic import op
import sqlalchemy as sa
revision='c9d0e1f2a3b4'
down_revision='b8c9d0e1f2a3'
branch_labels=None
depends_on=None

def upgrade():
    # Earlier revisions create tables from current ORM metadata on a fresh install.
    op.execute('ALTER TABLE hourly_features ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()')

def downgrade():op.drop_column('hourly_features','updated_at')
