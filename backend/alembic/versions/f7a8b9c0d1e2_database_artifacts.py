"""Bounded persistent artifact bytes for sleeping demos."""
from alembic import op

revision = 'f7a8b9c0d1e2'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE artifact_objects (
        storage_key text PRIMARY KEY,
        content bytea NOT NULL,
        sha256 varchar(64) NOT NULL,
        size_bytes bigint NOT NULL CHECK (size_bytes = octet_length(content)),
        updated_at timestamptz NOT NULL DEFAULT now()
    )''')


def downgrade():
    op.drop_table('artifact_objects')
