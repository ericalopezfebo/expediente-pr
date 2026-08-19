from datetime import date, datetime, timezone
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    due_date: date | None = None
    assignee: str | None = Field(default=None, max_length=240)


class Task(TaskCreate):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    completed: bool = False


class DeadlineRequest(BaseModel):
    start_date: date
    days: int = Field(gt=0, le=365)
    use_calendar_days: bool = True
    authority: str = Field(min_length=1, max_length=500)


class DeadlineResult(BaseModel):
    start_date: date
    nominal_date: date
    due_date: date
    adjusted: bool
    explanation: list[str]
    authority: str
    requires_attorney_review: bool = True

