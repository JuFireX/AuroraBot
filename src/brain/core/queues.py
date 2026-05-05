from __future__ import annotations

from collections import deque

from src.brain.core.models import Action, Attention, Plan, TodoItem


class TodoQueue:
    def __init__(self) -> None:
        self._q: deque[TodoItem] = deque()

    def push(self, item: TodoItem) -> None:
        self._q.append(item)

    def drain(self) -> list[TodoItem]:
        items = list(self._q)
        self._q.clear()
        return items

    def empty(self) -> bool:
        return not self._q

    def size(self) -> int:
        return len(self._q)

    def clear(self) -> None:
        self._q.clear()


class PlansQueue:
    def __init__(self) -> None:
        self._plans: list[Plan] = []

    def push(self, plan: Plan) -> None:
        self._plans.append(plan)
        self._plans.sort(key=lambda item: item.priority, reverse=True)

    def pop_highest(self) -> Plan | None:
        return self._plans.pop(0) if self._plans else None

    def pop_lowest(self) -> Plan | None:
        return self._plans.pop(-1) if self._plans else None

    def remove(self, plan_id: str) -> None:
        self._plans = [plan for plan in self._plans if plan.id != plan_id]

    def empty(self) -> bool:
        return not self._plans

    def size(self) -> int:
        return len(self._plans)

    def iter_all(self) -> list[Plan]:
        return list(self._plans)

    def clear(self) -> None:
        self._plans.clear()


class ActionsQueue:
    def __init__(self) -> None:
        self._q: deque[Action] = deque()

    def push_all(self, actions: list[Action]) -> None:
        self._q.extend(actions)

    def peek(self) -> Action | None:
        return self._q[0] if self._q else None

    def pop(self) -> Action | None:
        return self._q.popleft() if self._q else None

    def clear(self) -> None:
        self._q.clear()

    def empty(self) -> bool:
        return not self._q

    def size(self) -> int:
        return len(self._q)


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
