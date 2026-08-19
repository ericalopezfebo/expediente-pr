from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from .deadlines import calculate_deadline
from .models import Case, CaseCreate, DeadlineRequest, DeadlineResult, Task, TaskCreate
from .store import store

app = FastAPI(
    title="Expediente PR",
    version="0.1.0",
    description="API inicial para la gestión verificable de expedientes jurídicos.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/cases", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate) -> Case:
    return store.create_case(payload)


@app.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return store.list_cases()


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID) -> Case:
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return case


@app.post("/cases/{case_id}/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(case_id: UUID, payload: TaskCreate) -> Task:
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return store.create_task(case_id, payload)


@app.get("/cases/{case_id}/tasks", response_model=list[Task])
def list_tasks(case_id: UUID) -> list[Task]:
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return store.list_tasks(case_id)


@app.post("/deadlines/calculate", response_model=DeadlineResult)
def deadline(payload: DeadlineRequest) -> DeadlineResult:
    return calculate_deadline(payload)

