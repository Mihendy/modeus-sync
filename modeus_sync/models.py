"""Общая модель занятия — единственное, о чём договариваются источники и календари."""
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Lesson:
    """Одно занятие в виде, не зависящем ни от вуза, ни от календаря."""
    id: str                        # стабильный id в системе вуза — из него строится UID события
    title: str                     # название дисциплины
    start: datetime                # с часовым поясом
    end: datetime
    kind: str | None = None        # короткая метка типа: «Лек», «Пр», «Лаб»...
    topic: str | None = None       # тема занятия
    lesson: str | None = None      # номер / краткое имя занятия
    location: str | None = None    # аудитория с адресом или текст онлайн-площадки
    url: str | None = None         # ссылка на онлайн-пару
    teachers: tuple[str, ...] = ()
    status: str | None = None

    @property
    def summary(self) -> str:
        return f"[{self.kind}] {self.title}" if self.kind else self.title

    @property
    def description(self) -> str:
        return "\n".join(x for x in [
            self.lesson,
            f"Тема: {self.topic}" if self.topic and self.topic != self.title else None,
            f"Преподаватель: {', '.join(self.teachers)}" if self.teachers else None,
            f"Ссылка: {self.url}" if self.url else None,
            f"Статус: {self.status}" if self.status else None,
        ] if x)

    def fingerprint(self) -> str:
        """Хэш содержимого — по нему календарь понимает, что событие не менялось."""
        return hashlib.sha1(json.dumps(asdict(self), default=str, sort_keys=True).encode()).hexdigest()

    def uid(self, namespace: str) -> str:
        return f"{self.id}@{namespace}"
