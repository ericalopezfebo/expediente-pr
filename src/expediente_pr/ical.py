from datetime import UTC, datetime

from .models import CalendarEvent


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(events: list[CalendarEvent], include_details: bool = False) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Expediente PR//Legal Calendar//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    generated = _stamp(datetime.now(UTC))
    for event in events:
        title = event.title if include_details else "Evento de expediente"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event.id}@expediente-pr",
                f"DTSTAMP:{generated}",
                f"DTSTART:{_stamp(event.starts_at)}",
                f"DTEND:{_stamp(event.ends_at)}",
                f"SUMMARY:{_escape(title)}",
                f"STATUS:{'CONFIRMED' if event.status == 'confirmed' else 'TENTATIVE'}",
            ]
        )
        if include_details and event.description:
            lines.append(f"DESCRIPTION:{_escape(event.description)}")
        if include_details and event.location:
            lines.append(f"LOCATION:{_escape(event.location)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
