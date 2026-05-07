import tempfile
import unittest
from pathlib import Path

from src.brain.core.models import Action, Attention, AttentionState, Plan, TodoItem
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
                    sub_items=[],
                    priority=1.0,
                    base_priority=1.0,
                )
            )
            actions_queue.push_all([Action(id="action", capability_name="demo.echo", params={})])
            set_current_attention(
                Attention(
                    plan_id="plan",
                    intent="handle_qq_messages",
                    priority=1.0,
                    action_count=1,
                    current_index=0,
                    state=AttentionState.ACTIVE,
                )
            )
            persist_runtime_snapshot("test")
            reset_runtime_queues()
            self.assertTrue(restore_runtime_snapshot())
        Config.QUEUES_SNAPSHOT_FILE = original_path


if __name__ == "__main__":
    unittest.main()
