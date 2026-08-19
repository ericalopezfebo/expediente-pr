from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import issue_token
from .models import (
    AuditEvent,
    CalendarConflict,
    CalendarEvent,
    CalendarEventCreate,
    CalendarEventStatus,
    CalendarReminder,
    Case,
    CaseCreate,
    CaseStatus,
    Document,
    Firm,
    FirmCreate,
    FirmCredential,
    FirmRegistration,
    RelatedCaseSuggestion,
    Task,
    TaskCreate,
    User,
    UserCreate,
    UserCredential,
    UserRole,
)
from .records import (
    AuditRecord,
    CalendarEventRecord,
    CaseRecord,
    DocumentRecord,
    FirmRecord,
    TaskRecord,
    UserRecord,
)


class DuplicateCaseNumberError(ValueError):
    pass


def _case(record: CaseRecord) -> Case:
    return Case(
        id=UUID(record.id),
        case_number=record.case_number,
        title=record.title,
        client_name=record.client_name,
        jurisdiction=record.jurisdiction,
        forum=record.forum,
        matter_type=record.matter_type,
        related_case_numbers=record.related_case_numbers,
        status=CaseStatus(record.status),
        created_at=record.created_at,
    )


def _task(record: TaskRecord) -> Task:
    return Task(
        id=UUID(record.id),
        case_id=UUID(record.case_id),
        title=record.title,
        due_date=record.due_date,
        assignee=record.assignee,
        completed=record.completed,
    )


def create_firm(session: Session, payload: FirmCreate) -> Firm:
    now = datetime.now(UTC)
    record = FirmRecord(name=payload.name, created_at=now)
    session.add(record)
    session.commit()
    return Firm(id=UUID(record.id), name=record.name, created_at=now)


def _user(record: UserRecord) -> User:
    return User(
        id=UUID(record.id),
        firm_id=UUID(record.firm_id),
        name=record.name,
        email=record.email,
        role=UserRole(record.role),
        active=record.active,
    )


def register_firm(session: Session, payload: FirmRegistration) -> FirmCredential:
    now = datetime.now(UTC)
    firm = FirmRecord(name=payload.firm_name, created_at=now)
    session.add(firm)
    session.flush()
    token, digest = issue_token()
    admin = UserRecord(
        firm_id=firm.id,
        name=payload.admin_name,
        email=payload.admin_email.casefold(),
        role=UserRole.ADMIN.value,
        token_hash=digest,
        active=True,
    )
    session.add(admin)
    session.commit()
    return FirmCredential(
        firm=Firm(id=UUID(firm.id), name=firm.name, created_at=firm.created_at),
        administrator=_user(admin),
        api_token=token,
    )


