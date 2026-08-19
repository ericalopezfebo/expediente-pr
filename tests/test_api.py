from fastapi.testclient import TestClient

from expediente_pr.main import app

client = TestClient(app)


def register_firm(name: str = "Bufete de prueba") -> tuple[str, str]:
    response = client.post(
        "/firms/register",
        headers={"X-Bootstrap-Token": "test-bootstrap-secret"},
        json={
            "firm_name": name,
            "admin_name": "Administradora",
            "admin_email": f"admin-{name}@example.test",
        },
    )
    assert response.status_code == 201
    return response.json()["firm"]["id"], response.json()["api_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def create_user(admin_token: str, role: str, email: str) -> str:
    response = client.post(
        "/users",
        headers=auth_headers(admin_token),
        json={"name": role.title(), "email": email, "role": role},
    )
    assert response.status_code == 201
    return response.json()["api_token"]


def test_bootstrap_secret_is_required() -> None:
    response = client.post(
        "/firms/register",
        json={"firm_name": "F", "admin_name": "A", "admin_email": "a@example.test"},
    )
    assert response.status_code == 403


def test_case_task_and_audit_flow() -> None:
    _, token = register_firm()
    case_response = client.post("/cases", json=case_payload(), headers=auth_headers(token))
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    task_response = client.post(
        f"/cases/{case_id}/tasks",
        json={"title": "Revisar orden", "due_date": "2026-08-24", "assignee": "Abogada"},
        headers=auth_headers(token),
    )
    assert task_response.status_code == 201

    audit_response = client.get("/audit-events", headers=auth_headers(token))
    assert audit_response.status_code == 200
    assert {item["action"] for item in audit_response.json()} == {
        "case.created",
        "task.created",
    }


def test_authenticated_tenant_isolation() -> None:
    _, first_token = register_firm("Primer bufete")
    _, second_token = register_firm("Segundo bufete")
    case_response = client.post(
        "/cases", json=case_payload(), headers=auth_headers(first_token)
    )
    case_id = case_response.json()["id"]

    response = client.get(f"/cases/{case_id}", headers=auth_headers(second_token))
    assert response.status_code == 404


def test_roles_restrict_sensitive_operations() -> None:
    _, admin_token = register_firm()
    staff_token = create_user(admin_token, "staff", "staff@example.test")
    client_token = create_user(admin_token, "client", "client@example.test")

    staff_create = client.post(
        "/cases", json=case_payload(), headers=auth_headers(staff_token)
    )
    client_list = client.get("/cases", headers=auth_headers(client_token))
    client_audit = client.get("/audit-events", headers=auth_headers(client_token))
    assert staff_create.status_code == 403
    assert client_list.status_code == 403
    assert client_audit.status_code == 403


def test_invalid_token_is_rejected() -> None:
    response = client.get("/cases", headers=auth_headers("not-a-token"))
    assert response.status_code == 401
