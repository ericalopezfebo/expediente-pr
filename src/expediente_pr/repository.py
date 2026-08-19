from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import issue_token
from .models import (
    AuditEvent,
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
