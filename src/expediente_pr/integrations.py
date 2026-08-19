from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from enum import StrEnum
from urllib.parse import quote, urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .records import (
    CalendarEventRecord,
    CommunicationRecord,
    ExternalEventLinkRecord,
    IntegrationConnectionRecord,
)


class IntegrationConfigurationError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


class IntegrationProvider(StrEnum):
    GOOGLE = "google"
    WHATSAPP = "whatsapp"


class ConnectionView(BaseModel):
    id: UUID
    provider: IntegrationProvider
    display_name: str | None
    scopes: list[str]
    status: str
    configuration: dict[str, str]


class AuthorizationURL(BaseModel):
    url: str


class GmailMessage(BaseModel):
    case_id: UUID | None = None
    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=50_000)


class WhatsAppConnect(BaseModel):
    code: str = Field(min_length=4, max_length=4096)
    phone_number_id: str = Field(min_length=1, max_length=200)
    waba_id: str = Field(min_length=1, max_length=200)


class WhatsAppTemplate(BaseModel):
    case_id: UUID | None = None
    to: str = Field(pattern=r"^[1-9][0-9]{7,15}$")
    template_name: str = Field(min_length=1, max_length=512)
    language_code: str = Field(default="es", min_length=2, max_length=20)
    parameters: list[str] = Field(default_factory=list, max_length=20)


class DeliveryResult(BaseModel):
    provider: IntegrationProvider
    external_id: str
    status: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise IntegrationConfigurationError(f"Falta configurar {name}")
    return value


def _fernet() -> Fernet:
    try:
        return Fernet(_required("EXPEDIENTE_TOKEN_ENCRYPTION_KEY").encode())
    except (ValueError, TypeError) as exc:
        raise IntegrationConfigurationError(
            "EXPEDIENTE_TOKEN_ENCRYPTION_KEY no es una clave Fernet válida"
        ) from exc


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise IntegrationConfigurationError("No se pudo descifrar la credencial") from exc


def create_oauth_state(firm_id: UUID, user_id: UUID, provider: IntegrationProvider) -> str:
    payload = {
        "firm_id": str(firm_id),
        "user_id": str(user_id),
        "provider": provider.value,
        "expires": int(time.time()) + 600,
        "nonce": base64.urlsafe_b64encode(os.urandom(18)).decode(),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).decode()
    signature = hmac.new(
        _required("EXPEDIENTE_OAUTH_STATE_SECRET").encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def verify_oauth_state(state: str, provider: IntegrationProvider) -> tuple[UUID, UUID]:
    encoded, separator, signature = state.partition(".")
    if not separator:
        raise ValueError("Estado OAuth inválido")
    expected = hmac.new(
        _required("EXPEDIENTE_OAUTH_STATE_SECRET").encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Firma OAuth inválida")
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded))
        if payload["provider"] != provider.value or payload["expires"] < int(time.time()):
            raise ValueError("Estado OAuth expirado o de otro proveedor")
        return UUID(payload["firm_id"]), UUID(payload["user_id"])
    except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Estado OAuth inválido") from exc


