from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from . import auth, repository
from .dashboard import DASHBOARD_HTML
from .database import create_schema, get_session
from .deadlines import UnknownDeadlineRuleError, calculate_deadline, list_rules
from .document_storage import (
    MAX_DOCUMENT_BYTES,
    UnsafeDocumentError,
    export_to_velum,
    save_quarantined,
)
from .ical import build_calendar
from .models import (
    AuditEvent,
    CalendarConflict,
    CalendarEvent,
    CalendarEventCreate,
    CalendarReminder,
    Case,
    CaseCreate,
    DeadlineEventCreate,
    DeadlineRequest,
    DeadlineResult,
    DeadlineRule,
    Document,
    FirmCredential,
    FirmRegistration,
    RelatedCaseSuggestion,
    Task,
    TaskCreate,
    UserCreate,
    UserCredential,
    UserRole,
    VelumExport,
)

SessionDep = Annotated[Session, Depends(get_session)]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]
BootstrapHeader = Annotated[str | None, Header(alias="X-Bootstrap-Token")]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="Expediente PR",
    version="0.4.0",
    description="API para la gestión auditable y aislada de expedientes jurídicos.",
    lifespan=lifespan,
)


def current_identity(
    session: SessionDep, authorization: AuthorizationHeader = None
) -> auth.Identity:
    return auth.authenticate(session, authorization)


IdentityDep = Annotated[auth.Identity, Depends(current_identity)]


def authorize(identity: auth.Identity, *roles: UserRole) -> None:
    if identity.role not in roles:
        raise HTTPException(status_code=403, detail="Permiso insuficiente")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(
        DASHBOARD_HTML,
        headers={
            "Content-Security-Policy": (
                "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
            )
        },
    )


@app.post("/firms/register", response_model=FirmCredential, status_code=status.HTTP_201_CREATED)
def register_firm(
    payload: FirmRegistration,
    session: SessionDep,
    bootstrap_token: BootstrapHeader = None,
) -> FirmCredential:
    auth.verify_bootstrap_token(bootstrap_token)
    return repository.register_firm(session, payload)


@app.post("/users", response_model=UserCredential, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, session: SessionDep, identity: IdentityDep
) -> UserCredential:
    authorize(identity, UserRole.ADMIN)
    try:
        return repository.create_user(session, identity.firm_id, identity.email, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/cases", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate, session: SessionDep, identity: IdentityDep
) -> Case:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY)
    try:
        return repository.create_case(session, identity.firm_id, identity.email, payload)
    except repository.DuplicateCaseNumberError as exc:
        raise HTTPException(
            status_code=409, detail="El número de caso ya existe en el bufete"
        ) from exc


