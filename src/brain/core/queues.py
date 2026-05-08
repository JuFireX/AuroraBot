from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict
from enum import Enum

from src.brain.core.models import (
    Action,
    ActionStatus,
    Attention,
    AttentionState,
    Plan,
    PlanStatus,
    TodoItem,
    TodoStatus,
    Urgency,
)
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Queues")


class TodoQueue:
    def __init__(self) -> None:
        self._items: dict[str, TodoItem] = {}
        self._order: list[str] = []
        self._has_new_items = False

    def push(self, item: TodoItem) -> None:
        if item.id not in self._items:
            self._order.append(item.id)
        self._items[item.id] = item
        self._has_new_items = True

    def get(self, todo_id: str) -> TodoItem | None:
        return self._items.get(todo_id)

    def get_many(self, todo_ids: list[str]) -> list[TodoItem]:
        return [self._items[todo_id] for todo_id in todo_ids if todo_id in self._items]

    def iter_pending(self) -> list[TodoItem]:
        return [item for item in self.iter_all() if item.status == TodoStatus.PENDING]

    def consume_new_item_flag(self) -> bool:
        had_new_items = self._has_new_items
        self._has_new_items = False
        return had_new_items

    def claim(self, todo_ids: list[str], plan_id: str) -> None:
        now = time.time()
        for todo_id in todo_ids:
            item = self._items.get(todo_id)
            if item is None:
                continue
            item.status = TodoStatus.CLAIMED
            item.claimed_by_plan_id = plan_id
            item.last_seen_at = now

    def mark_done(self, todo_ids: list[str]) -> None:
        now = time.time()
        for todo_id in todo_ids:
            item = self._items.get(todo_id)
            if item is None:
                continue
            item.status = TodoStatus.DONE
            item.last_seen_at = now

    def mark_dropped(self, todo_ids: list[str]) -> None:
        now = time.time()
        for todo_id in todo_ids:
            item = self._items.get(todo_id)
            if item is None:
                continue
            item.status = TodoStatus.DROPPED
            item.last_seen_at = now

    def empty(self) -> bool:
        return not self._items

    def size(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._order.clear()
        self._has_new_items = False

    def replace(self, items: list[TodoItem]) -> None:
        self.clear()
        for item in items:
            self._order.append(item.id)
            self._items[item.id] = item

    def prune_finalized(self, keep_ids: set[str] | None = None) -> None:
        protected = keep_ids or set()
        retained_order: list[str] = []
        retained_items: dict[str, TodoItem] = {}
        for item_id in self._order:
            item = self._items.get(item_id)
            if item is None:
                continue
            if item.id not in protected and item.status in {
                TodoStatus.DONE,
                TodoStatus.DROPPED,
            }:
                continue
            retained_order.append(item_id)
            retained_items[item_id] = item
        self._order = retained_order
        self._items = retained_items

    def iter_all(self) -> list[TodoItem]:
        return [
            self._items[item_id] for item_id in self._order if item_id in self._items
        ]


class PlansQueue:
    def __init__(self) -> None:
        self._plans: list[Plan] = []

    def push(self, plan: Plan) -> None:
        for index, existing in enumerate(self._plans):
            if existing.id == plan.id:
                self._plans[index] = plan
                self._resort()
                return
        self._plans.append(plan)
        self._resort()

    def get(self, plan_id: str) -> Plan | None:
        for plan in self._plans:
            if plan.id == plan_id:
                return plan
        return None

    def highest_priority(self) -> Plan | None:
        for plan in self._plans:
            if plan.status == PlanStatus.PENDING:
                return plan
        return None

    def find_merge_target(self, intent: str, session_id: str) -> Plan | None:
        for plan in self._plans:
            if plan.intent != intent or plan.session_id != session_id:
                continue
            if plan.status in {
                PlanStatus.PENDING,
                PlanStatus.ACTIVE,
                PlanStatus.BLOCKED,
            }:
                return plan
        return None

    def empty(self) -> bool:
        return not self._plans

    def size(self) -> int:
        return len(self._plans)

    def clear(self) -> None:
        self._plans.clear()

    def replace(self, plans: list[Plan]) -> None:
        self._plans = plans
        self._resort()

    def prune_terminal(self, keep_ids: set[str] | None = None) -> None:
        protected = keep_ids or set()
        self._plans = [
            plan
            for plan in self._plans
            if plan.id in protected
            or plan.status not in {PlanStatus.COMPLETED, PlanStatus.FAILED}
        ]
        self._resort()

    def iter_all(self) -> list[Plan]:
        return list(self._plans)

    def _resort(self) -> None:
        self._plans.sort(key=lambda item: item.priority, reverse=True)


class ActionsQueue:
    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._pending_ids: deque[str] = deque()
        self._all_ids: list[str] = []

    def push_all(self, actions: list[Action]) -> None:
        for action in actions:
            if action.id not in self._actions:
                self._all_ids.append(action.id)
            self._actions[action.id] = action
            if action.id not in self._pending_ids:
                self._pending_ids.append(action.id)

    def peek(self) -> Action | None:
        if not self._pending_ids:
            return None
        return self._actions.get(self._pending_ids[0])

    def pop(self) -> Action | None:
        if not self._pending_ids:
            return None
        action_id = self._pending_ids.popleft()
        return self._actions.get(action_id)

    def get(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def update(self, action: Action) -> None:
        if action.id not in self._actions:
            self._all_ids.append(action.id)
        self._actions[action.id] = action

    def remove_pending_ids(self, action_ids: list[str]) -> None:
        if not action_ids:
            return
        drop_ids = set(action_ids)
        self._pending_ids = deque(
            action_id for action_id in self._pending_ids if action_id not in drop_ids
        )

    def clear(self) -> None:
        self._actions.clear()
        self._pending_ids.clear()
        self._all_ids.clear()

    def empty(self) -> bool:
        return not self._pending_ids

    def size(self) -> int:
        return len(self._pending_ids)

    def replace(
        self, actions: list[Action], pending_action_ids: list[str] | None = None
    ) -> None:
        self.clear()
        for action in actions:
            self._all_ids.append(action.id)
            self._actions[action.id] = action
        if pending_action_ids is None:
            pending_action_ids = [
                action.id
                for action in actions
                if action.status in {ActionStatus.PENDING, ActionStatus.RUNNING}
            ]
        self._pending_ids = deque(
            action_id for action_id in pending_action_ids if action_id in self._actions
        )

    def prune_finished(self, keep_ids: set[str] | None = None) -> None:
        protected = keep_ids or set()
        retained_actions: dict[str, Action] = {}
        retained_all_ids: list[str] = []
        for action_id in self._all_ids:
            action = self._actions.get(action_id)
            if action is None:
                continue
            if action.id not in protected and action.status in {
                ActionStatus.SUCCEEDED,
                ActionStatus.FAILED,
                ActionStatus.SKIPPED,
            }:
                continue
            retained_actions[action_id] = action
            retained_all_ids.append(action_id)
        self._actions = retained_actions
        self._all_ids = retained_all_ids
        self._pending_ids = deque(
            action_id for action_id in self._pending_ids if action_id in self._actions
        )

    def iter_all(self) -> list[Action]:
        return [
            self._actions[action_id]
            for action_id in self._all_ids
            if action_id in self._actions
        ]

    def pending_ids(self) -> list[str]:
        return list(self._pending_ids)


todo_queue = TodoQueue()
plans_queue = PlansQueue()
actions_queue = ActionsQueue()
current_attention: Attention | None = None


def set_current_attention(attention: Attention | None) -> None:
    global current_attention
    current_attention = attention


def clear_current_attention() -> None:
    set_current_attention(None)


def reset_runtime_queues() -> None:
    clear_current_attention()
    todo_queue.clear()
    plans_queue.clear()
    actions_queue.clear()


def persist_runtime_snapshot(reason: str = "manual") -> None:
    prune_runtime_state()
    snapshot = {
        "version": "4.1",
        "updated_at": time.time(),
        "reason": reason,
        "queues": {
            "todo": [_to_json_ready(item) for item in todo_queue.iter_all()],
            "plans": [_to_json_ready(item) for item in plans_queue.iter_all()],
            "actions": [_to_json_ready(item) for item in actions_queue.iter_all()],
            "pending_action_ids": actions_queue.pending_ids(),
            "attention": _to_json_ready(current_attention),
        },
    }
    Config.QUEUES_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    Config.QUEUES_SNAPSHOT_FILE.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prune_runtime_state() -> None:
    protected_plan_ids: set[str] = set()
    protected_todo_ids: set[str] = set()
    protected_action_ids: set[str] = set()

    if current_attention is not None:
        protected_plan_ids.add(current_attention.plan_id)
        protected_todo_ids.update(current_attention.source_todo_ids)
        protected_action_ids.update(current_attention.action_ids)

    for plan in plans_queue.iter_all():
        if plan.status in {PlanStatus.PENDING, PlanStatus.ACTIVE, PlanStatus.BLOCKED}:
            protected_plan_ids.add(plan.id)
            protected_todo_ids.update(plan.source_todo_ids)

    plans_queue.prune_terminal(protected_plan_ids)
    actions_queue.prune_finished(protected_action_ids)
    todo_queue.prune_finalized(protected_todo_ids)


def restore_runtime_snapshot() -> bool:
    file_path = Config.QUEUES_SNAPSHOT_FILE
    if not file_path.exists():
        return False
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
        queue_payload = payload.get("queues", {})
        restored_todos = [
            _todo_from_dict(item)
            for item in queue_payload.get("todo", [])
            if isinstance(item, dict)
        ]
        restored_plans = [
            _plan_from_dict(item)
            for item in queue_payload.get("plans", [])
            if isinstance(item, dict)
        ]
        restored_actions = [
            _action_from_dict(item)
            for item in queue_payload.get("actions", [])
            if isinstance(item, dict)
        ]
        restored_pending_action_ids = [
            str(item)
            for item in queue_payload.get("pending_action_ids", [])
            if str(item).strip()
        ]
        attention_data = queue_payload.get("attention")
        restored_attention = (
            _attention_from_dict(attention_data)
            if isinstance(attention_data, dict)
            else None
        )
        _validate_runtime_consistency(
            restored_actions,
            restored_pending_action_ids,
            restored_attention,
        )
        todo_queue.replace(restored_todos)
        plans_queue.replace(restored_plans)
        actions_queue.replace(restored_actions, restored_pending_action_ids)
        set_current_attention(restored_attention)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to restore queue snapshot: %s", exc)
        return False


def _to_json_ready(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_to_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_ready(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _to_json_ready(asdict(value))
    return value


def _todo_from_dict(data: dict[str, object]) -> TodoItem:
    return TodoItem(
        id=str(data.get("id", "")),
        type=str(data.get("type", "")),
        payload=dict(data.get("payload", {})),
        urgency=Urgency(str(data.get("urgency", Urgency.NORMAL.value))),
        status=TodoStatus(str(data.get("status", TodoStatus.PENDING.value))),
        claimed_by_plan_id=(
            str(data.get("claimed_by_plan_id"))
            if data.get("claimed_by_plan_id") is not None
            else None
        ),
        created_at=float(data.get("created_at", 0.0)),
        last_seen_at=float(data.get("last_seen_at", 0.0)),
    )


def _plan_from_dict(data: dict[str, object]) -> Plan:
    return Plan(
        id=str(data.get("id", "")),
        intent=str(data.get("intent", "")),
        summary=str(data.get("summary", "")),
        session_id=str(data.get("session_id", "")),
        priority=float(data.get("priority", 0.0)),
        base_priority=float(data.get("base_priority", 0.0)),
        status=PlanStatus(str(data.get("status", PlanStatus.PENDING.value))),
        source_todo_ids=[
            str(item) for item in data.get("source_todo_ids", []) if str(item).strip()
        ],
        related_episodes=[
            str(item) for item in data.get("related_episodes", []) if str(item).strip()
        ],
        attention_count=int(data.get("attention_count", 0)),
        expand_fail_count=int(data.get("expand_fail_count", 0)),
        last_expanded_at=float(data.get("last_expanded_at", 0.0)),
        last_error=str(data.get("last_error", "")),
        created_at=float(data.get("created_at", 0.0)),
        last_touched_at=float(data.get("last_touched_at", 0.0)),
    )


def _action_from_dict(data: dict[str, object]) -> Action:
    capability_name = str(data.get("capability_name", data.get("tool_name", "")))
    return Action(
        id=str(data.get("id", "")),
        plan_id=str(data.get("plan_id", "")),
        capability_name=capability_name,
        params=dict(data.get("params", {})),
        order=int(data.get("order", 0)),
        status=ActionStatus(str(data.get("status", ActionStatus.PENDING.value))),
        result_summary=str(data.get("result_summary", "")),
        error_message=str(data.get("error_message", "")),
        created_at=float(data.get("created_at", 0.0)),
        started_at=float(data.get("started_at", 0.0)),
        finished_at=float(data.get("finished_at", 0.0)),
    )


def _attention_from_dict(data: dict[str, object]) -> Attention:
    return Attention(
        id=str(data.get("id", "")),
        plan_id=str(data.get("plan_id", "")),
        intent=str(data.get("intent", "")),
        priority=float(data.get("priority", 0.0)),
        action_ids=[
            str(item) for item in data.get("action_ids", []) if str(item).strip()
        ],
        source_todo_ids=[
            str(item) for item in data.get("source_todo_ids", []) if str(item).strip()
        ],
        current_index=int(data.get("current_index", 0)),
        state=AttentionState(str(data.get("state", AttentionState.ACTIVE.value))),
        started_at=float(data.get("started_at", 0.0)),
        last_advanced_at=float(data.get("last_advanced_at", 0.0)),
    )


def _validate_runtime_consistency(
    actions: list[Action],
    pending_action_ids: list[str],
    attention: Attention | None,
) -> None:
    action_ids = {action.id for action in actions}
    if attention is None:
        if pending_action_ids:
            raise ValueError("snapshot contains pending actions without attention")
        return
    if attention.state in {AttentionState.COMPLETED, AttentionState.FAILED}:
        raise ValueError("snapshot contains completed attention")
    if not attention.action_ids:
        raise ValueError("attention.action_ids must not be empty")
    if attention.current_index < 0 or attention.current_index > len(
        attention.action_ids
    ):
        raise ValueError("attention.current_index is out of range")
    if any(action_id not in action_ids for action_id in attention.action_ids):
        raise ValueError("attention references missing actions")
    remaining_actions = attention.action_ids[attention.current_index :]
    if pending_action_ids != remaining_actions:
        raise ValueError(
            "attention progress mismatch: "
            f"remaining={remaining_actions} actual={pending_action_ids}"
        )