def google_authorization_url(firm_id: UUID, user_id: UUID) -> str:
    query = urlencode(
        {
            "client_id": _required("GOOGLE_CLIENT_ID"),
            "redirect_uri": _required("GOOGLE_REDIRECT_URI"),
            "response_type": "code",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "scope": " ".join(
                [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/gmail.send",
                ]
            ),
            "state": create_oauth_state(firm_id, user_id, IntegrationProvider.GOOGLE),
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def exchange_google_code(code: str) -> dict[str, object]:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": _required("GOOGLE_CLIENT_ID"),
            "client_secret": _required("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": _required("GOOGLE_REDIRECT_URI"),
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if response.is_error:
        raise ProviderError("Google rechazó el intercambio de autorización")
    return response.json()


def _view(record: IntegrationConnectionRecord) -> ConnectionView:
    safe_configuration = {
        key: value
        for key, value in (record.configuration or {}).items()
        if key in {"calendar_id", "phone_number_id", "waba_id"}
    }
    return ConnectionView(
        id=UUID(record.id),
        provider=IntegrationProvider(record.provider),
        display_name=record.display_name,
        scopes=record.scopes or [],
        status=record.status,
        configuration=safe_configuration,
    )


def list_connections(session: Session, firm_id: UUID, user_id: UUID) -> list[ConnectionView]:
    records = session.scalars(
        select(IntegrationConnectionRecord).where(
            IntegrationConnectionRecord.firm_id == str(firm_id),
            IntegrationConnectionRecord.user_id == str(user_id),
        )
    )
    return [_view(record) for record in records]


def disconnect(
    session: Session,
    firm_id: UUID,
    user_id: UUID,
    provider: IntegrationProvider,
) -> None:
    record = connection_record(session, firm_id, user_id, provider)
    record.status = "revoked"
    record.encrypted_access_token = encrypt_secret("revoked")
    record.encrypted_refresh_token = None
    record.updated_at = datetime.now(UTC)
    session.commit()


def upsert_connection(
    session: Session,
    *,
    firm_id: UUID,
    user_id: UUID,
    provider: IntegrationProvider,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    scopes: list[str] | None = None,
    configuration: dict[str, str] | None = None,
) -> ConnectionView:
    record = session.scalar(
        select(IntegrationConnectionRecord).where(
            IntegrationConnectionRecord.firm_id == str(firm_id),
            IntegrationConnectionRecord.user_id == str(user_id),
            IntegrationConnectionRecord.provider == provider.value,
        )
    )
    now = datetime.now(UTC)
    if record is None:
        record = IntegrationConnectionRecord(
            firm_id=str(firm_id),
            user_id=str(user_id),
            provider=provider.value,
            encrypted_access_token=encrypt_secret(access_token),
            created_at=now,
            updated_at=now,
        )
        session.add(record)
    else:
        record.encrypted_access_token = encrypt_secret(access_token)
        record.updated_at = now
    if refresh_token:
        record.encrypted_refresh_token = encrypt_secret(refresh_token)
    record.scopes = scopes or record.scopes or []
    record.configuration = configuration or record.configuration or {}
    record.token_expires_at = now + timedelta(seconds=expires_in) if expires_in else None
    record.status = "active"
    session.commit()
    session.refresh(record)
    return _view(record)


def connection_record(
    session: Session,
    firm_id: UUID,
    user_id: UUID,
    provider: IntegrationProvider,
) -> IntegrationConnectionRecord:
    record = session.scalar(
        select(IntegrationConnectionRecord).where(
            IntegrationConnectionRecord.firm_id == str(firm_id),
            IntegrationConnectionRecord.user_id == str(user_id),
            IntegrationConnectionRecord.provider == provider.value,
            IntegrationConnectionRecord.status == "active",
        )
    )
    if record is None:
        raise ValueError(f"No hay conexión activa con {provider.value}")
    return record


def google_access_token(
    session: Session, connection: IntegrationConnectionRecord
) -> str:
    expires_at = connection.token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if not expires_at or expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return decrypt_secret(connection.encrypted_access_token)
    if not connection.encrypted_refresh_token:
        connection.status = "reauthorization_required"
        session.commit()
        raise ProviderError("Google requiere volver a autorizar la conexión")
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": _required("GOOGLE_CLIENT_ID"),
            "client_secret": _required("GOOGLE_CLIENT_SECRET"),
            "refresh_token": decrypt_secret(connection.encrypted_refresh_token),
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if response.is_error:
        connection.status = "reauthorization_required"
        session.commit()
        raise ProviderError("Google rechazó la renovación de la conexión")
    token = response.json()
    connection.encrypted_access_token = encrypt_secret(token["access_token"])
    connection.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(token.get("expires_in", 3600))
    )
    connection.updated_at = datetime.now(UTC)
    session.commit()
    return token["access_token"]


def push_google_event(
    session: Session, firm_id: UUID, user_id: UUID, event_id: UUID
) -> DeliveryResult:
    connection = connection_record(
        session, firm_id, user_id, IntegrationProvider.GOOGLE
    )
    event = session.scalar(
        select(CalendarEventRecord).where(
            CalendarEventRecord.id == str(event_id),
            CalendarEventRecord.firm_id == str(firm_id),
        )
    )
    if event is None:
        raise ValueError("Evento no encontrado")
    link = session.scalar(
        select(ExternalEventLinkRecord).where(
            ExternalEventLinkRecord.connection_id == connection.id,
            ExternalEventLinkRecord.calendar_event_id == event.id,
        )
    )
    calendar_id = connection.configuration.get("calendar_id", "primary")
    base_url = (
        "https://www.googleapis.com/calendar/v3/calendars/"
        f"{quote(calendar_id, safe='')}/events"
    )
    payload = {
        "summary": event.title,
        "description": event.description,
        "location": event.location,
        "start": {"dateTime": event.starts_at.isoformat()},
        "end": {"dateTime": event.ends_at.isoformat()},
        "extendedProperties": {
            "private": {
                "expediente_pr_event_id": event.id,
                "expediente_pr_firm_id": event.firm_id,
            }
        },
    }
    headers = {"Authorization": f"Bearer {google_access_token(session, connection)}"}
    if link:
        response = httpx.put(f"{base_url}/{link.external_id}", json=payload, headers=headers)
    else:
        response = httpx.post(base_url, json=payload, headers=headers)
    if response.is_error:
        raise ProviderError("Google Calendar rechazó la sincronización")
    result = response.json()
    if link is None:
        link = ExternalEventLinkRecord(
            firm_id=str(firm_id),
            connection_id=connection.id,
            calendar_event_id=event.id,
            external_id=result["id"],
            updated_at=datetime.now(UTC),
        )
        session.add(link)
    link.etag = result.get("etag")
    link.updated_at = datetime.now(UTC)
    session.commit()
    return DeliveryResult(
        provider=IntegrationProvider.GOOGLE,
        external_id=result["id"],
        status="synced",
    )


def send_gmail(
    session: Session, firm_id: UUID, user_id: UUID, message: GmailMessage
) -> DeliveryResult:
    connection = connection_record(
        session, firm_id, user_id, IntegrationProvider.GOOGLE
    )
    email = EmailMessage()
    email["To"] = message.to
    email["Subject"] = message.subject
    email.set_content(message.body)
    raw = base64.urlsafe_b64encode(email.as_bytes()).decode().rstrip("=")
    response = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        json={"raw": raw},
        headers={
            "Authorization": f"Bearer {google_access_token(session, connection)}"
        },
        timeout=20,
    )
    if response.is_error:
        raise ProviderError("Gmail rechazó el envío")
    external_id = response.json()["id"]
    session.add(
        CommunicationRecord(
            firm_id=str(firm_id),
            case_id=str(message.case_id) if message.case_id else None,
            connection_id=connection.id,
            channel="gmail",
            direction="outbound",
            external_id=external_id,
            recipient=message.to,
            subject=message.subject,
            status="sent",
            metadata_json={},
            occurred_at=datetime.now(UTC),
        )
    )
    session.commit()
    return DeliveryResult(
        provider=IntegrationProvider.GOOGLE,
        external_id=external_id,
        status="sent",
    )


def exchange_meta_code(code: str) -> str:
    version = os.getenv("META_GRAPH_VERSION", "v23.0")
    response = httpx.get(
        f"https://graph.facebook.com/{version}/oauth/access_token",
        params={
            "client_id": _required("META_APP_ID"),
            "client_secret": _required("META_APP_SECRET"),
            "code": code,
        },
        timeout=20,
    )
    if response.is_error:
        raise ProviderError("Meta rechazó el código de WhatsApp")
    return response.json()["access_token"]


def send_whatsapp_template(
    session: Session, firm_id: UUID, user_id: UUID, request: WhatsAppTemplate
) -> DeliveryResult:
    connection = connection_record(
        session, firm_id, user_id, IntegrationProvider.WHATSAPP
    )
    phone_number_id = connection.configuration.get("phone_number_id")
    if not phone_number_id:
        raise IntegrationConfigurationError("Falta phone_number_id de WhatsApp")
    version = os.getenv("META_GRAPH_VERSION", "v23.0")
    components = []
    if request.parameters:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": parameter}
                    for parameter in request.parameters
                ],
            }
        )
    response = httpx.post(
        f"https://graph.facebook.com/{version}/{phone_number_id}/messages",
        json={
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "template",
            "template": {
                "name": request.template_name,
                "language": {"code": request.language_code},
                "components": components,
            },
        },
        headers={
            "Authorization": f"Bearer {decrypt_secret(connection.encrypted_access_token)}"
        },
        timeout=20,
    )
    if response.is_error:
        raise ProviderError("WhatsApp rechazó el mensaje")
    external_id = response.json()["messages"][0]["id"]
    session.add(
        CommunicationRecord(
            firm_id=str(firm_id),
            case_id=str(request.case_id) if request.case_id else None,
            connection_id=connection.id,
            channel="whatsapp",
            direction="outbound",
            external_id=external_id,
            recipient=request.to,
            subject=None,
            status="accepted",
            metadata_json={"template": request.template_name},
            occurred_at=datetime.now(UTC),
        )
    )
    session.commit()
    return DeliveryResult(
        provider=IntegrationProvider.WHATSAPP,
        external_id=external_id,
        status="accepted",
    )


