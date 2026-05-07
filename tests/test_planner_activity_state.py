import asyncio
import unittest

from src.brain.core.models import TodoItem, Urgency
from src.brain.core.planner import run
from src.brain.core.queues import plans_queue, todo_queue
from src.brain.core.state import bot_state
from src.brain.memory.episodic import episode_store


class PlannerActivityStateTest(unittest.TestCase):
    def setUp(self) -> None:
        todo_queue.clear()
        plans_queue.clear()
        bot_state.reset()
        episode_store.clear()

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


if __name__ == "__main__":
    unittest.main()
