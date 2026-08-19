from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CaseStatus(StrEnum):
    OPEN = "open"
    STAYED = "stayed"
    CLOSED = "closed"


class Jurisdiction(StrEnum):
    PUERTO_RICO_COURTS = "pr_courts"
    PUERTO_RICO_AGENCY = "pr_agency"
    FEDERAL = "federal"


class UserRole(StrEnum):
    ADMIN = "admin"
    ATTORNEY = "attorney"
    STAFF = "staff"
    CLIENT = "client"


class FirmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)


class Firm(FirmCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    email: str = Field(min_length=3, max_length=320)
    role: UserRole


class User(BaseModel):
    id: UUID
    firm_id: UUID
    name: str
    email: str
    role: UserRole
    active: bool


class UserCredential(BaseModel):
    user: User
    api_token: str


class FirmRegistration(BaseModel):
    firm_name: str = Field(min_length=1, max_length=240)
    admin_name: str = Field(min_length=1, max_length=240)
    admin_email: str = Field(min_length=3, max_length=320)


class FirmCredential(BaseModel):
    firm: Firm
    administrator: User
    api_token: str


class CaseCreate(BaseModel):
    case_number: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    client_name: str = Field(min_length=1, max_length=240)
    jurisdiction: Jurisdiction
    forum: str = Field(min_length=1, max_length=240)
    matter_type: str = Field(min_length=1, max_length=120)
    related_case_numbers: list[str] = Field(default_factory=list)


class Case(CaseCreate):
    id: UUID = Field(default_factory=uuid4)
    status: CaseStatus = CaseStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    due_date: date | None = None
    assignee: str | None = Field(default=None, max_length=240)


class Task(TaskCreate):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    completed: bool = False


class AuditEvent(BaseModel):
    id: UUID
    firm_id: UUID
    actor: str
    action: str
    resource_type: str
    resource_id: UUID
    occurred_at: datetime
    details: dict[str, str] = Field(default_factory=dict)


class Document(BaseModel):
    id: UUID
    case_id: UUID
    filename: str
    media_type: str
    size: int
    sha256: str
    scan_status: str
    created_at: datetime


class VelumExport(BaseModel):
    document_id: UUID
    sha256: str
    local_path: str
    warning: str


class RelatedCaseSuggestion(BaseModel):
    case_id: UUID
    case_number: str
    title: str
    score: float
    reasons: list[str]


class DeadlineRequest(BaseModel):
    start_date: date
    days: int = Field(gt=0, le=365)
    rule_id: str = "pr-civil-68.1"
    closure_dates: list[date] = Field(default_factory=list)
    mail_extension_applicable: bool = False
    start_event: str = Field(min_length=1, max_length=500)


class DeadlineRule(BaseModel):
    id: str
    name: str
    jurisdiction: str
    version: str
    authority: str
    source_url: str
    active: bool


class DeadlineResult(BaseModel):
    rule: DeadlineRule
    start_date: date
    nominal_date: date
    due_date: date
    adjusted: bool
    explanation: list[str]
    warnings: list[str] = Field(default_factory=list)
    requires_attorney_review: bool = True
