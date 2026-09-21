# modeus-sync — расписание вуза в твоём календаре

Скрипт входит в Modeus через SSO твоего вуза, забирает пары и раскладывает их
в отдельный календарь (Яндекс или любой CalDAV) или в `.ics`-файл.
Запускается по расписанию из GitHub Actions или cron — свой сервер не нужен.

> Неофициальный проект, не связан ни с Modeus, ни с вузами. Пользуешься на свой страх и риск.

- новые пары добавляются, изменённые (время, аудитория, ссылка) обновляются;
- пары, пропавшие из расписания (перенос/отмена), удаляются;
- трогает только свои события в своём календаре — личные события в безопасности;
- повторный запуск ничего не дублирует: у каждой пары постоянный UID.

В событии: `[Лек] Название дисциплины`, место (аудитория или ссылка на онлайн-пару),
в описании — номер занятия, тема, преподаватель, ссылка, статус.

## Что поддерживается

| Вуз | `UNIVERSITY` | Вход | Статус |
|---|---|---|---|
| УрФУ | `urfu` | ADFS (sso.urfu.ru) | ✅ работает |
| Твой вуз на Modeus | — | — | [добавь его](#добавить-свой-вуз) |

| Календарь | `TARGET` | |
|---|---|---|
| Яндекс Календарь и любой CalDAV (Nextcloud, Fastmail…) | `caldav` | ✅ |
| Файл `.ics` | `ics` | ✅ |
| Google Calendar | — | [нужна помощь](#добавить-свой-календарь) |

## Быстрый старт

```bash
git clone https://github.com/<you>/modeus-sync && cd modeus-sync
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # заполни логины и пароли
set -a && . ./.env && set +a

python -m modeus_sync --list      # поддерживаемые вузы и календари
python -m modeus_sync --dry-run   # только скачать и напечатать пары — начни с этого
python -m modeus_sync             # синхронизировать
```

Для Яндекса нужен **пароль приложения**, а не обычный пароль: Яндекс ID → Безопасность →
Пароли приложений → «Календарь (CalDAV)». Календарь «Modeus <вуз>» скрипт создаст сам;
если не выйдет — создай его вручную с тем же именем.

### Настройки

| Переменная | По умолчанию | |
|---|---|---|
| `UNIVERSITY` | `urfu` | код вуза, см. `--list` |
| `UNIVERSITY_LOGIN`, `UNIVERSITY_PASSWORD` | — | логин/пароль от SSO вуза |
| `TARGET` | `caldav` | `caldav` или `ics` |
| `CALDAV_URL` | `https://caldav.yandex.ru` | адрес CalDAV-сервера |
| `CALDAV_LOGIN`, `CALDAV_PASSWORD` | — | для Яндекса — логин и пароль приложения |
| `CALENDAR_NAME` | `Modeus <вуз>` | имя отдельного календаря |
| `ICS_PATH` | `schedule.ics` | куда писать файл при `TARGET=ics` |
| `DAYS_BACK`, `DAYS_AHEAD` | `7`, `60` | окно синхронизации в днях |

## Автозапуск

### GitHub Actions

1. Сделай форк и включи в нём workflow во вкладке Actions — в форках он по умолчанию выключен.
   Пароли в логах маскируются, но сами логи публичного репозитория видны всем; если это
   мешает — вместо форка сделай приватную копию (*Use this template*).
2. Settings → Secrets and variables → Actions:
   - **Secrets**: `UNIVERSITY_LOGIN`, `UNIVERSITY_PASSWORD`, `CALDAV_LOGIN`, `CALDAV_PASSWORD`
     (значения без кавычек);
   - **Variables** (по желанию): `UNIVERSITY`, `CALDAV_URL`, `CALENDAR_NAME`, `DAYS_BACK`, `DAYS_AHEAD`.
3. Actions → «Sync schedule» → *Run workflow* — проверь первый запуск вручную.

Расписание — каждые 3 часа (`cron` в `.github/workflows/sync.yml`, время UTC). GitHub может
опаздывать с запуском на 5–30 минут, а в публичных репозиториях отключает расписание, если
60 дней не было коммитов — тогда во вкладке Actions достаточно нажать *Enable workflow*.

### Если SSO вуза не пускает GitHub

Раннеры GitHub стоят за границей, и SSO вуза может их не пускать (таймаут или 403 на входе).
Тогда запускай у себя через cron:

```bash
crontab -e
0 */3 * * * cd ~/modeus-sync && set -a && . ./.env && set +a && .venv/bin/python -m modeus_sync >> sync.log 2>&1
```

Либо поставь [self-hosted runner](https://docs.github.com/actions/hosting-your-own-runners)
на свою машину и замени в workflow `runs-on: ubuntu-latest` на `runs-on: self-hosted`.

## Нашёл ошибку?

Заведи [issue](../../issues/new/choose) и приложи:

1. вуз и какой календарь используешь;
2. вывод `python -m modeus_sync --dry-run` — хотя бы до места ошибки;
3. что ожидал увидеть.

**Перед отправкой вычисти из вывода личное**: логины, ссылки и пароли конференций
(они бывают прямо в поле места), ФИО. Никогда не прикладывай HAR-файлы, cookies и токены —
в них твой пароль и доступ к аккаунту.

## Как устроено

```
Источник (ScheduleSource)            Модель             Календарь (CalendarTarget)
┌───────────────────────────┐                          ┌──────────────────────────┐
│ ModeusSource              │                          │ IncrementalTarget        │
│   tenant: urfu            │   ──►  list[Lesson]  ──► │   CalDavTarget           │
│   idp: IdentityProvider ◄─┼─ стратегия входа         │   (GoogleTarget?)        │
│        AdfsIdentityProv.  │                          │ IcsFileTarget            │
└───────────────────────────┘                          └──────────────────────────┘
          ▲ universities.py: какой вуз — какой источник         ▲ targets/__init__.py
```

```
modeus_sync/
  cli.py            точка входа: читает настройки, соединяет источник и календарь
  models.py         Lesson — общий формат занятия, fingerprint() для поиска изменений
  universities.py   реестр вузов
  sources/
    base.py         контракт ScheduleSource и LoginError
    idp.py          стратегии входа: IdentityProvider, AdfsIdentityProvider
    modeus.py       ModeusSource — API Modeus, общий для всех вузов
  targets/
    base.py         контракт CalendarTarget и шаблон IncrementalTarget (сравнение, удаление)
    caldav.py       CalDAV / Яндекс
    ics.py          .ics-файл
  ical.py           Lesson -> iCalendar
```

Защита от дублей: UID события = `<id пары в Modeus>@modeus-<вуз>-sync`. Перед записью
скрипт читает события календаря, у которых UID кончается на этот суффикс, и сравнивает
по UID: есть — обновляет (если поменялся хэш содержимого), нет — создаёт, лишнее — удаляет.
Если источник вернул ноль пар, скрипт ничего не удаляет: это чаще сбой, чем отмена всех пар.

## Добавить свой вуз

Modeus у многих вузов один и тот же (`<вуз>.modeus.org`), различается только вход.

### Вуз на Modeus

1. Выясни, как устроен вход. Открой DevTools → Network (включи *Preserve log*),
   войди в `https://<вуз>.modeus.org` и посмотри цепочку запросов: куда редиректит
   `<вуз>-auth.modeus.org/oauth2/authorize`, какая форма логина и что приходит после неё
   (SAML-форма, OIDC-редирект…). HAR с этой сессией **не публикуй** — в нём пароль.
2. Если это ADFS — вероятно, хватит `AdfsIdentityProvider("sso.<вуз>.ru")`. Иначе напиши
   свою стратегию в `sources/idp.py`:

   ```python
   class KeycloakIdentityProvider(IdentityProvider):
       def __init__(self, host: str):
           self.host = host

       def login(self, session, login_page, username, password):
           # login_page — ответ, на который Modeus увёл браузер (страница логина вуза).
           # Заполни форму, пройди свои шаги и верни ответ, с которого начинается обратный
           # редирект в Modeus (запрос с allow_redirects=False). Ошибки — raise LoginError(...).
           ...
   ```

   Для SAML уже есть помощник `submit_saml_form(session, page)`.
3. Зарегистрируй вуз в `modeus_sync/universities.py`:

   ```python
   University(
       code="utmn",
       title="ТюмГУ",
       login_hint="логин от единой учётной записи ТюмГУ",
       make_source=lambda login, password: ModeusSource(
           tenant="utmn",
           idp=KeycloakIdentityProvider("sso.utmn.ru"),
           username=login, password=password,
           timezone="Asia/Yekaterinburg",
       ),
   ),
   ```

   Если адреса не укладываются в схему `<tenant>.modeus.org` / `<tenant>-auth.modeus.org`,
   передай `base_url=` и `auth_url=` явно.
4. Проверь `python -m modeus_sync --university utmn --dry-run` и присылай pull request.
   В описании PR — что проверил; личных данных не нужно.

### Вуз не на Modeus

Реализуй `ScheduleSource` (`sources/base.py`): атрибут `timezone` и метод
`fetch(start, end) -> list[Lesson]`. Главное требование — `Lesson.id` должен быть
стабильным между запусками, иначе в календаре появятся дубли. Дальше — такая же запись
в `universities.py`.

`code` вуза после релиза не меняй: из него строится суффикс UID, и смена кода
создаст в календарях пользователей дубли.

## Добавить свой календарь

Для календаря с поштучным API (Google Calendar, Outlook…) унаследуйся от
`IncrementalTarget` — сравнение, защита от дублей и от массового удаления уже там:

```python
class GoogleCalendarTarget(IncrementalTarget):
    def list_events(self, start, end, namespace) -> dict[str, str]:
        """UID -> fingerprint наших событий в окне. UID и хэш удобно хранить
        в extendedProperties.private события."""

    def create(self, uid, lesson): ...
    def update(self, uid, lesson): ...
    def delete(self, uid): ...


def from_env(calendar_name: str) -> GoogleCalendarTarget:
    ...  # читает свои переменные окружения
```

Зарегистрируй фабрику в `TARGETS` в `modeus_sync/targets/__init__.py` — и она станет
доступна как `TARGET=google`. Если календарь умеет только «записать всё целиком»
(как файл), реализуй напрямую `CalendarTarget.apply()`.

## Лицензия

[MIT](LICENSE)
