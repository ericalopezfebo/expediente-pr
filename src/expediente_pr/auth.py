import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import UserRole
from .records import UserRecord


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    firm_id: UUID
    name: str
    email: str
    role: UserRole


def issue_token() -> tuple[str, str]:
    token = f"exp_{secrets.token_urlsafe(32)}"
    return token, token_digest(token)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_bootstrap_token(candidate: str | None) -> None:
    expected = os.getenv("EXPEDIENTE_BOOTSTRAP_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Registro inicial deshabilitado")
    if candidate is None or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=403, detail="Credencial inicial inválida")


def authenticate(session: Session, authorization: str | None) -> Identity:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Se requiere Bearer token")
    record = session.scalar(
        select(UserRecord).where(
            UserRecord.token_hash == token_digest(token), UserRecord.active.is_(True)
        )
    )
    if record is None:
        raise HTTPException(status_code=401, detail="Credencial inválida")
    return Identity(
        user_id=UUID(record.id),
        firm_id=UUID(record.firm_id),
        name=record.name,
        email=record.email,
        role=UserRole(record.role),
    )
