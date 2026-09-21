"""Реестр вузов. Новый вуз = новая запись в UNIVERSITIES (см. «Добавить свой вуз» в README)."""
from collections.abc import Callable
from dataclasses import dataclass

from .sources import AdfsIdentityProvider, ModeusSource, ScheduleSource


@dataclass(frozen=True)
class University:
    code: str                                          # значение UNIVERSITY, латиницей
    title: str                                         # как называть вуз в логах и имени календаря
    login_hint: str                                    # что вводить как UNIVERSITY_LOGIN
    make_source: Callable[[str, str], ScheduleSource]  # (логин, пароль) -> источник

    @property
    def namespace(self) -> str:
        """Суффикс UID событий. Не меняй у существующих вузов — иначе в календарях появятся дубли."""
        return f"modeus-{self.code}-sync"


UNIVERSITIES = {u.code: u for u in [
    University(
        code="urfu",
        title="УрФУ",
        login_hint="логин, как на sso.urfu.ru",
        make_source=lambda login, password: ModeusSource(
            tenant="urfu",
            idp=AdfsIdentityProvider("sso.urfu.ru"),
            username=login, password=password,
            timezone="Asia/Yekaterinburg",
        ),
    ),
]}
