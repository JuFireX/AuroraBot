import tempfile
import unittest
import json
from pathlib import Path

from src.brain.core.models import (
    Action,
    ActionStatus,
    Attention,
    AttentionState,
    Plan,
    PlanStatus,
    TodoItem,
    TodoStatus,
)
from src.brain.core.queues import (
    actions_queue,
    plans_queue,
    reset_runtime_queues,
    restore_runtime_snapshot,
    set_current_attention,
    todo_queue,
    persist_runtime_snapshot,
)
from src.config import Config


class QueueSnapshotRestoreTest(unittest.TestCase):
    def test_snapshot_restore_round_trip(self) -> None:
        original_path = Config.QUEUES_SNAPSHOT_FILE
        with tempfile.TemporaryDirectory() as tmp_dir:
            Config.QUEUES_SNAPSHOT_FILE = Path(tmp_dir) / "runtime_queues.json"
            reset_runtime_queues()
            todo_queue.push(TodoItem(id="todo", type="qq_msg", payload={"session_id": "s1"}))
            plans_queue.push(
                Plan(
                    id="plan",
                    intent="handle_qq_messages",
                    summary="处理QQ消息",
                    session_id="s1",
                    priority=1.0,
                    base_priority=1.0,
                    source_todo_ids=["todo"],
                )
            )
            actions_queue.push_all(
                [Action(id="action", plan_id="plan", capability_name="demo.echo", params={})]
            )
            set_current_attention(
                Attention(
                    id="attention",
                    plan_id="plan",
                    intent="handle_qq_messages",
                    priority=1.0,
                    action_ids=["action"],
                    source_todo_ids=["todo"],
                    current_index=0,
                    state=AttentionState.ACTIVE,
                )
            )
            persist_runtime_snapshot("test")
            reset_runtime_queues()
            self.assertTrue(restore_runtime_snapshot())
        Config.QUEUES_SNAPSHOT_FILE = original_path

    def test_snapshot_prunes_terminal_runtime_items(self) -> None:
        original_path = Config.QUEUES_SNAPSHOT_FILE
        with tempfile.TemporaryDirectory() as tmp_dir:
            Config.QUEUES_SNAPSHOT_FILE = Path(tmp_dir) / "runtime_queues.json"
            reset_runtime_queues()
            todo_queue.push(
                TodoItem(
                    id="done-todo",
                    type="qq_msg",
                    payload={"session_id": "s1"},
                    status=TodoStatus.DONE,
                )
            )
            plans_queue.push(
                Plan(
                    id="done-plan",
                    intent="handle_qq_messages",
                    summary="处理QQ消息",
                    session_id="s1",
                    priority=1.0,
                    base_priority=1.0,
                    status=PlanStatus.COMPLETED,
                    source_todo_ids=["done-todo"],
                )
            )
            actions_queue.push_all(
                [
                    Action(
                        id="done-action",
                        plan_id="done-plan",
                        capability_name="demo.echo",
                        params={},
                        status=ActionStatus.SUCCEEDED,
                    )
                ]
            )

            persist_runtime_snapshot("test-prune")

            payload = json.loads(Config.QUEUES_SNAPSHOT_FILE.read_text(encoding="utf-8"))
            queues_payload = payload["queues"]
            self.assertEqual(queues_payload["todo"], [])
            self.assertEqual(queues_payload["plans"], [])
            self.assertEqual(queues_payload["actions"], [])
        Config.QUEUES_SNAPSHOT_FILE = original_path


if __name__ == "__main__":
    unittest.main()