def verify_meta_signature(body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        _required("META_APP_SECRET").encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


def record_whatsapp_webhook(session: Session, payload: dict[str, object]) -> int:
    recorded = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                continue
            connections = session.scalars(
                select(IntegrationConnectionRecord).where(
                    IntegrationConnectionRecord.provider
                    == IntegrationProvider.WHATSAPP.value,
                    IntegrationConnectionRecord.status == "active",
                )
            )
            connection = next(
                (
                    item
                    for item in connections
                    if item.configuration.get("phone_number_id") == phone_number_id
                ),
                None,
            )
            if connection is None:
                continue
            for message in value.get("messages", []):
                external_id = message.get("id")
                duplicate = session.scalar(
                    select(CommunicationRecord).where(
                        CommunicationRecord.connection_id == connection.id,
                        CommunicationRecord.external_id == external_id,
                    )
                )
                if duplicate:
                    continue
                session.add(
                    CommunicationRecord(
                        firm_id=connection.firm_id,
                        case_id=None,
                        connection_id=connection.id,
                        channel="whatsapp",
                        direction="inbound",
                        external_id=external_id,
                        recipient=message.get("from"),
                        subject=None,
                        status="received_unassigned",
                        metadata_json={"type": message.get("type", "unknown")},
                        occurred_at=datetime.now(UTC),
                    )
                )
                recorded += 1
    session.commit()
    return recorded
