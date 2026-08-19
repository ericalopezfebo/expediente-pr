from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import auth, repository
from .database import create_schema, get_session
from .deadlines import calculate_deadline
from .models import (
    AuditEvent,
    Case,
    CaseCreate,
    DeadlineRequest,
    DeadlineResult,
    FirmCredential,
    FirmRegistration,
    Task,
    TaskCreate,
    UserCredential,
    UserCreate,
    UserRole,
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
    version="0.3.0",
    description="API para la gestión auditable y aislada de expedientes jurídicos.",
    lifespan=lifespan,
)


def current_identity(session: SessionDep, authorization: AuthorizationHeader) -> auth.Identity:
    return auth.authenticate(session, authorization)


IdentityDep = Annotated[auth.Identity, Depends(current_identity)]


def authorize(identity: auth.Identity, *roles: UserRole) -> None:
    if identity.role not in roles:
        raise HTTPException(status_code=403, detail="Permiso insuficiente")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/firms/register", response_model=FirmCredential, status_code=status.HTTP_201_CREATED)
def register_firm(
    payload: FirmRegistration, session: SessionDep, bootstrap_token: BootstrapHeader
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


@app.get("/audit-events", response_model=list[AuditEvent])
def audit_events(session: SessionDep, identity: IdentityDep) -> list[AuditEvent]:
    authorize(identity, UserRole.ADMIN)
    return repository.list_audit_events(session, identity.firm_id)


@app.post("/deadlines/calculate", response_model=DeadlineResult)
def deadline(payload: DeadlineRequest) -> DeadlineResult:
    return calculate_deadline(payload)
