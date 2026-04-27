import asyncio
from pathlib import Path
from polaris.brain.core.agent import instance
from polaris.brain.core.models import TodoItem, Urgency
from polaris.utils.Logger import get_logger

logger = get_logger()

# Ensure data dir exists
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class AlarmService:
    def __init__(self):
        self._running = False
        self._task = None

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("[AlarmService] Started")
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("[AlarmService] Stopped")

    async def _loop(self):
        while self._running:
            # Simulate a scheduled alarm every 30 seconds
            await asyncio.sleep(30)
            logger.info("[AlarmService] Triggering a scheduled alarm...")
            todo = TodoItem(
                type="alarm_reminder",
                payload={"message": "Time to stretch!"},
                urgency=Urgency.GENTLE,
            )
            instance.push_todo(todo)


alarm_service_instance = AlarmService()
