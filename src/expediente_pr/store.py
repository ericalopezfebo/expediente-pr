from uuid import UUID

from .models import Case, CaseCreate, Task, TaskCreate


class MemoryStore:
    """Development store. Production will replace this behind the same interface."""

    def __init__(self) -> None:
        self.cases: dict[UUID, Case] = {}
        self.tasks: dict[UUID, Task] = {}

    def clear(self) -> None:
        self.cases.clear()
        self.tasks.clear()

    def create_case(self, payload: CaseCreate) -> Case:
        case = Case(**payload.model_dump())
        self.cases[case.id] = case
        return case

    def list_cases(self) -> list[Case]:
        return sorted(self.cases.values(), key=lambda case: case.created_at, reverse=True)

    def get_case(self, case_id: UUID) -> Case | None:
        return self.cases.get(case_id)

    def create_task(self, case_id: UUID, payload: TaskCreate) -> Task:
        task = Task(case_id=case_id, **payload.model_dump())
        self.tasks[task.id] = task
        return task

    def list_tasks(self, case_id: UUID) -> list[Task]:
        return [task for task in self.tasks.values() if task.case_id == case_id]


store = MemoryStore()

