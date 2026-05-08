import asyncio
import time
import unittest

from src.brain.core.models import TodoItem, Urgency
from src.brain.core.planner import run
from src.brain.core.queues import plans_queue, todo_queue
from src.brain.core.state import bot_state
from src.brain.memory.episodic import episode_store
from src.config import Config


class PlannerActivityStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_debounce = Config.QQ_REPLY_DEBOUNCE_SECONDS
        Config.QQ_REPLY_DEBOUNCE_SECONDS = 0.0
        todo_queue.clear()
        plans_queue.clear()
        bot_state.reset()
        episode_store.clear()

    def tearDown(self) -> None:
        Config.QQ_REPLY_DEBOUNCE_SECONDS = self._original_debounce

    def test_planner_records_activity_and_creates_plan(self) -> None:
        todo_queue.push(
            TodoItem(
                id="1",
                type="qq_msg",
                payload={"session_id": "s1", "text": "hi", "user_id": "u1"},
                urgency=Urgency.NORMAL,
            )
        )
        created = asyncio.run(run())
        self.assertEqual(len(created), 1)
        self.assertGreater(bot_state.activity_rate, 0.0)

    def test_planner_defers_recent_qq_messages_for_batching(self) -> None:
        Config.QQ_REPLY_DEBOUNCE_SECONDS = 5.0
        todo_queue.push(
            TodoItem(
                id="1",
                type="qq_msg",
                payload={"session_id": "s1", "text": "第一句", "user_id": "u1"},
                urgency=Urgency.NORMAL,
                created_at=time.time(),
            )
        )
        created = asyncio.run(run())
        self.assertEqual(created, [])

        now = time.time() - 10
        todo_queue.clear()
        plans_queue.clear()
        todo_queue.push(
            TodoItem(
                id="1",
                type="qq_msg",
                payload={"session_id": "s1", "text": "第一句", "user_id": "u1"},
                urgency=Urgency.NORMAL,
                created_at=now,
            )
        )
        todo_queue.push(
            TodoItem(
                id="2",
                type="qq_msg",
                payload={"session_id": "s1", "text": "第二句", "user_id": "u1"},
                urgency=Urgency.NORMAL,
                created_at=now + 1,
            )
        )
        created = asyncio.run(run())
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].source_todo_ids, ["1", "2"])


if __name__ == "__main__":
    unittest.main()
