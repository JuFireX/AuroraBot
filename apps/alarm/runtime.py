from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.platform.contracts import AppEvent
from src.utils.log_utils import get_logger
from src.utils.time_utils import from_epoch_seconds, to_epoch_seconds

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI

logger = get_logger("AlarmApplication")
DEFAULT_INTERVAL_SECONDS = 1800
DEFAULT_DIARY_TIME = "22:00"


class AlarmApplication:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None
        self._alarms_file: Path | None = None
        self._settings_file: Path | None = None
        self._alarms: list[dict[str, Any]] = []
        self._settings: dict[str, Any] = {}

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api
        self._alarms_file = api.data_dir / "alarms.json"
        self._settings_file = api.data_dir / "config.json"

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        self._load_settings()
        self._load_alarms()
        if not self._alarms:
            self._alarms = self._default_alarms()
            self._save_alarms()
        logger.info("Alarm application started")

    async def on_stop(self) -> None:
        self._save_alarms()
        logger.info("Alarm application stopped")

    async def on_tick(self) -> None:
        self._dispatch_due_alarms()

    def set_alarm(
        self,
        message: str,
        interval_seconds: float | None = None,
        alarm_type: str = "generic",
    ) -> dict[str, object]:
        now = time.time()
        alarm = {
            "id": str(uuid.uuid4()),
            "message": message,
            "enabled": True,
            "interval_seconds": interval_seconds or self._default_interval_seconds(),
            "next_trigger_at": from_epoch_seconds(
                now + (interval_seconds or self._default_interval_seconds())
            ),
            "last_triggered_at": None,
            "alarm_type": alarm_type,
            "target": {},
        }
        self._alarms.append(alarm)
        self._save_alarms()
        return {"alarm_id": alarm["id"], "status": "created"}

    def _dispatch_due_alarms(self) -> None:
        api = self._require_api()
        now = time.time()
        changed = False
        for alarm in self._alarms:
            if not alarm.get("enabled", True):
                continue
            next_trigger_at = to_epoch_seconds(alarm.get("next_trigger_at"), now + 1)
            if next_trigger_at is None or next_trigger_at > now:
                continue
            payload = dict(alarm)
            target = payload.get("target", {})
            if isinstance(target, dict):
                session_id = (
                    target.get("session_id")
                    or target.get("group_id")
                    or target.get("user_id")
                )
                if session_id is not None:
                    payload["session_id"] = str(session_id)
            todo_type = (
                "diary_prompt"
                if payload.get("alarm_type") == "diary_prompt"
                else "alarm_reminder"
            )
            if todo_type == "diary_prompt":
                payload["date"] = time.strftime("%Y-%m-%d")
            api.emit_event(
                AppEvent(
                    source=api.package,
                    type=todo_type,
                    session_id=str(payload.get("session_id", "")),
                    summary=str(payload.get("message", "")).strip(),
                    payload=payload,
                )
            )
            interval_seconds = float(
                payload.get("interval_seconds", self._default_interval_seconds())
            )
            alarm["last_triggered_at"] = from_epoch_seconds(now)
            alarm["next_trigger_at"] = from_epoch_seconds(now + interval_seconds)
            changed = True
        if changed:
            self._save_alarms()

    def _load_alarms(self) -> None:
        if self._alarms_file is None or not self._alarms_file.exists():
            return
        try:
            loaded = json.loads(self._alarms_file.read_text(encoding="utf-8-sig"))
            self._alarms = [dict(item) for item in loaded if isinstance(item, dict)]
        except Exception:
            self._alarms = []

    def _save_alarms(self) -> None:
        if self._alarms_file is None:
            return
        self._alarms_file.parent.mkdir(parents=True, exist_ok=True)
        self._alarms_file.write_text(
            json.dumps(self._alarms, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_json(self, file_path: Path | None, default: Any) -> Any:
        if file_path is None or not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return default

    def _write_json(self, file_path: Path | None, data: Any) -> None:
        if file_path is None:
            return
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_settings(self) -> None:
        settings = self._read_json(self._settings_file, {})
        if not isinstance(settings, dict):
            settings = {}
        self._settings = {
            "default_interval_seconds": _to_positive_int(
                settings.get("default_interval_seconds"), DEFAULT_INTERVAL_SECONDS
            ),
            "diary_time": _normalize_diary_time(
                settings.get("diary_time"), DEFAULT_DIARY_TIME
            ),
        }
        self._write_json(self._settings_file, self._settings)

    def _default_interval_seconds(self) -> int:
        return _to_positive_int(
            self._settings.get("default_interval_seconds"), DEFAULT_INTERVAL_SECONDS
        )

    def _diary_time(self) -> str:
        return _normalize_diary_time(
            self._settings.get("diary_time"), DEFAULT_DIARY_TIME
        )

    def _default_alarms(self) -> list[dict[str, Any]]:
        now = time.time()
        default_interval_seconds = self._default_interval_seconds()
        diary_interval = _seconds_until_next_diary_time(self._diary_time())
        return [
            {
                "id": "default_stretch_alarm",
                "message": "Time to stretch.",
                "enabled": True,
                "interval_seconds": default_interval_seconds,
                "next_trigger_at": from_epoch_seconds(now + default_interval_seconds),
                "last_triggered_at": None,
                "alarm_type": "generic",
                "target": {},
            },
            {
                "id": "daily_diary_prompt",
                "message": "Time to write the diary.",
                "summary": "Daily review",
                "interactions": [],
                "reflections": "",
                "date": time.strftime("%Y-%m-%d"),
                "enabled": True,
                "interval_seconds": 86400,
                "next_trigger_at": from_epoch_seconds(now + diary_interval),
                "last_triggered_at": None,
                "alarm_type": "diary_prompt",
                "target": {},
            },
        ]

    def _require_api(self) -> "PlatformAPI":
        if self._api is None:
            raise RuntimeError("AlarmApplication is not bound to PlatformAPI")
        return self._api


def _seconds_until_next_diary_time(diary_time: str) -> int:
    now = time.localtime()
    hour_text, minute_text = diary_time.split(":", maxsplit=1)
    target_hour = int(hour_text)
    target_minute = int(minute_text)
    current_seconds = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
    target_seconds = target_hour * 3600 + target_minute * 60
    if target_seconds <= current_seconds:
        return 86400 - current_seconds + target_seconds
    return target_seconds - current_seconds


def _to_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_diary_time(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if ":" not in text:
        return default
    hour_text, minute_text = text.split(":", maxsplit=1)
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return default
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default
    return f"{hour:02d}:{minute:02d}"
