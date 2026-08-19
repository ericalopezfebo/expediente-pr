from fastapi.testclient import TestClient

from expediente_pr.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_case_and_task_flow() -> None:
    case_response = client.post(
        "/cases",
        json={
            "case_number": "SJ2026CV00001",
            "title": "Cliente v. Agencia",
            "client_name": "Cliente de prueba",
            "jurisdiction": "pr_courts",
            "forum": "Tribunal de Primera Instancia",
            "matter_type": "procedimiento civil",
            "related_case_numbers": ["PR-00-000002"],
        },
    )
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    task_response = client.post(
        f"/cases/{case_id}/tasks",
        json={"title": "Revisar orden", "due_date": "2026-08-24", "assignee": "Abogada"},
    )
    assert task_response.status_code == 201
    assert task_response.json()["case_id"] == case_id

    list_response = client.get(f"/cases/{case_id}/tasks")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_unknown_case_is_404() -> None:
    response = client.get("/cases/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

