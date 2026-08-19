from datetime import date

import pytest

from expediente_pr.deadlines import UnknownDeadlineRuleError, calculate_deadline
from expediente_pr.models import DeadlineRequest


def request(**changes: object) -> DeadlineRequest:
    values: dict[str, object] = {
        "start_date": date(2026, 8, 10),
        "days": 12,
        "start_event": "Notificación de prueba",
    }
    values.update(changes)
    return DeadlineRequest(**values)


def test_long_term_moves_weekend_to_monday() -> None:
    result = calculate_deadline(request())
    assert result.nominal_date == date(2026, 8, 22)
    assert result.due_date == date(2026, 8, 24)
    assert result.adjusted is True
    assert result.rule.id == "pr-civil-68.1"
    assert result.requires_attorney_review is True


def test_terms_under_seven_days_exclude_intermediate_closures() -> None:
    result = calculate_deadline(
        request(days=3, closure_dates=[date(2026, 8, 11)])
    )
    assert result.due_date == date(2026, 8, 14)


def test_mail_extension_is_explicit() -> None:
    result = calculate_deadline(request(days=10, mail_extension_applicable=True))
    assert result.nominal_date == date(2026, 8, 23)
    assert result.due_date == date(2026, 8, 24)


def test_unknown_rule_fails_closed() -> None:
    with pytest.raises(UnknownDeadlineRuleError):
        calculate_deadline(request(rule_id="invented-rule"))