def create_user(
    session: Session, firm_id: UUID, actor: str, payload: UserCreate
) -> UserCredential:
    token, digest = issue_token()
    record = UserRecord(
        firm_id=str(firm_id),
        name=payload.name,
        email=payload.email.casefold(),
        role=payload.role.value,
        token_hash=digest,
        active=True,
    )
    session.add(record)
    try:
        session.flush()
        audit(
            session,
            firm_id=firm_id,
            actor=actor,
            action="user.created",
            resource_type="user",
            resource_id=UUID(record.id),
            details={"role": payload.role.value},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("El correo ya existe en el bufete") from exc
    return UserCredential(user=_user(record), api_token=token)


def firm_exists(session: Session, firm_id: UUID) -> bool:
    return session.get(FirmRecord, str(firm_id)) is not None


def audit(
    session: Session,
    *,
    firm_id: UUID,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: UUID,
    details: dict[str, str] | None = None,
) -> None:
    session.add(
        AuditRecord(
            firm_id=str(firm_id),
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            occurred_at=datetime.now(UTC),
            details=details or {},
        )
    )


def create_case(session: Session, firm_id: UUID, actor: str, payload: CaseCreate) -> Case:
    now = datetime.now(UTC)
    record = CaseRecord(
        firm_id=str(firm_id),
        created_at=now,
        status=CaseStatus.OPEN.value,
        **payload.model_dump(mode="json"),
    )
    session.add(record)
    try:
        session.flush()
        audit(
            session,
            firm_id=firm_id,
            actor=actor,
            action="case.created",
            resource_type="case",
            resource_id=UUID(record.id),
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateCaseNumberError(payload.case_number) from exc
    return _case(record)


def list_cases(session: Session, firm_id: UUID) -> list[Case]:
    statement = (
        select(CaseRecord)
        .where(CaseRecord.firm_id == str(firm_id))
        .order_by(CaseRecord.created_at.desc())
    )
    return [_case(record) for record in session.scalars(statement)]


def get_case(session: Session, firm_id: UUID, case_id: UUID) -> Case | None:
    statement = select(CaseRecord).where(
        CaseRecord.id == str(case_id), CaseRecord.firm_id == str(firm_id)
    )
    record = session.scalar(statement)
    return _case(record) if record else None


def create_task(
    session: Session, firm_id: UUID, case_id: UUID, actor: str, payload: TaskCreate
) -> Task:
    record = TaskRecord(
        firm_id=str(firm_id), case_id=str(case_id), completed=False, **payload.model_dump()
    )
    session.add(record)
    session.flush()
    audit(
        session,
        firm_id=firm_id,
        actor=actor,
        action="task.created",
        resource_type="task",
        resource_id=UUID(record.id),
        details={"case_id": str(case_id)},
    )
    session.commit()
    return _task(record)


def list_tasks(session: Session, firm_id: UUID, case_id: UUID) -> list[Task]:
    statement = select(TaskRecord).where(
        TaskRecord.firm_id == str(firm_id), TaskRecord.case_id == str(case_id)
    )
    return [_task(record) for record in session.scalars(statement)]


def list_audit_events(session: Session, firm_id: UUID) -> list[AuditEvent]:
    statement = (
        select(AuditRecord)
        .where(AuditRecord.firm_id == str(firm_id))
        .order_by(AuditRecord.occurred_at.desc())
    )
    return [
        AuditEvent(
            id=UUID(record.id),
            firm_id=UUID(record.firm_id),
            actor=record.actor,
            action=record.action,
            resource_type=record.resource_type,
            resource_id=UUID(record.resource_id),
            occurred_at=record.occurred_at,
            details=record.details,
        )
        for record in session.scalars(statement)
    ]


def _document(record: DocumentRecord) -> Document:
    return Document(
        id=UUID(record.id),
        case_id=UUID(record.case_id),
        filename=record.filename,
        media_type=record.media_type,
        size=record.size,
        sha256=record.sha256,
        scan_status=record.scan_status,
        created_at=record.created_at,
    )


def record_document(
    session: Session,
    *,
    firm_id: UUID,
    case_id: UUID,
    actor: str,
    filename: str,
    media_type: str,
    size: int,
    sha256: str,
    storage_key: str,
) -> Document:
    record = DocumentRecord(
        firm_id=str(firm_id),
        case_id=str(case_id),
        filename=filename,
        media_type=media_type,
        size=size,
        sha256=sha256,
        storage_key=storage_key,
        scan_status="quarantined",
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    audit(
        session,
        firm_id=firm_id,
        actor=actor,
        action="document.quarantined",
        resource_type="document",
        resource_id=UUID(record.id),
        details={"case_id": str(case_id), "sha256": sha256},
    )
    session.commit()
    return _document(record)


def list_documents(session: Session, firm_id: UUID, case_id: UUID) -> list[Document]:
    statement = select(DocumentRecord).where(
        DocumentRecord.firm_id == str(firm_id), DocumentRecord.case_id == str(case_id)
    )
    return [_document(record) for record in session.scalars(statement)]


def get_document_record(
    session: Session, firm_id: UUID, document_id: UUID
) -> DocumentRecord | None:
    return session.scalar(
        select(DocumentRecord).where(
            DocumentRecord.id == str(document_id),
            DocumentRecord.firm_id == str(firm_id),
        )
    )


def case_timeline(session: Session, firm_id: UUID, case_id: UUID) -> list[AuditEvent]:
    events = list_audit_events(session, firm_id)
    case_value = str(case_id)
    return [
        event
        for event in events
        if str(event.resource_id) == case_value or event.details.get("case_id") == case_value
    ]


def related_case_suggestions(
    session: Session, firm_id: UUID, case_id: UUID
) -> list[RelatedCaseSuggestion]:
    target = session.scalar(
        select(CaseRecord).where(
            CaseRecord.id == str(case_id), CaseRecord.firm_id == str(firm_id)
        )
    )
    if target is None:
        return []
    suggestions: list[RelatedCaseSuggestion] = []
    target_words = set(target.title.casefold().split())
    for candidate in session.scalars(
        select(CaseRecord).where(
            CaseRecord.firm_id == str(firm_id), CaseRecord.id != target.id
        )
    ):
        reasons: list[str] = []
        score = 0.0
        if candidate.client_name.casefold() == target.client_name.casefold():
            score += 0.7
            reasons.append("Mismo cliente")
        words = set(candidate.title.casefold().split())
        overlap = len(target_words & words) / max(len(target_words | words), 1)
        if overlap >= 0.5:
            score += 0.3 * overlap
            reasons.append("Título similar")
        if score >= 0.5:
            suggestions.append(
                RelatedCaseSuggestion(
                    case_id=UUID(candidate.id),
                    case_number=candidate.case_number,
                    title=candidate.title,
                    score=round(score, 3),
                    reasons=reasons,
                )
            )
    return sorted(suggestions, key=lambda item: item.score, reverse=True)


def _calendar_event(record: CalendarEventRecord) -> CalendarEvent:
    starts_at = (
        record.starts_at.replace(tzinfo=UTC)
        if record.starts_at.tzinfo is None
        else record.starts_at
    )
    ends_at = (
        record.ends_at.replace(tzinfo=UTC)
        if record.ends_at.tzinfo is None
        else record.ends_at
    )
    return CalendarEvent(
        id=UUID(record.id),
        firm_id=UUID(record.firm_id),
        case_id=UUID(record.case_id) if record.case_id else None,
        title=record.title,
        description=record.description,
        event_type=record.event_type,
        starts_at=starts_at,
        ends_at=ends_at,
        location=record.location,
        assigned_user_id=UUID(record.assigned_user_id) if record.assigned_user_id else None,
        reminder_minutes=record.reminder_minutes,
        legal_authority=record.legal_authority,
        calculation_summary=record.calculation_summary,
        status=record.status,
        created_by=UUID(record.created_by),
        confirmed_by=UUID(record.confirmed_by) if record.confirmed_by else None,
        confirmed_at=record.confirmed_at,
        created_at=record.created_at,
    )


def create_calendar_event(
    session: Session, firm_id: UUID, creator_id: UUID, actor: str, payload: CalendarEventCreate
) -> CalendarEvent:
    if payload.case_id and get_case(session, firm_id, payload.case_id) is None:
        raise ValueError("Expediente no encontrado")
    if payload.assigned_user_id:
        assigned = session.scalar(
            select(UserRecord).where(
                UserRecord.id == str(payload.assigned_user_id),
                UserRecord.firm_id == str(firm_id),
                UserRecord.active.is_(True),
            )
        )
        if assigned is None:
            raise ValueError("Persona asignada no pertenece al bufete")
    values = payload.model_dump(mode="json", exclude={"starts_at", "ends_at"})
    record = CalendarEventRecord(
        firm_id=str(firm_id),
        created_by=str(creator_id),
        status=CalendarEventStatus.TENTATIVE.value,
        created_at=datetime.now(UTC),
        starts_at=payload.starts_at.astimezone(UTC),
        ends_at=payload.ends_at.astimezone(UTC),
        **values,
    )
    session.add(record)
    session.flush()
    audit(
        session,
        firm_id=firm_id,
        actor=actor,
        action="calendar_event.created",
        resource_type="calendar_event",
        resource_id=UUID(record.id),
        details={"case_id": record.case_id or "", "event_type": record.event_type},
    )
    session.commit()
    return _calendar_event(record)


def list_calendar_events(
    session: Session,
    firm_id: UUID,
    starts_after: datetime,
    starts_before: datetime,
    case_id: UUID | None = None,
    assigned_user_id: UUID | None = None,
) -> list[CalendarEvent]:
    statement = (
        select(CalendarEventRecord)
        .where(
            CalendarEventRecord.firm_id == str(firm_id),
            CalendarEventRecord.starts_at < starts_before,
            CalendarEventRecord.ends_at > starts_after,
            CalendarEventRecord.status != CalendarEventStatus.CANCELLED.value,
        )
        .order_by(CalendarEventRecord.starts_at)
    )
    if case_id:
        statement = statement.where(CalendarEventRecord.case_id == str(case_id))
    if assigned_user_id:
        statement = statement.where(
            CalendarEventRecord.assigned_user_id == str(assigned_user_id)
        )
    return [_calendar_event(record) for record in session.scalars(statement)]


def confirm_calendar_event(
    session: Session, firm_id: UUID, event_id: UUID, confirmer_id: UUID, actor: str
) -> CalendarEvent | None:
    record = session.scalar(
        select(CalendarEventRecord).where(
            CalendarEventRecord.id == str(event_id),
            CalendarEventRecord.firm_id == str(firm_id),
        )
    )
    if record is None:
        return None
    record.status = CalendarEventStatus.CONFIRMED.value
    record.confirmed_by = str(confirmer_id)
    record.confirmed_at = datetime.now(UTC)
    audit(
        session,
        firm_id=firm_id,
        actor=actor,
        action="calendar_event.confirmed",
        resource_type="calendar_event",
        resource_id=event_id,
        details={"case_id": record.case_id or ""},
    )
    session.commit()
    return _calendar_event(record)


def calendar_conflicts(
    session: Session, firm_id: UUID, starts_after: datetime, starts_before: datetime
) -> list[CalendarConflict]:
    records = list(
        session.scalars(
            select(CalendarEventRecord).where(
                CalendarEventRecord.firm_id == str(firm_id),
                CalendarEventRecord.assigned_user_id.is_not(None),
                CalendarEventRecord.starts_at < starts_before,
                CalendarEventRecord.ends_at > starts_after,
                CalendarEventRecord.status != CalendarEventStatus.CANCELLED.value,
            )
        )
    )
    conflicts: list[CalendarConflict] = []
    for index, event in enumerate(records):
        for other in records[index + 1 :]:
            if event.assigned_user_id != other.assigned_user_id:
                continue
            if event.starts_at < other.ends_at and other.starts_at < event.ends_at:
                conflicts.append(
                    CalendarConflict(
                        event_id=UUID(event.id),
                        conflicting_event_id=UUID(other.id),
                        assigned_user_id=UUID(event.assigned_user_id),
                        starts_at=max(event.starts_at, other.starts_at),
                        ends_at=min(event.ends_at, other.ends_at),
                    )
                )
    return conflicts


def due_calendar_reminders(
    session: Session, firm_id: UUID, at: datetime, window_minutes: int
) -> list[CalendarReminder]:
    window_end = at + timedelta(minutes=window_minutes)
    records = session.scalars(
        select(CalendarEventRecord).where(
            CalendarEventRecord.firm_id == str(firm_id),
            CalendarEventRecord.starts_at > at,
            CalendarEventRecord.starts_at <= at + timedelta(days=366),
            CalendarEventRecord.status != CalendarEventStatus.CANCELLED.value,
        )
    )
    reminders: list[CalendarReminder] = []
    for record in records:
        starts_at = (
            record.starts_at.replace(tzinfo=UTC)
            if record.starts_at.tzinfo is None
            else record.starts_at
        )
        for minutes in record.reminder_minutes:
            due_at = starts_at - timedelta(minutes=minutes)
            if at <= due_at < window_end:
                reminders.append(
                    CalendarReminder(
                        event_id=UUID(record.id),
                        reminder_minutes=minutes,
                        due_at=due_at,
                        title=record.title,
                        assigned_user_id=(
                            UUID(record.assigned_user_id) if record.assigned_user_id else None
                        ),
                    )
                )
    return sorted(reminders, key=lambda item: item.due_at)
