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


def test_timeline_and_related_case_suggestions() -> None:
    _, token = register_firm()
    first = client.post("/cases", json=case_payload("CASE-1"), headers=auth_headers(token))
    second_payload = case_payload("CASE-2")
    second_payload["title"] = "Cliente contra Agencia"
    second = client.post("/cases", json=second_payload, headers=auth_headers(token))
    assert second.status_code == 201

    first_id = first.json()["id"]
    client.post(
        f"/cases/{first_id}/tasks",
        json={"title": "Comparar expedientes"},
        headers=auth_headers(token),
    )
    timeline = client.get(f"/cases/{first_id}/timeline", headers=auth_headers(token))
    suggestions = client.get(
        f"/cases/{first_id}/related-suggestions", headers=auth_headers(token)
    )
    assert {item["action"] for item in timeline.json()} == {
        "case.created",
        "task.created",
    }
    assert suggestions.json()[0]["case_number"] == "CASE-2"
    assert "Mismo cliente" in suggestions.json()[0]["reasons"]


def test_document_is_validated_and_quarantined() -> None:
    _, token = register_firm()
    case = client.post("/cases", json=case_payload(), headers=auth_headers(token)).json()
    response = client.post(
        f"/cases/{case['id']}/documents",
        headers=auth_headers(token),
        files={"file": ("mocion.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["scan_status"] == "quarantined"
    assert len(response.json()["sha256"]) == 64


def test_disguised_document_is_rejected() -> None:
    _, token = register_firm()
    case = client.post("/cases", json=case_payload(), headers=auth_headers(token)).json()
    response = client.post(
        f"/cases/{case['id']}/documents",
        headers=auth_headers(token),
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 422


def test_dashboard_does_not_persist_token() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "localStorage" not in response.text
    assert "Expediente PR" in response.text


def test_legal_calendar_conflicts_confirmation_and_private_export() -> None:
    _, admin_token = register_firm()
    user_response = client.post(
        "/users",
        headers=auth_headers(admin_token),
        json={"name": "Abogada", "email": "lawyer@example.test", "role": "attorney"},
    )
    assigned_user_id = user_response.json()["user"]["id"]
    first_payload = {
        "title": "Vista confidencial",
        "description": "Detalles que no deben exportarse por defecto",
        "event_type": "hearing",
        "starts_at": "2026-09-01T09:00:00-04:00",
        "ends_at": "2026-09-01T10:00:00-04:00",
        "assigned_user_id": assigned_user_id,
        "reminder_minutes": [60],
    }
    second_payload = {
        **first_payload,
        "title": "Reunión superpuesta",
        "event_type": "meeting",
        "starts_at": "2026-09-01T09:30:00-04:00",
        "ends_at": "2026-09-01T10:30:00-04:00",
    }
    first = client.post(
        "/calendar/events", json=first_payload, headers=auth_headers(admin_token)
    )
    second = client.post(
        "/calendar/events", json=second_payload, headers=auth_headers(admin_token)
    )
    assert first.status_code == second.status_code == 201

    query = "start=2026-09-01T00:00:00-04:00&end=2026-09-02T00:00:00-04:00"
    conflicts = client.get(f"/calendar/conflicts?{query}", headers=auth_headers(admin_token))
    assert len(conflicts.json()) == 1

    confirmed = client.post(
        f"/calendar/events/{first.json()['id']}/confirm", headers=auth_headers(admin_token)
    )
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_by"] is not None

    private_ics = client.get(
        f"/calendar/export.ics?{query}", headers=auth_headers(admin_token)
    )
    assert "Evento de expediente" in private_ics.text
    assert "Vista confidencial" not in private_ics.text


def test_deadline_event_is_tentative_and_keeps_authority() -> None:
    _, token = register_firm()
    case = client.post("/cases", json=case_payload(), headers=auth_headers(token)).json()
    response = client.post(
        f"/cases/{case['id']}/deadline-events",
        headers=auth_headers(token),
        json={
            "title": "Término de prueba",
            "deadline": {
                "start_date": "2026-08-10",
                "days": 12,
                "start_event": "Notificación de prueba",
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "tentative"
    assert "Regla 68.1" in response.json()["legal_authority"]


def test_due_reminders_are_available_to_a_worker() -> None:
    _, token = register_firm()
    event = client.post(
        "/calendar/events",
        headers=auth_headers(token),
        json={
            "title": "Vista",
            "event_type": "hearing",
            "starts_at": "2026-09-01T10:00:00-04:00",
            "ends_at": "2026-09-01T11:00:00-04:00",
            "reminder_minutes": [60],
        },
    )
    assert event.status_code == 201
    response = client.get(
        "/calendar/reminders/due?at=2026-09-01T08:45:00-04:00&window_minutes=30",
        headers=auth_headers(token),
    )
    assert len(response.json()) == 1
    assert response.json()[0]["reminder_minutes"] == 60
