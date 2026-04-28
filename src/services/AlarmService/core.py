import asyncio
import json
import random
import time

from nonebot import get_bot

from src.brain.core.agent import instance
from src.brain.core.executor import executor_registry
from src.brain.core.models import TodoItem, Urgency
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger()


class AlarmService:
    def __init__(self):
        self._running = False
        self._task = None
        self._registered = False
        self._alarms_file = Config.ALARM_DATA_DIR / "alarms.json"
        self._alarms: list[dict] = []
        self._alert_decisions: dict[str, bool] = {}

    async def start(self):
        if not self._registered:
            executor_registry.register("evaluate_ignore", self.execute_evaluate_ignore)
            executor_registry.register("alert_user", self.execute_alert_user)
            executor_registry.register("finalize_alarm", self.execute_finalize_alarm)
            executor_registry.register_precondition(
                "alarm_should_alert", self.precondition_alarm_should_alert
            )
            self._registered = True

        if self._running:
            return

        self._load_alarms()
        self._running = True
        logger.info("[AlarmService] Started")
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        self._save_alarms()
        logger.info("[AlarmService] Stopped")

    async def _loop(self):
        while self._running:
            self._dispatch_due_alarms()
            await asyncio.sleep(Config.ALARM_LOOP_INTERVAL_SECONDS)

    def _dispatch_due_alarms(self):
        now = time.time()
        changed = False
        for alarm in self._alarms:
            if not alarm.get("enabled", True):
                continue
            if alarm.get("pending", False):
                continue
            if alarm.get("next_trigger_at", now + 1) > now:
                continue

            logger.info(f"[AlarmService] Triggering alarm {alarm['id']}")
            todo = TodoItem(
                type="alarm_reminder",
                payload=alarm.copy(),
                urgency=Urgency.GENTLE,
                group_key=alarm["id"],
                suggested_time_window={
                    "start": alarm["next_trigger_at"],
                    "end": alarm["next_trigger_at"] + alarm.get("grace_seconds", 300),
                },
            )
            instance.push_todo(todo)
            alarm["pending"] = True
            changed = True

        if changed:
            self._save_alarms()

    async def execute_evaluate_ignore(self, action):
        alarm = action.params.get("alarm", {})
        alarm_id = alarm.get("id", "unknown")

        should_ignore = (
            instance.state.cognitive_load >= instance.state.busy_threshold
            or instance.state.energy_current < 20
        ) and random.random() < Config.GENTLE_IGNORE_CHANCE

        self._alert_decisions[alarm_id] = not should_ignore
        logger.info(
            f"[AlarmService] Alarm {alarm_id} decision: {'alert' if not should_ignore else 'ignore'}"
        )

    async def precondition_alarm_should_alert(self, action) -> bool:
        alarm = action.params.get("alarm", {})
        alarm_id = alarm.get("id", "unknown")
        return self._alert_decisions.get(alarm_id, True)

    async def execute_alert_user(self, action):
        alarm = action.params.get("alarm", {})
        message = alarm.get("message", "提醒时间到了")
        alarm_id = alarm.get("id", "unknown")

        try:
            target = alarm.get("target", {})
            bot_id = target.get("bot_id")
            if bot_id:
                bot = get_bot(str(bot_id))
                if target.get("group_id") is not None:
                    await bot.send_group_msg(
                        group_id=target["group_id"], message=message
                    )
                elif target.get("user_id") is not None:
                    await bot.send_private_msg(
                        user_id=target["user_id"], message=message
                    )
            logger.info(f"[AlarmService] Alerted alarm {alarm_id}: {message}")
        except Exception as e:
            logger.error(f"[AlarmService] Failed to alert alarm {alarm_id}: {e}")

    async def execute_finalize_alarm(self, action):
        alarm = action.params.get("alarm", {})
        alarm_id = alarm.get("id")
        if alarm_id is None:
            return

        should_alert = self._alert_decisions.pop(alarm_id, True)
        for item in self._alarms:
            if item["id"] != alarm_id:
                continue

            interval_seconds = item.get(
                "interval_seconds", Config.ALARM_DEFAULT_INTERVAL_SECONDS
            )
            snooze_seconds = item.get("snooze_seconds", 300)
            item["pending"] = False
            item["last_triggered_at"] = time.time()
            item["next_trigger_at"] = time.time() + (
                interval_seconds if should_alert else snooze_seconds
            )
            break

        self._save_alarms()

    def _load_alarms(self):
        if self._alarms_file.exists():
            try:
                self._alarms = json.loads(self._alarms_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"[AlarmService] Failed to load alarms: {e}")
                self._alarms = []

        if not self._alarms:
            now = time.time()
            self._alarms = [
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
                    "target": {},
                }
            ]
            self._save_alarms()

    def _save_alarms(self):
        try:
            self._alarms_file.parent.mkdir(parents=True, exist_ok=True)
            self._alarms_file.write_text(
                json.dumps(self._alarms, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[AlarmService] Failed to save alarms: {e}")


alarm_service_instance = AlarmService()
