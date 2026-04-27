import uuid
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class Urgency(str, Enum):
    GENTLE = "gentle"
    NORMAL = "normal"
    URGENT = "urgent"


class AttentionState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


@dataclass
class TodoItem:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    urgency: Urgency = Urgency.NORMAL
    group_key: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    suggested_time_window: Optional[Dict[str, float]] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TodoItem":
        if "urgency" in data and isinstance(data["urgency"], str):
            data["urgency"] = Urgency(data["urgency"])
        return cls(**data)


@dataclass
class Plan:
    intent: str
    sub_items: List[TodoItem] = field(default_factory=list)
    group_key: Optional[str] = None
    priority: float = 0.0
    base_priority: float = 0.0
    weight: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_touched_at: float = field(default_factory=time.time)

    def __lt__(self, other: "Plan"):
        # heapq pops smallest first, so we invert priority to make it a max heap
        return self.priority > other.priority

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        if "sub_items" in data:
            data["sub_items"] = [TodoItem.from_dict(item) for item in data["sub_items"]]
        return cls(**data)


@dataclass
class Action:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    energy_cost: float = 0.0
    preconditions: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(**data)


@dataclass
class Attention:
    plan_id: str
    intent: str
    priority: float
    group_key: Optional[str] = None
    total_energy_estimate: float = 0.0
    action_list: List[Action] = field(default_factory=list)
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Attention":
        if "action_list" in data:
            data["action_list"] = [
                Action.from_dict(item) for item in data["action_list"]
            ]
        if "state" in data and isinstance(data["state"], str):
            data["state"] = AttentionState(data["state"])
        return cls(**data)
