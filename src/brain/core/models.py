from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Urgency(str, Enum):
    GENTLE = "gentle"
    NORMAL = "normal"
    URGENT = "urgent"


class AttentionState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EpisodeStatus(str, Enum):
    PENDING = "pending"
    CLOSED = "closed"


@dataclass(slots=True)
class TodoItem:
    id: str
    type: str
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    created_at: float = 0.0


@dataclass(slots=True)
class Plan:
    id: str
    intent: str
    sub_items: list[TodoItem]
    priority: float
    base_priority: float
    related_episodes: list[str] = field(default_factory=list)
    created_at: float = 0.0
    last_touched_at: float = 0.0


@dataclass(slots=True)
class Action:
    id: str
    capability_name: str
    params: dict[str, Any]


@dataclass(slots=True)
class Attention:
    plan_id: str
    intent: str
    priority: float
    action_count: int
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = 0.0


@dataclass(slots=True)
class Episode:
    id: str
    summary: str
    participants: list[str]
    status: EpisodeStatus = EpisodeStatus.PENDING
    pending_on: str | None = None
    created_at: float = 0.0
    closed_at: float | None = None
