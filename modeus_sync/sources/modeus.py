"""Источник расписания Modeus. Один класс на все вузы: отличаются адрес, часовой пояс и стратегия входа."""
import base64
import json
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests

from ..models import Lesson
from .base import LoginError, ScheduleSource
from .idp import IdentityProvider

TYPE_LABELS = {
    "LECT": "Лек", "SEMI": "Пр", "LAB": "Лаб", "CONS": "Конс",
    "SELF": "СРС", "EXAMINATION": "Экз", "MIDTERM": "Зачёт", "CUR_CHECK": "КТ",
}

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")


class ModeusSource(ScheduleSource):
    def __init__(self, tenant: str, idp: IdentityProvider, username: str, password: str,
                 timezone: str, base_url: str | None = None, auth_url: str | None = None):
        """tenant — поддомен вуза: urfu -> https://urfu.modeus.org и https://urfu-auth.modeus.org."""
        self.base_url = base_url or f"https://{tenant}.modeus.org"
        self.auth_url = auth_url or f"https://{tenant}-auth.modeus.org"
        self.redirect_uri = f"{self.base_url}/schedule-calendar/my"
        self.idp = idp
        self.username = username
        self.password = password
        self.timezone = ZoneInfo(timezone)

    def fetch(self, start: datetime, end: datetime) -> list[Lesson]:
        tokens = self._login()
        person_id = jwt_claims(tokens["id_token"])["person_id"]
        print("Вход в Modeus выполнен")
        return normalize(self._search(tokens, person_id, start, end))

    # ------------------------------------------------------------ авторизация

    def _client_id(self, s: requests.Session) -> str:
        """client_id общий для всех пользователей — берём его из публичного конфига фронтенда."""
        try:
            r = s.get(f"{self.base_url}/schedule-calendar/assets/app.config.json", timeout=30)
            r.raise_for_status()
            return r.json()["wso"]["clientId"]
        except Exception as exc:
            raise LoginError(f"Не удалось прочитать client_id из app.config.json: {exc}")

    def _login(self) -> dict:
        """OAuth2 implicit: authorize -> вход на стороне вуза -> редиректы до #id_token."""
        s = requests.Session()
        s.headers["User-Agent"] = UA
        nonce = secrets.token_urlsafe(24)

        r = s.get(f"{self.auth_url}/oauth2/authorize", params={
            "response_type": "id_token token", "client_id": self._client_id(s),
            "redirect_uri": self.redirect_uri, "scope": "openid",
            "state": nonce, "nonce": nonce,
        }, timeout=30)
        r.raise_for_status()

        r = self.idp.login(s, r, self.username, self.password)
        for _ in range(15):
            loc = r.headers.get("Location")
            if not loc:
                break
            if "id_token=" in loc or "access_token=" in loc:
                frag = parse_qs(urlsplit(loc).fragment)
                return {k: v[0] for k, v in frag.items()}
            r = s.get(urljoin(r.url, loc), allow_redirects=False, timeout=30)
        raise LoginError("Не удалось получить id_token после входа (цепочка редиректов оборвалась)")

    # ------------------------------------------------------------ API

    def _search(self, tokens: dict, person_id: str, start: datetime, end: datetime) -> dict:
        """Скачивает события кусками по 30 дней и склеивает связанные сущности."""
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Content-Type": "application/json"})
        url = f"{self.base_url}/schedule-calendar-v2/api/calendar/events/search?tz={self.timezone.key}"

        merged = {}
        cur = start
        while cur < end:
            chunk_end = min(cur + timedelta(days=30), end)
            body = {"size": 500, "timeMin": cur.isoformat(), "timeMax": chunk_end.isoformat(),
                    "attendeePersonId": [person_id]}
            resp = None
            # какой именно токен ждёт API, неизвестно — пробуем оба
            for key in ("id_token", "access_token"):
                if not tokens.get(key):
                    continue
                resp = s.post(url, json=body, timeout=60,
                              headers={"Authorization": f"Bearer {tokens[key]}"})
                if resp.status_code != 401:
                    break
            if resp is None:
                raise LoginError("Modeus не вернул ни id_token, ни access_token")
            resp.raise_for_status()
            for k, items in resp.json().get("_embedded", {}).items():
                merged.setdefault(k, []).extend(items)
            cur = chunk_end
        return merged


def jwt_claims(token: str) -> dict:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def _id(link_obj):
    """HAL-ссылка вида {'href': '/<uuid>'} -> uuid."""
    if isinstance(link_obj, list):
        link_obj = link_obj[0]
    return (link_obj or {}).get("href", "").strip("/").split("/")[0] or None


def normalize(emb: dict) -> list[Lesson]:
    """Превращает HAL-ответ Modeus в плоский список занятий."""
    by_id = lambda key: {x["id"]: x for x in emb.get(key, []) if "id" in x}
    courses = by_id("course-unit-realizations")
    persons = by_id("persons")
    rooms = by_id("rooms")
    locations = {x.get("eventId"): x for x in emb.get("event-locations", [])}

    ev_rooms = {}
    for er in emb.get("event-rooms", []):
        room = rooms.get(_id(er["_links"].get("room")))
        if room:
            ev_rooms.setdefault(_id(er["_links"].get("event")), []).append(room)

    teachers = {}
    for a in emb.get("event-attendees", []):
        if a.get("roleId") == "TEACH":
            p = persons.get(_id(a["_links"].get("person")))
            if p and not p["fullName"].lower().startswith("support"):
                teachers.setdefault(_id(a["_links"].get("event")), []).append(p["fullName"])

    seen, result = set(), []
    for ev in emb.get("events", []):
        if ev["id"] in seen:
            continue
        seen.add(ev["id"])
        course = courses.get(_id(ev["_links"].get("course-unit-realization")), {})
        loc_parts, url = [], None
        for room in ev_rooms.get(ev["id"], []):
            b = room.get("building") or {}
            loc_parts.append(", ".join(filter(None, [room.get("name"), b.get("address")])))
        custom = (locations.get(ev["id"]) or {}).get("customLocation")
        if custom:
            m = re.search(r"https?://\S+", custom)
            url = m.group(0).rstrip(".,;)") if m else None
            loc_parts.append(custom)
        type_id = ev.get("typeId")
        result.append(Lesson(
            id=ev["id"],
            title=course.get("name") or ev.get("name") or "Занятие",
            start=datetime.fromisoformat(ev["start"]),
            end=datetime.fromisoformat(ev["end"]),
            kind=TYPE_LABELS.get(type_id, type_id),
            topic=ev.get("name"),
            lesson=ev.get("nameShort"),
            location="; ".join(dict.fromkeys(loc_parts)) or None,
            url=url,
            teachers=tuple(sorted(set(teachers.get(ev["id"], [])))),
            status=(ev.get("holdingStatus") or {}).get("name"),
        ))
    return sorted(result, key=lambda e: e.start)
