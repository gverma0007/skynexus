"""Attributed infrastructure assets and private reproducibility artifacts."""
from alembic import op
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None

def upgrade():
    from app.models.research import Asset, Artifact
    for model in (Asset, Artifact):
        model.__table__.create(op.get_bind())

def downgrade():
    op.drop_table('research_artifacts')
    op.drop_table('research_assets')
