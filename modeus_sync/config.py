import os
import sys


def env(name: str, default: str | None = None, required: bool = True) -> str | None:
    v = os.environ.get(name) or default
    if required and not v:
        sys.exit(f"Не задана переменная окружения {name}")
    return v
