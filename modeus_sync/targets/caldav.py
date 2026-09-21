"""Любой CalDAV-сервер. По умолчанию — Яндекс Календарь."""
from ..config import env
from ..ical import HASH_PROP, to_calendar, to_vevent
from .base import IncrementalTarget

YANDEX_CALDAV = "https://caldav.yandex.ru"


class CalDavTarget(IncrementalTarget):
    def __init__(self, url: str, username: str, password: str, calendar_name: str):
        import caldav

        principal = caldav.DAVClient(url, username=username, password=password).principal()
        self.calendar = self._find_or_create(principal, calendar_name)
        self._objects = {}

    @staticmethod
    def _find_or_create(principal, name):
        for cal in principal.calendars():
            if (cal.name or "").strip() == name:
                return cal
        try:
            return principal.make_calendar(name=name)
        except Exception as exc:
            raise RuntimeError(f"Календарь «{name}» не найден, и создать его не получилось ({exc}). "
                               f"Создай его вручную с таким же именем и запусти снова.")

    def list_events(self, start, end, namespace):
        result = {}
        for obj in self.calendar.search(start=start, end=end, event=True, expand=False):
            comp = obj.icalendar_component
            uid = str(comp.get("uid", ""))
            if uid.endswith("@" + namespace):
                self._objects[uid] = obj
                result[uid] = str(comp.get(HASH_PROP, ""))
        return result

    def create(self, uid, lesson):
        self.calendar.save_event(to_calendar([to_vevent(lesson, uid)]))

    def update(self, uid, lesson):
        obj = self._objects[uid]
        obj.data = to_calendar([to_vevent(lesson, uid)])
        obj.save()

    def delete(self, uid):
        self._objects.pop(uid).delete()


def from_env(calendar_name: str) -> CalDavTarget:
    return CalDavTarget(
        url=env("CALDAV_URL", YANDEX_CALDAV),
        username=env("CALDAV_LOGIN"),
        password=env("CALDAV_PASSWORD"),
        calendar_name=calendar_name,
    )
