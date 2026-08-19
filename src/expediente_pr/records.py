from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid4())


class FirmRecord(Base):
    __tablename__ = "firms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("firm_id", "email", name="uq_user_firm_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CaseRecord(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("firm_id", "case_number", name="uq_case_firm_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    case_number: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    client_name: Mapped[str] = mapped_column(String(240))
    jurisdiction: Mapped[str] = mapped_column(String(40))
    forum: Mapped[str] = mapped_column(String(240))
    matter_type: Mapped[str] = mapped_column(String(120))
    related_case_numbers: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    tasks: Mapped[list["TaskRecord"]] = relationship(cascade="all, delete-orphan")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(240), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(240))
    media_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="quarantined")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarEventRecord(Base):
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    reminder_minutes: Mapped[list[int]] = mapped_column(JSON, default=list)
    legal_authority: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    calculation_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="tentative", index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntegrationConnectionRecord(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("firm_id", "user_id", "provider", name="uq_integration_owner_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    account_id: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(String(4096))
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    configuration: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExternalEventLinkRecord(Base):
    __tablename__ = "external_event_links"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "calendar_event_id", name="uq_external_link_event"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id"), index=True
    )
    calendar_event_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_events.id"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(1024))
    etag: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommunicationRecord(Base):
    __tablename__ = "communications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("cases.id"), index=True, nullable=True
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    metadata_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firm_id: Mapped[str] = mapped_column(ForeignKey("firms.id"), index=True)
    actor: Mapped[str] = mapped_column(String(240))
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
