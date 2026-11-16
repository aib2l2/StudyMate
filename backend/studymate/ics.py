"""Minimal RFC 5545 (iCalendar) writer without dependencies."""

from datetime import UTC, datetime

CRLF = "\r\n"


def escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Split lines longer than 75 octets of UTF-8 without breaking a character."""
    out, current, size = [], "", 0
    for char in line:
        width = len(char.encode())
        limit = 75 if not out else 74  # continuation lines start with a space
        if size + width > limit:
            out.append(current)
            current, size = "", 0
        current += char
        size += width
    out.append(current)
    return (CRLF + " ").join(out)


def stamp(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y%m%dT%H%M%SZ")


def calendar(events: list[dict], now: int) -> str:
    """events: uid, start, end, summary, description, location, url, sequence."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//StudyMate Campus//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e['uid']}",
            f"DTSTAMP:{stamp(now)}",
            f"DTSTART:{stamp(e['start'])}",
            f"DTEND:{stamp(e['end'])}",
            f"SEQUENCE:{e.get('sequence', 0)}",
            f"SUMMARY:{escape(e['summary'])}",
            f"DESCRIPTION:{escape(e.get('description', ''))}",
            "STATUS:CONFIRMED",
        ]
        if e.get("location"):
            lines.append(f"LOCATION:{escape(e['location'])}")
        if e.get("url"):
            lines.append(f"URL:{e['url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return CRLF.join(fold(line) for line in lines) + CRLF
