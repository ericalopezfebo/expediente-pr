from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from expediente_pr.database import SessionLocal
from expediente_pr.records import (
    CalendarEventRecord,
    FirmRecord,
    ReminderDeliveryRecord,
    UserRecord,
)
from expediente_pr.worker import deliver_queued_reminders, enqueue_due_reminders


def _seed_due_event(now: datetime) -> None:
    with SessionLocal() as session:
        firm = FirmRecord(name="Bufete", created_at=now)
        session.add(firm)
        session.flush()
        user = UserRecord(
            firm_id=firm.id,
            name="Abogada",
            email="abogada@example.test",
            role="attorney",
            token_hash="worker-test-token",
            active=True,
        )
        session.add(user)
        session.flush()
        session.add(
            CalendarEventRecord(
                firm_id=firm.id,
                title="Evento confidencial",
                event_type="hearing",
                starts_at=now + timedelta(minutes=30),
                ends_at=now + timedelta(minutes=90),
                assigned_user_id=user.id,
                reminder_minutes=[20],
                status="confirmed",
                created_by=user.id,
                created_at=now,
            )
        )
        session.commit()


def test_worker_deduplicates_and_retries_without_google_connection() -> None:
    now = datetime.now(UTC)
    _seed_due_event(now)
    with SessionLocal() as session:
        assert enqueue_due_reminders(session, now) == 1
        assert enqueue_due_reminders(session, now) == 0
        result = deliver_queued_reminders(session, now)
        delivery = session.scalar(select(ReminderDeliveryRecord))

    assert result == {"sent": 0, "failed": 1, "skipped": 0}
    assert delivery is not None
    assert delivery.status == "retry"
    assert delivery.attempts == 1
    assert "conectado Google" in delivery.last_error
