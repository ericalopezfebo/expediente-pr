from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import repository
from .database import create_schema, get_session
from .deadlines import calculate_deadline
from .models import (
    AuditEvent,
    Case,
    CaseCreate,
    DeadlineRequest,
    DeadlineResult,
    Firm,
    FirmCreate,
    Task,
    TaskCreate,
)

SessionDep = Annotated[Session, Depends(get_session)]
FirmHeader = Annotated[UUID, Header(alias="X-Firm-ID")]
ActorHeader = Annotated[str, Header(alias="X-Actor", min_length=1, max_length=240)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="Expediente PR",
    version="0.2.0",
    description="API para la gestión auditable y aislada de expedientes jurídicos.",
    lifespan=lifespan,
)


def require_firm(session: SessionDep, firm_id: FirmHeader) -> UUID:
    if not repository.firm_exists(session, firm_id):
        raise HTTPException(status_code=404, detail="Bufete no encontrado")
    return firm_id


FirmDep = Annotated[UUID, Depends(require_firm)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/firms", response_model=Firm, status_code=status.HTTP_201_CREATED)
def register_firm(payload: FirmCreate, session: SessionDep) -> Firm:
    return repository.create_firm(session, payload)


@app.post("/cases", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate, session: SessionDep, firm_id: FirmDep, actor: ActorHeader
) -> Case:
    try:
        return repository.create_case(session, firm_id, actor, payload)
    except repository.DuplicateCaseNumberError as exc:
        raise HTTPException(
            status_code=409, detail="El número de caso ya existe en el bufete"
        ) from exc


@app.get("/cases", response_model=list[Case])
def list_cases(session: SessionDep, firm_id: FirmDep) -> list[Case]:
    return repository.list_cases(session, firm_id)


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID, session: SessionDep, firm_id: FirmDep) -> Case:
    case = repository.get_case(session, firm_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return case


@app.post("/cases/{case_id}/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(
    case_id: UUID,
    payload: TaskCreate,
    session: SessionDep,
    firm_id: FirmDep,
    actor: ActorHeader,
) -> Task:
    if repository.get_case(session, firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.create_task(session, firm_id, case_id, actor, payload)


@app.get("/cases/{case_id}/tasks", response_model=list[Task])
def list_tasks(case_id: UUID, session: SessionDep, firm_id: FirmDep) -> list[Task]:
    if repository.get_case(session, firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return repository.list_tasks(session, firm_id, case_id)


@app.get("/audit-events", response_model=list[AuditEvent])
def audit_events(session: SessionDep, firm_id: FirmDep) -> list[AuditEvent]:
    return repository.list_audit_events(session, firm_id)


@app.post("/deadlines/calculate", response_model=DeadlineResult)
def deadline(payload: DeadlineRequest) -> DeadlineResult:
    return calculate_deadline(payload)
