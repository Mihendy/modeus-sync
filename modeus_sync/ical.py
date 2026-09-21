"""Занятие -> iCalendar. Используют CalDAV и .ics-файл; Google и прочие API строят событие сами."""
from datetime import datetime, timezone

from icalendar import Calendar, Event

from .models import Lesson

HASH_PROP = "X-MODEUS-HASH"


def to_vevent(lesson: Lesson, uid: str) -> Event:
    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", lesson.summary)
    ev.add("dtstart", lesson.start.astimezone(timezone.utc))
    ev.add("dtend", lesson.end.astimezone(timezone.utc))
    if lesson.location:
        ev.add("location", lesson.location)
    if lesson.url:
        ev.add("url", lesson.url)
    if lesson.description:
        ev.add("description", lesson.description)
    ev.add(HASH_PROP, lesson.fingerprint())
    ev.add("dtstamp", datetime.now(timezone.utc))
    return ev


def to_calendar(events: list[Event], name: str | None = None) -> str:
    cal = Calendar()
    cal.add("prodid", "-//modeus-sync//RU")
    cal.add("version", "2.0")
    if name:
        cal.add("x-wr-calname", name)
    for ev in events:
        cal.add_component(ev)
    return cal.to_ical().decode()
