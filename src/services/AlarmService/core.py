from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from typing import Any

from nonebot import get_bot

from src.brain.core.models import TodoItem, Urgency
from src.brain.core.state import bot_state
from src.brain.core.tool_registry import Tool, register
from src.brain.core.queues import todo_queue
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("AlarmService")


class AlarmService:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._registered = False
        self._alarms_file = Config.ALARM_DATA_DIR / "alarms.json"
        self._alarms: list[dict[str, Any]] = []
        self._alert_decisions: dict[str, bool] = {}

    async def start(self) -> None:
        if not self._registered:
            self._register_tools()
            self._registered = True
        if self._running:
            return
        self._load_alarms()
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[AlarmService] Started")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
        self._save_alarms()
        logger.info("[AlarmService] Stopped")

    async def _loop(self) -> None:
        while self._running:
            self._dispatch_due_alarms()
            await asyncio.sleep(Config.ALARM_LOOP_INTERVAL_SECONDS)

    def _dispatch_due_alarms(self) -> None:
        now = time.time()
        changed = False
        for alarm in self._alarms:
            if not alarm.get("enabled", True):
                continue
            if alarm.get("pending", False):
                continue
            if float(alarm.get("next_trigger_at", now + 1)) > now:
                continue

            todo_type = "diary_prompt" if alarm.get("alarm_type") == "diary_prompt" else "alarm_reminder"
            if todo_type == "diary_prompt":
                alarm["date"] = time.strftime("%Y-%m-%d")
            todo = TodoItem(
                id=str(uuid.uuid4()),
                type=todo_type,
                payload=alarm.copy(),
                urgency=Urgency.GENTLE,
                created_at=now,
            )
            todo_queue.push(todo)
            alarm["pending"] = True
            changed = True
            logger.info("[AlarmService] Triggered %s (%s)", alarm.get("id"), todo_type)

        if changed:
            self._save_alarms()

    def _register_tools(self) -> None:
        register(
            Tool(
                name="set_alarm",
                description="设置一个在指定时间触发的提醒",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "interval_seconds": {"type": "number"},
                        "alarm_type": {"type": "string"},
                    },
                    "required": ["message"],
                },
                handler=self.set_alarm,
            )
        )
        register(
            Tool(
                name="evaluate_ignore",
                description="根据忙碌程度判断是否忽略柔性提醒",
                parameters_schema={"type": "object", "properties": {"alarm": {"type": "object"}}, "required": ["alarm"]},
                handler=self.evaluate_ignore,
            )
        )
        register(
            Tool(
                name="alert_user",
                description="将提醒发送给用户或打印日志",
                parameters_schema={"type": "object", "properties": {"alarm": {"type": "object"}}, "required": ["alarm"]},
                handler=self.alert_user,
            )
        )
        register(
            Tool(
                name="finalize_alarm",
                description="完成一次闹钟处理并安排下次触发",
                parameters_schema={"type": "object", "properties": {"alarm": {"type": "object"}}, "required": ["alarm"]},
                handler=self.finalize_alarm,
            )
        )

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
            "pending": False,
            "interval_seconds": interval_seconds or Config.ALARM_DEFAULT_INTERVAL_SECONDS,
            "snooze_seconds": 300,
            "grace_seconds": 300,
            "next_trigger_at": now + (interval_seconds or Config.ALARM_DEFAULT_INTERVAL_SECONDS),
            "last_triggered_at": None,
            "alarm_type": alarm_type,
            "target": {},
        }
        self._alarms.append(alarm)
        self._save_alarms()
        return {"alarm_id": alarm["id"], "status": "created"}

    def evaluate_ignore(self, alarm: dict[str, object]) -> dict[str, object]:
        alarm_id = str(alarm.get("id", "unknown"))
        should_ignore = (
            bot_state.cognitive_load >= bot_state.busy_threshold
            or bot_state.energy_current < 20
        ) and random.random() < Config.GENTLE_IGNORE_CHANCE
        self._alert_decisions[alarm_id] = not should_ignore
        logger.info(
            "[AlarmService] Alarm %s decision=%s",
            alarm_id,
            "ignore" if should_ignore else "alert",
        )
        return {"alarm_id": alarm_id, "should_alert": not should_ignore}

    async def alert_user(self, alarm: dict[str, object]) -> dict[str, object]:
        message = str(alarm.get("message", "提醒时间到了"))
        alarm_id = str(alarm.get("id", "unknown"))
        if not self._alert_decisions.get(alarm_id, True):
            logger.info("[AlarmService] Skipped alert for %s", alarm_id)
            return {"alarm_id": alarm_id, "status": "skipped"}
        try:
            target = alarm.get("target", {})
            bot_id = target.get("bot_id") if isinstance(target, dict) else None
            if bot_id:
                bot = get_bot(str(bot_id))
                if isinstance(target, dict) and target.get("group_id") is not None:
                    await bot.send_group_msg(group_id=target["group_id"], message=message)
                elif isinstance(target, dict) and target.get("user_id") is not None:
                    await bot.send_private_msg(user_id=target["user_id"], message=message)
            logger.info("[AlarmService] Alerted %s: %s", alarm_id, message)
            return {"alarm_id": alarm_id, "status": "alerted"}
        except Exception as exc:
            logger.error("[AlarmService] Failed to alert %s: %s", alarm_id, exc)
            return {"alarm_id": alarm_id, "status": "failed"}

    def finalize_alarm(self, alarm: dict[str, object]) -> dict[str, object]:
        alarm_id = str(alarm.get("id", ""))
        should_alert = self._alert_decisions.pop(alarm_id, True)
        for item in self._alarms:
            if item.get("id") != alarm_id:
                continue
            interval_seconds = float(item.get("interval_seconds", Config.ALARM_DEFAULT_INTERVAL_SECONDS))
            snooze_seconds = float(item.get("snooze_seconds", 300))
            item["pending"] = False
            item["last_triggered_at"] = time.time()
            item["next_trigger_at"] = time.time() + (
                interval_seconds if should_alert else snooze_seconds
            )
            break
        self._save_alarms()
        return {"alarm_id": alarm_id, "status": "finalized"}

    def _load_alarms(self) -> None:
        if self._alarms_file.exists():
            try:
                self._alarms = json.loads(self._alarms_file.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                logger.error("[AlarmService] Failed to load alarms: %s", exc)
                self._alarms = []
        if not self._alarms:
            self._alarms = self._default_alarms()
            self._save_alarms()

    def _default_alarms(self) -> list[dict[str, Any]]:
        now = time.time()
        diary_interval = _seconds_until_next_diary_time()
        return [
            {
                "id": "default_stretch_alarm",
                "message": "Time to stretch!",
                "enabled": True,
                "pending": False,
                "interval_seconds": Config.ALARM_DEFAULT_INTERVAL_SECONDS,
                "snooze_seconds": 300,
                "grace_seconds": 300,
                "next_trigger_at": now + Config.ALARM_DEFAULT_INTERVAL_SECONDS,
                "last_triggered_at": None,
                "alarm_type": "generic",
                "target": {},
            },
            {
                "id": "daily_diary_prompt",
                "message": "该写日记了，回顾一下今天的经历。",
                "summary": "今天的经历回顾",
                "interactions": [],
                "reflections": "",
                "date": time.strftime("%Y-%m-%d"),
                "enabled": True,
                "pending": False,
                "interval_seconds": 86400,
                "snooze_seconds": 1800,
                "grace_seconds": 1800,
                "next_trigger_at": now + diary_interval,
                "last_triggered_at": None,
                "alarm_type": "diary_prompt",
                "target": {},
            },
        ]

    def _save_alarms(self) -> None:
        try:
            self._alarms_file.parent.mkdir(parents=True, exist_ok=True)
            self._alarms_file.write_text(
                json.dumps(self._alarms, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("[AlarmService] Failed to save alarms: %s", exc)


def _seconds_until_next_diary_time() -> int:
    now = time.localtime()
    hour_text, minute_text = Config.DIARY_TIME.split(":", maxsplit=1)
    target_hour = int(hour_text)
    target_minute = int(minute_text)
    current_seconds = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
    target_seconds = target_hour * 3600 + target_minute * 60
    if target_seconds <= current_seconds:
        return 86400 - current_seconds + target_seconds
    return target_seconds - current_seconds


alarm_service_instance = AlarmService()
