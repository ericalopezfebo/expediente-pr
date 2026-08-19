import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from expediente_pr.integrations import (
    IntegrationConfigurationError,
    IntegrationProvider,
    create_oauth_state,
    decrypt_secret,
    encrypt_secret,
    google_authorization_url,
    receive_google_notification,
    upsert_connection,
    verify_meta_signature,
    verify_oauth_state,
    watch_google_calendar,
)
from expediente_pr.database import SessionLocal
from expediente_pr.records import FirmRecord, UserRecord


@pytest.fixture
def integration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPEDIENTE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("EXPEDIENTE_OAUTH_STATE_SECRET", "state-secret-for-tests")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.test/integrations/google/callback")
    monkeypatch.setenv("META_APP_SECRET", "meta-secret")
    monkeypatch.setenv(
        "GOOGLE_CALENDAR_WEBHOOK_URL",
        "https://example.test/webhooks/google/calendar",
    )


def test_secrets_are_encrypted(integration_environment: None) -> None:
    encrypted = encrypt_secret("refresh-token")
    assert "refresh-token" not in encrypted
    assert decrypt_secret(encrypted) == "refresh-token"


def test_oauth_state_is_bound_to_provider_and_identity(
    integration_environment: None,
) -> None:
    firm_id = uuid4()
    user_id = uuid4()
    state = create_oauth_state(firm_id, user_id, IntegrationProvider.GOOGLE)

    assert verify_oauth_state(state, IntegrationProvider.GOOGLE) == (firm_id, user_id)
    with pytest.raises(ValueError):
        verify_oauth_state(state, IntegrationProvider.WHATSAPP)
    with pytest.raises(ValueError):
        verify_oauth_state(f"{state}tampered", IntegrationProvider.GOOGLE)


def test_google_authorization_requests_minimum_supported_scopes(
    integration_environment: None,
) -> None:
    url = google_authorization_url(uuid4(), uuid4())
    assert "calendar.events" in url
    assert "gmail.send" in url
    assert "gmail.readonly" not in url
    assert "access_type=offline" in url


def test_whatsapp_webhook_signature(integration_environment: None) -> None:
    body = b'{"entry":[]}'
    signature = hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, f"sha256={signature}")
    assert not verify_meta_signature(body + b"x", f"sha256={signature}")
    assert not verify_meta_signature(body, None)


def test_missing_encryption_key_disables_secret_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXPEDIENTE_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(IntegrationConfigurationError):
        encrypt_secret("must-not-be-stored")


def test_google_notification_marks_linked_connection_for_sync(
    integration_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class Response:
        is_error = False

        @staticmethod
        def json() -> dict[str, str]:
            return {"resourceId": "resource-1", "expiration": "9999999999999"}

    def fake_post(*_: object, **kwargs: object) -> Response:
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr("expediente_pr.integrations.httpx.post", fake_post)
    now = datetime.now(UTC)
    with SessionLocal() as session:
        firm = FirmRecord(name="Bufete", created_at=now)
        session.add(firm)
        session.flush()
        user = UserRecord(
            firm_id=firm.id,
            name="Abogada",
            email="google@example.test",
            role="attorney",
            token_hash="google-watch-token",
            active=True,
        )
        session.add(user)
        session.commit()
        upsert_connection(
            session,
            firm_id=UUID(firm.id),
            user_id=UUID(user.id),
            provider=IntegrationProvider.GOOGLE,
            access_token="access-token",
            configuration={"calendar_id": "primary"},
        )
        result = watch_google_calendar(
            session, UUID(firm.id), UUID(user.id)
        )
        assert receive_google_notification(
            session,
            result["channel_id"],
            str(captured["token"]),
            "resource-1",
        )
