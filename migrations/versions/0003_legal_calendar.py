"""Add firm-scoped legal calendar."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("assigned_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reminder_minutes", sa.JSON(), nullable=False),
        sa.Column("legal_authority", sa.String(1000), nullable=True),
        sa.Column("calculation_summary", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_calendar_events_firm_id", "calendar_events", ["firm_id"])
    op.create_index("ix_calendar_events_case_id", "calendar_events", ["case_id"])
    op.create_index("ix_calendar_events_event_type", "calendar_events", ["event_type"])
    op.create_index("ix_calendar_events_starts_at", "calendar_events", ["starts_at"])
    op.create_index(
        "ix_calendar_events_assigned_user_id", "calendar_events", ["assigned_user_id"]
    )
    op.create_index("ix_calendar_events_status", "calendar_events", ["status"])


def downgrade() -> None:
    op.drop_table("calendar_events")
