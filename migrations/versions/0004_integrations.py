"""Add encrypted provider connections and external delivery records."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("account_id", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(320), nullable=True),
        sa.Column("encrypted_access_token", sa.String(4096), nullable=False),
        sa.Column("encrypted_refresh_token", sa.String(4096), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "firm_id", "user_id", "provider", name="uq_integration_owner_provider"
        ),
    )
    op.create_index("ix_integration_connections_firm_id", "integration_connections", ["firm_id"])
    op.create_index("ix_integration_connections_user_id", "integration_connections", ["user_id"])
    op.create_index("ix_integration_connections_provider", "integration_connections", ["provider"])
    op.create_index("ix_integration_connections_status", "integration_connections", ["status"])

    op.create_table(
        "external_event_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id"),
            nullable=False,
        ),
        sa.Column(
            "calendar_event_id",
            sa.String(36),
            sa.ForeignKey("calendar_events.id"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(1024), nullable=False),
        sa.Column("etag", sa.String(500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id", "calendar_event_id", name="uq_external_link_event"
        ),
    )
    op.create_index("ix_external_event_links_firm_id", "external_event_links", ["firm_id"])
    op.create_index(
        "ix_external_event_links_connection_id", "external_event_links", ["connection_id"]
    )
    op.create_index(
        "ix_external_event_links_calendar_event_id",
        "external_event_links",
        ["calendar_event_id"],
    )

    op.create_table(
        "communications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("firm_id", sa.String(36), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(1024), nullable=True),
        sa.Column("recipient", sa.String(320), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_communications_firm_id", "communications", ["firm_id"])
    op.create_index("ix_communications_case_id", "communications", ["case_id"])
    op.create_index("ix_communications_connection_id", "communications", ["connection_id"])
    op.create_index("ix_communications_channel", "communications", ["channel"])
    op.create_index("ix_communications_status", "communications", ["status"])


def downgrade() -> None:
    op.drop_table("communications")
    op.drop_table("external_event_links")
    op.drop_table("integration_connections")
