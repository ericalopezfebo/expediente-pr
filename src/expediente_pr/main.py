from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.orm import Session

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
from .repository import (
    DuplicateCaseNumberError,
    create_case as persist_case,
    create_firm,
    create_task as persist_task,
    firm_exists,
    get_case as find_case,
    list_audit_events,
    list_cases as find_cases,
    list_tasks as find_tasks,
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
    if not firm_exists(session, firm_id):
        raise HTTPException(status_code=404, detail="Bufete no encontrado")
    return firm_id


FirmDep = Annotated[UUID, Depends(require_firm)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/firms", response_model=Firm, status_code=status.HTTP_201_CREATED)
def register_firm(payload: FirmCreate, session: SessionDep) -> Firm:
    return create_firm(session, payload)


@app.post("/cases", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate, session: SessionDep, firm_id: FirmDep, actor: ActorHeader
) -> Case:
    try:
        return persist_case(session, firm_id, actor, payload)
    except DuplicateCaseNumberError as exc:
        raise HTTPException(
            status_code=409, detail="El número de caso ya existe en el bufete"
        ) from exc


@app.get("/cases", response_model=list[Case])
def list_cases(session: SessionDep, firm_id: FirmDep) -> list[Case]:
    return find_cases(session, firm_id)


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID, session: SessionDep, firm_id: FirmDep) -> Case:
    case = find_case(session, firm_id, case_id)
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
    if find_case(session, firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return persist_task(session, firm_id, case_id, actor, payload)


@app.get("/cases/{case_id}/tasks", response_model=list[Task])
def list_tasks(case_id: UUID, session: SessionDep, firm_id: FirmDep) -> list[Task]:
    if find_case(session, firm_id, case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return find_tasks(session, firm_id, case_id)


@app.get("/audit-events", response_model=list[AuditEvent])
def audit_events(session: SessionDep, firm_id: FirmDep) -> list[AuditEvent]:
    return list_audit_events(session, firm_id)


@app.post("/deadlines/calculate", response_model=DeadlineResult)
def deadline(payload: DeadlineRequest) -> DeadlineResult:
    return calculate_deadline(payload)
