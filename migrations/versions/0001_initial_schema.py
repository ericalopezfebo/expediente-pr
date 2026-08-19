"""Initial authenticated multi-firm schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "firms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("firm_id", "email", name="uq_user_firm_email"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_users_firm_id", "users", ["firm_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_token_hash", "users", ["token_hash"])
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("case_number", sa.String(80), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("client_name", sa.String(240), nullable=False),
        sa.Column("jurisdiction", sa.String(40), nullable=False),
        sa.Column("forum", sa.String(240), nullable=False),
        sa.Column("matter_type", sa.String(120), nullable=False),
        sa.Column("related_case_numbers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("firm_id", "case_number", name="uq_case_firm_number"),
    )
    op.create_index("ix_cases_firm_id", "cases", ["firm_id"])
    op.create_index("ix_cases_case_number", "cases", ["case_number"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assignee", sa.String(240), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_tasks_firm_id", "tasks", ["firm_id"])
    op.create_index("ix_tasks_case_id", "tasks", ["case_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("actor", sa.String(240), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_events_firm_id", "audit_events", ["firm_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_resource_id", "audit_events", ["resource_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("tasks")
    op.drop_table("cases")
    op.drop_table("users")
    op.drop_table("firms")
