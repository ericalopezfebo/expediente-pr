from datetime import UTC, datetime
from uuid import uuid4

from expediente_pr.ical import build_calendar
from expediente_pr.models import CalendarEvent


def test_ical_escapes_details() -> None:
    user_id = uuid4()
    event = CalendarEvent(
        id=uuid4(),
        firm_id=uuid4(),
        title="Vista, Sala 1",
        description="Línea uno\nLínea dos",
        event_type="hearing",
        starts_at=datetime(2026, 9, 1, 13, tzinfo=UTC),
        ends_at=datetime(2026, 9, 1, 14, tzinfo=UTC),
        reminder_minutes=[],
        status="confirmed",
        created_by=user_id,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    private = build_calendar([event])
    detailed = build_calendar([event], include_details=True)
    assert "Vista" not in private
    assert "SUMMARY:Vista\\, Sala 1" in detailed
    assert "DESCRIPTION:Línea uno\\nLínea dos" in detailed
