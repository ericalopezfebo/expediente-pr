from datetime import date, timedelta

from .models import DeadlineRequest, DeadlineResult


def _advance_business_days(start: date, days: int) -> date:
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _next_weekday(value: date) -> date:
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


def calculate_deadline(payload: DeadlineRequest) -> DeadlineResult:
    """Calculate a transparent provisional date.

    This MVP handles weekends only. Puerto Rico holidays and rule-specific counting
    belong in the versioned rules engine planned for the next milestone.
    """
    if payload.use_calendar_days:
        nominal = payload.start_date + timedelta(days=payload.days)
    else:
        nominal = _advance_business_days(payload.start_date, payload.days)

    due = _next_weekday(nominal)
    adjusted = due != nominal
    counting_method = "días naturales" if payload.use_calendar_days else "días laborables"
    explanation = [
        f"El cómputo comienza después del {payload.start_date.isoformat()}.",
        f"Se añadieron {payload.days} {counting_method}.",
        f"La fecha nominal es {nominal.isoformat()}.",
    ]
    if adjusted:
        explanation.append(
            f"La fecha nominal cayó en fin de semana y se movió a {due.isoformat()}."
        )
    explanation.append("Resultado provisional sujeto a validación jurídica humana.")

    return DeadlineResult(
        start_date=payload.start_date,
        nominal_date=nominal,
        due_date=due,
        adjusted=adjusted,
        explanation=explanation,
        authority=payload.authority,
    )

