"""Файл .ics — снимок расписания за окно. Его можно раздавать как подписку или импортировать руками."""
from pathlib import Path

from ..config import env
from ..ical import to_calendar, to_vevent
from .base import CalendarTarget, SyncStats


class IcsFileTarget(CalendarTarget):
    def __init__(self, path: str, calendar_name: str):
        self.path = Path(path)
        self.calendar_name = calendar_name

    def apply(self, lessons, start, end, namespace):
        events = [to_vevent(lesson, lesson.uid(namespace)) for lesson in lessons]
        self.path.write_text(to_calendar(events, self.calendar_name), encoding="utf-8")
        print(f"Записано в {self.path}")
        return SyncStats(created=len(lessons), total=len(lessons))


def from_env(calendar_name: str) -> IcsFileTarget:
    return IcsFileTarget(env("ICS_PATH", "schedule.ics"), calendar_name)
