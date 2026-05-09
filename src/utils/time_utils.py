from __future__ import annotations

from datetime import datetime
from typing import Any


def now_text() -> str:
    return to_time_text(datetime.now().astimezone()) or ""


def from_epoch_seconds(value: float) -> str:
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def to_time_text(value: Any) -> str | None:
    dt = parse_time_value(value)
    if dt is None:
        return None
    return dt.isoformat(timespec="seconds")


def to_epoch_seconds(value: Any, default: float | None = None) -> float | None:
    dt = parse_time_value(value)
    if dt is None:
        return default
    return dt.timestamp()


def parse_time_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_local_timezone(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return _ensure_local_timezone(datetime.fromisoformat(text))
        except ValueError:
            return None
    return None


def _ensure_local_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value.astimezone()
