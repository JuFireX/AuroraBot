from src.brain.core.state import State
from src.brain.core.queues import Queues
from src.brain.core.engine import HeartbeatEngine
from src.brain.core.models import TodoItem
from src.config import Config


class Agent:
    def __init__(self):
        self.state = State.load()
        self.queues = Queues.load()
        self.engine = HeartbeatEngine(self.state, self.queues)

    def push_todo(self, item: TodoItem):
        self.queues.todo_queue.push(item)
        self.queues.save()

    async def start(self):
        await self.engine.start(interval_seconds=Config.HEARTBEAT_INTERVAL_SECONDS)

    def stop(self):
        self.engine.stop()
        self.state.save()
        self.queues.save()


# 全局单例
instance = Agent()
