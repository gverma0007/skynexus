"""saved reports columns + query indexes

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("what_changed_reports", "event_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "what_changed_reports",
        sa.Column("window_hours", sa.Integer(), server_default="24", nullable=False),
    )
    op.add_column(
        "what_changed_reports",
        sa.Column("ai_source", sa.String(length=20), server_default="template", nullable=False),
    )
    op.create_index(
        "ix_what_changed_reports_generated_at", "what_changed_reports", ["generated_at"]
    )
    op.create_index(
        "ix_satellite_observations_sat_time",
        "satellite_observations",
        ["satellite_id", "timestamp"],
    )
    op.create_index(
        "ix_weather_observations_region_time",
        "weather_observations",
        ["region_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_weather_observations_region_time", table_name="weather_observations")
    op.drop_index("ix_satellite_observations_sat_time", table_name="satellite_observations")
    op.drop_index("ix_what_changed_reports_generated_at", table_name="what_changed_reports")
    op.drop_column("what_changed_reports", "ai_source")
    op.drop_column("what_changed_reports", "window_hours")
    op.alter_column("what_changed_reports", "event_id", existing_type=sa.UUID(), nullable=False)
