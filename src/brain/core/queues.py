import heapq
import json
from typing import List, Optional
from collections import deque
from src.config import Config
from src.brain.core.models import (
    TodoItem,
    Plan,
    Action,
    Attention,
    EnhancedJSONEncoder,
)

QUEUES_FILE = Config.DATA_DIR / "queues.json"


class TodoQueue:
    def __init__(self):
        self._queue: deque[TodoItem] = deque[TodoItem]()

    def push(self, item: TodoItem):
        self._queue.append(item)

    def pop(self) -> TodoItem:
        return self._queue.popleft()

    def drain(self) -> List[TodoItem]:
        items = list(self._queue)
        self._queue.clear()
        return items

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def size(self) -> int:
        return len(self._queue)


class PlanQueue:
    def __init__(self):
        self._heap: List[Plan] = []

    def push(self, plan: Plan):
        heapq.heappush(self._heap, plan)

    def pop_highest(self) -> Optional[Plan]:
        if self.is_empty():
            return None
        return heapq.heappop(self._heap)

    def pop_lowest(self) -> Optional[Plan]:
        if self.is_empty():
            return None
        # `Plan.__lt__` makes `heapq.heappop` return the highest priority.
        # To get the lowest priority, we find the minimum priority element, remove it, and heapify.
        lowest = min(self._heap, key=lambda p: p.priority)
        self._heap.remove(lowest)
        heapq.heapify(self._heap)
        return lowest

    def find_by_intent(
        self, intent: str, group_key: str | None = None
    ) -> Optional[Plan]:
        for plan in self._heap:
            if plan.intent == intent and plan.group_key == group_key:
                return plan
        return None

    def update(self, plan: Plan):
        # Update priority might change order, so re-heapify
        heapq.heapify(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def size(self) -> int:
        return len(self._heap)

    def items(self) -> List[Plan]:
        return list(self._heap)


class ActionQueue:
    def __init__(self, actions: List[Action] = None):
        self._queue: deque[Action] = deque(actions or [])

    def push(self, action: Action):
        self._queue.append(action)

    def pop(self) -> Optional[Action]:
        if self.is_empty():
            return None
        return self._queue.popleft()

    def peek(self) -> Optional[Action]:
        if self.is_empty():
            return None
        return self._queue[0]

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def size(self) -> int:
        return len(self._queue)

    def replace(self, actions: List[Action]):
        self._queue = deque(actions)

    def clear(self):
        self._queue.clear()


class Queues:
    def __init__(self):
        self.todo_queue = TodoQueue()
        self.plan_queue = PlanQueue()
        self.action_queue = ActionQueue()
        self.current_attention: Optional[Attention] = None

    def save(self):
        QUEUES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "todo_queue": [item.to_dict() for item in self.todo_queue._queue],
            "plan_queue": [plan.to_dict() for plan in self.plan_queue._heap],
            "action_queue": [action.to_dict() for action in self.action_queue._queue],
            "current_attention": (
                self.current_attention.to_dict() if self.current_attention else None
            ),
        }
        with open(QUEUES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=EnhancedJSONEncoder)

    @classmethod
    def load(cls) -> "Queues":
        instance = cls()
        if QUEUES_FILE.exists():
            try:
                with open(QUEUES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, dict):
                    raise ValueError("queues.json root must be an object")

                if not data:
                    return instance

                if "todo_queue" in data:
                    for item_data in data["todo_queue"]:
                        instance.todo_queue.push(TodoItem.from_dict(item_data))

                if "plan_queue" in data:
                    for plan_data in data["plan_queue"]:
                        instance.plan_queue.push(Plan.from_dict(plan_data))

                if "action_queue" in data:
                    actions = [
                        Action.from_dict(action_data)
                        for action_data in data["action_queue"]
                    ]
                    instance.action_queue.replace(actions)

                if data.get("current_attention"):
                    instance.current_attention = Attention.from_dict(
                        data["current_attention"]
                    )

            except Exception as e:
                import logging

                logging.getLogger("polaris").error(f"Failed to load queues.json: {e}")
        return instance
