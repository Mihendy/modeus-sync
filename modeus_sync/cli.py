import argparse
import sys
from datetime import datetime, timedelta

from .config import env
from .sources import LoginError
from .targets import TARGETS
from .universities import UNIVERSITIES


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m modeus_sync",
                                description="Синхронизация расписания вуза с календарём.")
    p.add_argument("--dry-run", action="store_true", help="только скачать и показать пары, календарь не трогать")
    p.add_argument("--university", help="код вуза (по умолчанию UNIVERSITY или urfu)")
    p.add_argument("--target", help=f"куда писать: {', '.join(TARGETS)} (по умолчанию TARGET или caldav)")
    p.add_argument("--list", action="store_true", help="показать поддерживаемые вузы и календари")
    args = p.parse_args(argv)

    if args.list:
        for u in UNIVERSITIES.values():
            print(f"{u.code:10} {u.title} — UNIVERSITY_LOGIN: {u.login_hint}")
        print(f"\nКалендари (TARGET): {', '.join(TARGETS)}")
        return

    code = args.university or env("UNIVERSITY", "urfu")
    uni = UNIVERSITIES.get(code)
    if uni is None:
        sys.exit(f"Неизвестный вуз «{code}». Поддерживаются: {', '.join(UNIVERSITIES)}")
    target_name = args.target or env("TARGET", "caldav")
    if target_name not in TARGETS:
        sys.exit(f"Неизвестный календарь «{target_name}». Есть: {', '.join(TARGETS)}")

    source = uni.make_source(env("UNIVERSITY_LOGIN"), env("UNIVERSITY_PASSWORD"))
    today = datetime.now(source.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=int(env("DAYS_BACK", "7")))
    end = today + timedelta(days=int(env("DAYS_AHEAD", "60")))

    try:
        lessons = source.fetch(start, end)
    except LoginError as exc:
        sys.exit(f"Ошибка входа ({uni.title}): {exc}")
    print(f"Пар с {start:%d.%m} по {end:%d.%m}: {len(lessons)}")

    if args.dry_run:
        for x in lessons:
            print(f"{x.start:%a %d.%m %H:%M}  {x.summary} | {x.location or '—'}")
        return

    target = TARGETS[target_name](env("CALENDAR_NAME", f"Modeus {uni.title}"))
    print(target.apply(lessons, start, end, uni.namespace))
