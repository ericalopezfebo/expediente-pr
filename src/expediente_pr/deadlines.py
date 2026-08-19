from datetime import date, timedelta

from .models import DeadlineRequest, DeadlineResult, DeadlineRule

RULE_68_1 = DeadlineRule(
    id="pr-civil-68.1",
    name="Cómputo general de términos civiles",
    jurisdiction="Puerto Rico",
    version="2026-08-10",
    authority="Reglas de Procedimiento Civil de 2009, Regla 68.1, 32 LPRA Ap. V",
    source_url="https://bvirtualogp.pr.gov/ogp/Bvirtual/leyesreferencia/PDF/Justicia/RPCI.pdf",
    active=True,
)

RULES = {RULE_68_1.id: RULE_68_1}


class UnknownDeadlineRuleError(ValueError):
    pass


def list_rules() -> list[DeadlineRule]:
    return list(RULES.values())


def _closed(value: date, closures: set[date]) -> bool:
    return value.weekday() >= 5 or value in closures


def _advance_open_days(start: date, days: int, closures: set[date]) -> date:
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if not _closed(current, closures):
            remaining -= 1
    return current


def _next_open_day(value: date, closures: set[date]) -> date:
    while _closed(value, closures):
        value += timedelta(days=1)
    return value


def calculate_deadline(payload: DeadlineRequest) -> DeadlineResult:
    rule = RULES.get(payload.rule_id)
    if rule is None or not rule.active:
        raise UnknownDeadlineRuleError(payload.rule_id)

    closures = set(payload.closure_dates)
    total_days = payload.days + (3 if payload.mail_extension_applicable else 0)
    short_term = payload.days < 7
    if short_term:
        nominal = _advance_open_days(payload.start_date, total_days, closures)
        method = "se excluyeron sábados, domingos y cierres intermedios"
    else:
        nominal = payload.start_date + timedelta(days=total_days)
        method = "se contaron días naturales"

    due = _next_open_day(nominal, closures)
    adjusted = due != nominal
    explanation = [
        f"Evento inicial: {payload.start_event} ({payload.start_date.isoformat()}).",
        "El día del evento inicial no se contó.",
        f"Para el término base de {payload.days} días, {method}.",
    ]
    if payload.mail_extension_applicable:
        explanation.append(
            "Se añadieron tres días porque el usuario confirmó que aplica la Regla 68.3."
        )
    explanation.append(f"La fecha nominal resultó ser {nominal.isoformat()}.")
    if adjusted:
        explanation.append(
            f"El vencimiento se extendió hasta el próximo día abierto: {due.isoformat()}."
        )
    explanation.append("El cálculo requiere confirmación de un abogado antes de utilizarse.")

    warnings = [
        "La lista de cierres debe verificarse contra órdenes administrativas vigentes.",
        "El sistema no decide si el término es jurisdiccional, prorrogable o interrumpido.",
    ]
    if not closures:
        warnings.append("No se proporcionaron feriados ni cierres judiciales.")

    return DeadlineResult(
        rule=rule,
        start_date=payload.start_date,
        nominal_date=nominal,
        due_date=due,
        adjusted=adjusted,
        explanation=explanation,
        warnings=warnings,
    )
