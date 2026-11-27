"""Expose worker credential presence without distributing secrets to web services."""
from alembic import op
import sqlalchemy as sa
revision='d0e1f2a3b4c5'
down_revision='c9d0e1f2a3b4'
branch_labels=None
depends_on=None

def upgrade():op.add_column('source_states',sa.Column('configured',sa.Boolean(),nullable=True))
def downgrade():op.drop_column('source_states','configured')