@app.get("/cases", response_model=list[Case])
def list_cases(session: SessionDep, identity: IdentityDep) -> list[Case]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    return repository.list_cases(session, identity.firm_id)


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID, session: SessionDep, identity: IdentityDep) -> Case:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    case = repository.get_case(session, identity.firm_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return case


@app.post("/cases/{case_id}/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(
    case_id: UUID,
    payload: TaskCreate,
    session: SessionDep,
    identity: IdentityDep,
) -> Task:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.create_task(
        session, identity.firm_id, case_id, identity.email, payload
    )


@app.get("/cases/{case_id}/tasks", response_model=list[Task])
def list_tasks(case_id: UUID, session: SessionDep, identity: IdentityDep) -> list[Task]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.list_tasks(session, identity.firm_id, case_id)


@app.get("/cases/{case_id}/timeline", response_model=list[AuditEvent])
def case_timeline(case_id: UUID, session: SessionDep, identity: IdentityDep) -> list[AuditEvent]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.case_timeline(session, identity.firm_id, case_id)


@app.get("/cases/{case_id}/related-suggestions", response_model=list[RelatedCaseSuggestion])
def related_suggestions(
    case_id: UUID, session: SessionDep, identity: IdentityDep
) -> list[RelatedCaseSuggestion]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.related_case_suggestions(session, identity.firm_id, case_id)


@app.post(
    "/cases/{case_id}/documents", response_model=Document, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    case_id: UUID,
    session: SessionDep,
    identity: IdentityDep,
    file: Annotated[UploadFile, File()],
) -> Document:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    media_type = file.content_type or "application/octet-stream"
    try:
        storage_key, digest = save_quarantined(content, media_type)
    except UnsafeDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = Path(file.filename or "documento").name[:240]
    return repository.record_document(
        session,
        firm_id=identity.firm_id,
        case_id=case_id,
        actor=identity.email,
        filename=filename,
        media_type=media_type,
        size=len(content),
        sha256=digest,
        storage_key=storage_key,
    )


@app.get("/cases/{case_id}/documents", response_model=list[Document])
def documents(case_id: UUID, session: SessionDep, identity: IdentityDep) -> list[Document]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.list_documents(session, identity.firm_id, case_id)


@app.post("/documents/{document_id}/export-to-velum", response_model=VelumExport)
def velum_export(document_id: UUID, session: SessionDep, identity: IdentityDep) -> VelumExport:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY)
    record = repository.get_document_record(session, identity.firm_id, document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    try:
        target = export_to_velum(record.storage_key)
    except (UnsafeDocumentError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    repository.audit(
        session,
        firm_id=identity.firm_id,
        actor=identity.email,
        action="document.exported_to_velum",
        resource_type="document",
        resource_id=document_id,
        details={"sha256": record.sha256},
    )
    session.commit()
    return VelumExport(
        document_id=document_id,
        sha256=record.sha256,
        local_path=str(target),
        warning="La exportación local no confirma que VELUM haya procesado el documento.",
    )


@app.get("/audit-events", response_model=list[AuditEvent])
def audit_events(session: SessionDep, identity: IdentityDep) -> list[AuditEvent]:
    authorize(identity, UserRole.ADMIN)
    return repository.list_audit_events(session, identity.firm_id)


def _calendar_range(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="El intervalo requiere zona horaria")
    if end <= start or end - start > timedelta(days=366):
        raise HTTPException(status_code=422, detail="Intervalo inválido o mayor de un año")


@app.post("/calendar/events", response_model=CalendarEvent, status_code=status.HTTP_201_CREATED)
def create_calendar_event(
    payload: CalendarEventCreate, session: SessionDep, identity: IdentityDep
) -> CalendarEvent:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    try:
        return repository.create_calendar_event(
            session, identity.firm_id, identity.user_id, identity.email, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/calendar/events", response_model=list[CalendarEvent])
def calendar_events(
    session: SessionDep,
    identity: IdentityDep,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    case_id: UUID | None = None,
    assigned_user_id: UUID | None = None,
) -> list[CalendarEvent]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    _calendar_range(start, end)
    return repository.list_calendar_events(
        session,
        identity.firm_id,
        start,
        end,
        case_id=case_id,
        assigned_user_id=assigned_user_id,
    )


@app.post("/calendar/events/{event_id}/confirm", response_model=CalendarEvent)
def confirm_calendar_event(
    event_id: UUID, session: SessionDep, identity: IdentityDep
) -> CalendarEvent:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY)
    event = repository.confirm_calendar_event(
        session, identity.firm_id, event_id, identity.user_id, identity.email
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return event


@app.get("/calendar/conflicts", response_model=list[CalendarConflict])
def calendar_conflict_list(
    session: SessionDep,
    identity: IdentityDep,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
) -> list[CalendarConflict]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    _calendar_range(start, end)
    return repository.calendar_conflicts(session, identity.firm_id, start, end)


@app.get("/calendar/reminders/due", response_model=list[CalendarReminder])
def due_reminders(
    session: SessionDep,
    identity: IdentityDep,
    at: Annotated[datetime, Query()],
    window_minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
) -> list[CalendarReminder]:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    if at.tzinfo is None:
        raise HTTPException(status_code=422, detail="La fecha requiere zona horaria")
    return repository.due_calendar_reminders(
        session, identity.firm_id, at, window_minutes
    )


@app.post(
    "/cases/{case_id}/deadline-events",
    response_model=CalendarEvent,
    status_code=status.HTTP_201_CREATED,
)
def create_deadline_event(
    case_id: UUID,
    payload: DeadlineEventCreate,
    session: SessionDep,
    identity: IdentityDep,
) -> CalendarEvent:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY)
    if repository.get_case(session, identity.firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    try:
        result = calculate_deadline(payload.deadline)
    except UnknownDeadlineRuleError as exc:
        raise HTTPException(status_code=422, detail="Regla de términos desconocida") from exc
    timezone = ZoneInfo("America/Puerto_Rico")
    starts_at = datetime.combine(result.due_date, time(17, 0), tzinfo=timezone)
    event_payload = CalendarEventCreate(
        case_id=case_id,
        title=payload.title,
        description="Término calculado; requiere confirmación profesional.",
        event_type="deadline",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        assigned_user_id=payload.assigned_user_id,
        reminder_minutes=payload.reminder_minutes,
        legal_authority=result.rule.authority,
        calculation_summary=" ".join(result.explanation),
    )
    return repository.create_calendar_event(
        session, identity.firm_id, identity.user_id, identity.email, event_payload
    )


@app.get("/calendar/export.ics")
def export_calendar(
    session: SessionDep,
    identity: IdentityDep,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    include_details: bool = False,
) -> Response:
    authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY, UserRole.STAFF)
    _calendar_range(start, end)
    if include_details:
        authorize(identity, UserRole.ADMIN, UserRole.ATTORNEY)
    events = repository.list_calendar_events(session, identity.firm_id, start, end)
    return Response(
        build_calendar(events, include_details=include_details),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="expediente-pr.ics"'},
    )


@app.post("/deadlines/calculate", response_model=DeadlineResult)
def deadline(payload: DeadlineRequest) -> DeadlineResult:
    try:
        return calculate_deadline(payload)
    except UnknownDeadlineRuleError as exc:
        raise HTTPException(status_code=422, detail="Regla de términos desconocida") from exc


@app.get("/deadline-rules", response_model=list[DeadlineRule])
def deadline_rules() -> list[DeadlineRule]:
    return list_rules()
