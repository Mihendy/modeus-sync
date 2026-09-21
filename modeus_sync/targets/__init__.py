"""Реестр календарей: имя для TARGET -> фабрика, которая читает свои переменные окружения."""
from . import caldav, ics
from .base import CalendarTarget, IncrementalTarget, SyncStats

TARGETS = {
    "caldav": caldav.from_env,
    "ics": ics.from_env,
}

__all__ = ["TARGETS", "CalendarTarget", "IncrementalTarget", "SyncStats"]
