from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..models import Lesson


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    total: int = 0

    def __str__(self):
        return (f"Готово: +{self.created} новых, ~{self.updated} обновлено, -{self.deleted} удалено, "
                f"всего пар в окне: {self.total}")


class CalendarTarget(ABC):
    """Контракт календаря, куда складывается расписание."""

    @abstractmethod
    def apply(self, lessons: list[Lesson], start: datetime, end: datetime, namespace: str) -> SyncStats:
        """Привести календарь в окне [start, end) к списку lessons.

        Трогать можно только события с UID вида <lesson.id>@<namespace> — остальное принадлежит человеку.
        """


class IncrementalTarget(CalendarTarget):
    """Шаблон для календарей с поштучным API (CalDAV, Google Calendar, Outlook...).

    Реализуй четыре метода ниже — сравнение, защита от дублей и от массового удаления уже здесь.
    """

    @abstractmethod
    def list_events(self, start: datetime, end: datetime, namespace: str) -> dict[str, str]:
        """UID -> fingerprint для наших событий в окне. Чужие события (другой namespace) не возвращать."""

    @abstractmethod
    def create(self, uid: str, lesson: Lesson) -> None: ...

    @abstractmethod
    def update(self, uid: str, lesson: Lesson) -> None: ...

    @abstractmethod
    def delete(self, uid: str) -> None: ...

    def apply(self, lessons, start, end, namespace):
        existing = self.list_events(start, end, namespace)
        stats = SyncStats(total=len(lessons))

        wanted = set()
        for lesson in lessons:
            uid = lesson.uid(namespace)
            wanted.add(uid)
            if uid not in existing:
                self.create(uid, lesson)
                stats.created += 1
            elif existing[uid] != lesson.fingerprint():
                self.update(uid, lesson)
                stats.updated += 1

        stale = [uid for uid in existing if uid not in wanted]
        if stale and not lessons:
            # пустой ответ источника чаще означает сбой, чем отмену всех пар разом
            print(f"Источник не вернул ни одной пары — {len(stale)} событий в календаре не удаляю")
            return stats
        for uid in stale:
            self.delete(uid)
            stats.deleted += 1
        return stats
