from fastapi.testclient import TestClient

from expediente_pr.main import app

client = TestClient(app)


def create_firm(name: str = "Bufete de prueba") -> str:
    response = client.post("/firms", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def case_payload(number: str = "SJ2026CV00001") -> dict[str, object]:
    return {
        "case_number": number,
        "title": "Cliente v. Agencia",
        "client_name": "Cliente de prueba",
        "jurisdiction": "pr_courts",
        "forum": "Tribunal de Primera Instancia",
        "matter_type": "procedimiento civil",
        "related_case_numbers": ["PR-00-000002"],
    }


def headers(firm_id: str) -> dict[str, str]:
    return {"X-Firm-ID": firm_id, "X-Actor": "abogada@example.test"}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_case_task_and_audit_flow() -> None:
    firm_id = create_firm()
    case_response = client.post("/cases", json=case_payload(), headers=headers(firm_id))
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    task_response = client.post(
        f"/cases/{case_id}/tasks",
        json={"title": "Revisar orden", "due_date": "2026-08-24", "assignee": "Abogada"},
        headers=headers(firm_id),
    )
    assert task_response.status_code == 201

    audit_response = client.get("/audit-events", headers=headers(firm_id))
    assert audit_response.status_code == 200
    assert {item["action"] for item in audit_response.json()} == {
        "case.created",
        "task.created",
    }


def test_tenant_isolation_returns_not_found() -> None:
    first_firm = create_firm("Primer bufete")
    second_firm = create_firm("Segundo bufete")
    case_response = client.post("/cases", json=case_payload(), headers=headers(first_firm))
    case_id = case_response.json()["id"]

    response = client.get(f"/cases/{case_id}", headers=headers(second_firm))
    assert response.status_code == 404


def test_case_number_is_unique_within_firm_only() -> None:
    first_firm = create_firm("Primer bufete")
    second_firm = create_firm("Segundo bufete")
    first = client.post("/cases", json=case_payload(), headers=headers(first_firm))
    duplicate = client.post("/cases", json=case_payload(), headers=headers(first_firm))
    other_firm = client.post("/cases", json=case_payload(), headers=headers(second_firm))
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert other_firm.status_code == 201


def test_firm_header_is_required() -> None:
    response = client.get("/cases")
    assert response.status_code == 422
