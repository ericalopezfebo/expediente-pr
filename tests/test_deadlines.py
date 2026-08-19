from datetime import date

from expediente_pr.deadlines import calculate_deadline
from expediente_pr.models import DeadlineRequest


def test_calendar_deadline_moves_weekend_to_monday() -> None:
    result = calculate_deadline(
        DeadlineRequest(
            start_date=date(2026, 8, 10),
            days=12,
            use_calendar_days=True,
            authority="Regla de prueba; no constituye una autoridad jurídica real",
        )
    )
    assert result.nominal_date == date(2026, 8, 22)
    assert result.due_date == date(2026, 8, 24)
    assert result.adjusted is True
    assert result.requires_attorney_review is True


def test_business_days_skip_weekends() -> None:
    result = calculate_deadline(
        DeadlineRequest(
            start_date=date(2026, 8, 14),
            days=2,
            use_calendar_days=False,
            authority="Regla de prueba",
        )
    )
    assert result.due_date == date(2026, 8, 18)

