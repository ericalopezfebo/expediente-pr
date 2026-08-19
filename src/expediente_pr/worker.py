from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .integrations import (
    GmailMessage,
    IntegrationConfigurationError,
    ProviderError,
    send_gmail,
)
from .records import (
    CalendarEventRecord,
    IntegrationConnectionRecord,
    ReminderDeliveryRecord,
    UserRecord,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def enqueue_due_reminders(
    session: Session, now: datetime, lookahead_minutes: int = 15
) -> int:
    end = now + timedelta(minutes=lookahead_minutes)
    events = session.scalars(
        select(CalendarEventRecord).where(
            CalendarEventRecord.status != "cancelled",
            CalendarEventRecord.assigned_user_id.is_not(None),
            CalendarEventRecord.starts_at > now,
        )
    )
    created = 0
    for event in events:
        for offset in event.reminder_minutes or []:
            scheduled_at = _aware(event.starts_at) - timedelta(minutes=offset)
            if not now <= scheduled_at < end:
                continue
            session.add(
                ReminderDeliveryRecord(
                    firm_id=event.firm_id,
                    calendar_event_id=event.id,
                    reminder_minutes=offset,
                    channel="gmail",
                    status="queued",
                    attempts=0,
                    scheduled_at=scheduled_at,
                    created_at=now,
                    updated_at=now,
                )
            )
            try:
                session.commit()
                created += 1
            except IntegrityError:
                session.rollback()
    return created


def deliver_queued_reminders(
    session: Session, now: datetime, maximum_attempts: int = 5
) -> dict[str, int]:
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    deliveries = list(
        session.scalars(
            select(ReminderDeliveryRecord).where(
                ReminderDeliveryRecord.status.in_(["queued", "retry"]),
                ReminderDeliveryRecord.scheduled_at <= now + timedelta(minutes=15),
                ReminderDeliveryRecord.attempts < maximum_attempts,
            )
        )
    )
    for delivery in deliveries:
        event = session.get(CalendarEventRecord, delivery.calendar_event_id)
        user = session.get(UserRecord, event.assigned_user_id) if event else None
        if event is None or event.status == "cancelled" or user is None or not user.active:
            delivery.status = "cancelled"
            delivery.updated_at = now
            session.commit()
            counts["skipped"] += 1
            continue
        connection = session.scalar(
            select(IntegrationConnectionRecord).where(
                IntegrationConnectionRecord.firm_id == delivery.firm_id,
                IntegrationConnectionRecord.user_id == user.id,
                IntegrationConnectionRecord.provider == "google",
                IntegrationConnectionRecord.status == "active",
            )
        )
        if connection is None:
            delivery.status = "retry"
            delivery.last_error = "La persona asignada no ha conectado Google"
            delivery.attempts += 1
            delivery.last_attempt_at = now
            delivery.updated_at = now
            session.commit()
            counts["failed"] += 1
            continue
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.last_attempt_at = now
        delivery.updated_at = now
        session.commit()
        try:
            send_gmail(
                session,
                firm_id=UUID(delivery.firm_id),
                user_id=UUID(user.id),
                message=GmailMessage(
                    case_id=None,
                    to=user.email,
                    subject="Recordatorio de calendario — Expediente PR",
                    body=(
                        "Tiene un evento próximo en Expediente PR. "
                        "Acceda al sistema para consultar los detalles. "
                        "Este correo omite información confidencial deliberadamente."
                    ),
                ),
            )
            delivery.status = "sent"
            delivery.last_error = None
            counts["sent"] += 1
        except (IntegrationConfigurationError, ProviderError, ValueError) as exc:
            delivery.status = (
                "failed" if delivery.attempts >= maximum_attempts else "retry"
            )
            delivery.last_error = str(exc)[:1000]
            counts["failed"] += 1
        delivery.updated_at = datetime.now(UTC)
        session.commit()
    return counts


def run_once(now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(UTC)
    with SessionLocal() as session:
        enqueued = enqueue_due_reminders(session, current)
        result = deliver_queued_reminders(session, current)
        return {"enqueued": enqueued, **result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Procesa recordatorios de Expediente PR")
    parser.add_argument("--once", action="store_true", help="Ejecuta un ciclo y termina")
    parser.parse_args()
    print(run_once())


if __name__ == "__main__":
    main()
