"""Стратегии входа через SSO вуза (identity provider).

Modeus у всех вузов один и тот же, а вход — у каждого свой: УрФУ пускает через ADFS,
другие вузы — через Keycloak, CAS, собственные формы... Эта разница и спрятана здесь.
"""
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .base import LoginError


class IdentityProvider(ABC):
    """Стратегия входа на стороне вуза.

    Modeus уводит браузер на страницу логина вуза (login_page). Реализация вводит логин/пароль
    и возвращает ответ, с которого начинается обратная цепочка редиректов в Modeus —
    запрос делается с allow_redirects=False. Дальше ModeusSource сам дойдёт до токенов.
    """

    @abstractmethod
    def login(self, session: requests.Session, login_page: requests.Response,
              username: str, password: str) -> requests.Response:
        ...


def form_fields(form) -> dict:
    return {inp["name"]: inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}


def submit_saml_form(session: requests.Session, page: requests.Response) -> requests.Response | None:
    """Отправляет автоформу с SAMLResponse (SAML HTTP-POST binding). None — если формы на странице нет."""
    saml_input = BeautifulSoup(page.text, "html.parser").find("input", attrs={"name": "SAMLResponse"})
    if saml_input is None:
        return None
    form = saml_input.find_parent("form")
    return session.post(urljoin(page.url, form["action"]), data=form_fields(form),
                        allow_redirects=False, timeout=30)


class AdfsIdentityProvider(IdentityProvider):
    """Microsoft ADFS с формой логина и ответом по SAML (так устроен sso.urfu.ru)."""

    def __init__(self, host: str):
        self.host = host

    def login(self, session, login_page, username, password):
        if self.host not in urlsplit(login_page.url).netloc:
            raise LoginError(f"Ожидалась страница {self.host}, а пришли на {urlsplit(login_page.url).netloc}")

        soup = BeautifulSoup(login_page.text, "html.parser")
        form = soup.find("form", id="loginForm") or soup.find("form")
        if form is None:
            raise LoginError("На странице ADFS не найдена форма логина")
        data = form_fields(form)
        data.update({"UserName": username, "Password": password,
                     "AuthMethod": data.get("AuthMethod") or "FormsAuthentication"})

        r = session.post(urljoin(login_page.url, form.get("action") or login_page.url), data=data, timeout=30)
        r.raise_for_status()
        resp = submit_saml_form(session, r)
        if resp is None:
            soup = BeautifulSoup(r.text, "html.parser")
            err = soup.find(id="errorText")
            msg = err.get_text(strip=True) if err else ""
            if soup.find("input", attrs={"name": "Password"}):
                raise LoginError(f"ADFS не принял логин/пароль. {msg}".strip())
            raise LoginError("После ввода пароля ADFS не вернул SAMLResponse "
                             "(возможно, появился второй фактор)")
        return resp
