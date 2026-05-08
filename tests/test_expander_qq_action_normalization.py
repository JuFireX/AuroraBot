import unittest

from src.brain.core.expander import _normalize_action_params
from src.brain.core.models import Plan, TodoItem
from src.brain.core.queues import plans_queue, todo_queue


class ExpanderQQActionNormalizationTest(unittest.TestCase):
    def setUp(self) -> None:
        todo_queue.clear()
        plans_queue.clear()

    def test_private_message_action_accepts_message_alias(self) -> None:
        todo_queue.push(
            TodoItem(
                id="todo-1",
                type="qq_msg",
                payload={
                    "session_id": "2779675416",
                    "user_id": "2779675416",
                    "text": "说说话~",
                },
            )
        )
        plan = Plan(
            id="plan-1",
            intent="handle_qq_messages",
            summary="处理QQ消息",
            session_id="2779675416",
            priority=1.0,
            base_priority=1.0,
            source_todo_ids=["todo-1"],
        )
        normalized = _normalize_action_params(
            plan,
            "im.polaris.qq.send_qq_private_message",
            {"message": "在呢~"},
        )
        self.assertEqual(normalized["text"], "在呢~")
        self.assertEqual(normalized["user_id"], "2779675416")
        self.assertNotIn("message", normalized)


if __name__ == "__main__":
    unittest.main()
