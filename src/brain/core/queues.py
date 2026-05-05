from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict
from enum import Enum

from src.brain.core.models import Action, Attention, AttentionState, Plan, TodoItem, Urgency
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Queues")


class TodoQueue:
    def __init__(self) -> None:
        self._q: deque[TodoItem] = deque()

    def push(self, item: TodoItem) -> None:
        self._q.append(item)
        _autosave()

    def drain(self) -> list[TodoItem]:
        items = list(self._q)
        self._q.clear()
        _autosave()
        return items

    def empty(self) -> bool:
        return not self._q

    def size(self) -> int:
        return len(self._q)

    def clear(self) -> None:
        self._q.clear()
        _autosave()

    def replace(self, items: list[TodoItem]) -> None:
        self._q = deque(items)
        _autosave()

    def iter_all(self) -> list[TodoItem]:
        return list(self._q)


class PlansQueue:
    def __init__(self) -> None:
        self._plans: list[Plan] = []

    def push(self, plan: Plan) -> None:
        self._plans.append(plan)
        self._plans.sort(key=lambda item: item.priority, reverse=True)
        _autosave()

    def pop_highest(self) -> Plan | None:
        result = self._plans.pop(0) if self._plans else None
        _autosave()
        return result

    def pop_lowest(self) -> Plan | None:
        result = self._plans.pop(-1) if self._plans else None
        _autosave()
        return result

    def remove(self, plan_id: str) -> None:
        self._plans = [plan for plan in self._plans if plan.id != plan_id]
        _autosave()

    def empty(self) -> bool:
        return not self._plans

    def size(self) -> int:
        return len(self._plans)

    def iter_all(self) -> list[Plan]:
        return list(self._plans)

    def clear(self) -> None:
        self._plans.clear()
        _autosave()

    def replace(self, plans: list[Plan]) -> None:
        self._plans = plans
        self._plans.sort(key=lambda item: item.priority, reverse=True)
        _autosave()


class ActionsQueue:
    def __init__(self) -> None:
        self._q: deque[Action] = deque()

    def push_all(self, actions: list[Action]) -> None:
        self._q.extend(actions)
        _autosave()

    def peek(self) -> Action | None:
        return self._q[0] if self._q else None

    def pop(self) -> Action | None:
        result = self._q.popleft() if self._q else None
        _autosave()
        return result

    def clear(self) -> None:
        self._q.clear()
        _autosave()

    def empty(self) -> bool:
        return not self._q

    def size(self) -> int:
        return len(self._q)

    def replace(self, actions: list[Action]) -> None:
        self._q = deque(actions)
        _autosave()

    def iter_all(self) -> list[Action]:
        return list(self._q)


todo_queue = TodoQueue()
plans_queue = PlansQueue()
actions_queue = ActionsQueue()
current_attention: Attention | None = None


def set_current_attention(attention: Attention | None) -> None:
    global current_attention
    current_attention = attention
    _autosave()


def clear_current_attention() -> None:
    set_current_attention(None)


def reset_runtime_queues() -> None:
    clear_current_attention()
    todo_queue.clear()
    plans_queue.clear()
    actions_queue.clear()
    persist_runtime_snapshot("reset")


def persist_runtime_snapshot(reason: str = "manual") -> None:
    snapshot = {
        "version": "2.1",
        "updated_at": time.time(),
        "reason": reason,
        "queues": {
            "todo": [_to_json_ready(item) for item in todo_queue.iter_all()],
            "plans": [_to_json_ready(item) for item in plans_queue.iter_all()],
            "actions": [_to_json_ready(item) for item in actions_queue.iter_all()],
            "attention": _to_json_ready(current_attention),
        },
    }
    Config.QUEUES_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    Config.QUEUES_SNAPSHOT_FILE.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def restore_runtime_snapshot() -> bool:
    file_path = Config.QUEUES_SNAPSHOT_FILE
    if not file_path.exists():
        return False

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        queue_payload = payload.get("queues", {})
        todo_queue.replace([_todo_from_dict(item) for item in queue_payload.get("todo", [])])
        plans_queue.replace([_plan_from_dict(item) for item in queue_payload.get("plans", [])])
        actions_queue.replace(
            [_action_from_dict(item) for item in queue_payload.get("actions", [])]
        )
        attention_data = queue_payload.get("attention")
        set_current_attention(
            _attention_from_dict(attention_data) if isinstance(attention_data, dict) else None
        )
        logger.info(
            "[Queues] Restored snapshot todo=%s plans=%s actions=%s attention=%s",
            todo_queue.size(),
            plans_queue.size(),
            actions_queue.size(),
            "yes" if current_attention else "no",
        )
        return True
    except Exception as exc:
        logger.error("[Queues] Failed to restore snapshot: %s", exc)
        return False


def _autosave() -> None:
    if Config.QUEUES_AUTOSAVE:
        persist_runtime_snapshot("autosave")


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
        created_at=float(data.get("created_at", 0.0)),
        suggested_window=dict(data["suggested_window"]) if isinstance(data.get("suggested_window"), dict) else None,
    )


def _plan_from_dict(data: dict[str, object]) -> Plan:
    sub_items = [_todo_from_dict(item) for item in data.get("sub_items", []) if isinstance(item, dict)]
    return Plan(
        id=str(data.get("id", "")),
        intent=str(data.get("intent", "")),
        sub_items=sub_items,
        priority=float(data.get("priority", 0.0)),
        base_priority=float(data.get("base_priority", 0.0)),
        weight=float(data.get("weight", 1.0)),
        created_at=float(data.get("created_at", 0.0)),
        last_touched_at=float(data.get("last_touched_at", 0.0)),
    )


def _action_from_dict(data: dict[str, object]) -> Action:
    preconditions = data.get("preconditions", [])
    return Action(
        id=str(data.get("id", "")),
        tool_name=str(data.get("tool_name", "")),
        params=dict(data.get("params", {})),
        energy_cost=float(data.get("energy_cost", 1.0)),
        preconditions=list(preconditions) if isinstance(preconditions, list) else [],
    )


def _attention_from_dict(data: dict[str, object]) -> Attention:
    return Attention(
        plan_id=str(data.get("plan_id", "")),
        intent=str(data.get("intent", "")),
        priority=float(data.get("priority", 0.0)),
        total_energy_estimate=float(data.get("total_energy_estimate", 0.0)),
        action_count=int(data.get("action_count", 0)),
        current_index=int(data.get("current_index", 0)),
        state=AttentionState(str(data.get("state", AttentionState.ACTIVE.value))),
        created_at=float(data.get("created_at", 0.0)),
    )
