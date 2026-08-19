"""Add deduplicated reminder delivery jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column(
            "calendar_event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id"),
            nullable=False,
        ),
        sa.Column("reminder_minutes", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "calendar_event_id",
            "reminder_minutes",
            "channel",
            name="uq_reminder_delivery_event_offset_channel",
        ),
    )
    op.create_index("ix_reminder_deliveries_firm_id", "reminder_deliveries", ["firm_id"])
    op.create_index(
        "ix_reminder_deliveries_calendar_event_id",
        "reminder_deliveries",
        ["calendar_event_id"],
    )
    op.create_index("ix_reminder_deliveries_status", "reminder_deliveries", ["status"])
    op.create_index(
        "ix_reminder_deliveries_scheduled_at", "reminder_deliveries", ["scheduled_at"]
    )


def downgrade() -> None:
    op.drop_table("reminder_deliveries")
