from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Lesson


class LoginError(Exception):
    """Не удалось войти в систему вуза."""


class ScheduleSource(ABC):
    """Контракт источника расписания: одна реализация — одна система (Modeus, свой API вуза...).

    Логин и пароль передаются в конструктор; входит источник сам, внутри fetch().
    """

    #: часовой пояс вуза — в нём считается окно синхронизации
    timezone: ZoneInfo

    @abstractmethod
    def fetch(self, start: datetime, end: datetime) -> list[Lesson]:
        """Все занятия студента в окне [start, end), отсортированные по началу.

        При неверном логине/пароле или сломавшемся SSO — LoginError с понятным текстом.
        Id занятий обязаны быть стабильными между запусками, иначе в календаре будут дубли.
        """
