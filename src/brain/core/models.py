from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Urgency(str, Enum):
    GENTLE = "gentle"
    NORMAL = "normal"
    URGENT = "urgent"


class TodoStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    DROPPED = "dropped"


class PlanStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AttentionState(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class EpisodeStatus(str, Enum):
    PENDING = "pending"
    CLOSED = "closed"


@dataclass(slots=True)
class TodoItem:
    id: str
    type: str
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    status: TodoStatus = TodoStatus.PENDING
    claimed_by_plan_id: str | None = None
    created_at: float = 0.0
    last_seen_at: float = 0.0


@dataclass(slots=True)
class Plan:
    id: str
    intent: str
    summary: str
    session_id: str
    priority: float
    base_priority: float
    status: PlanStatus = PlanStatus.PENDING
    source_todo_ids: list[str] = field(default_factory=list)
    related_episodes: list[str] = field(default_factory=list)
    attention_count: int = 0
    expand_fail_count: int = 0
    last_expanded_at: float = 0.0
    last_error: str = ""
    created_at: float = 0.0
    last_touched_at: float = 0.0


@dataclass(slots=True)
class Attention:
    id: str
    plan_id: str
    intent: str
    priority: float
    action_ids: list[str] = field(default_factory=list)
    source_todo_ids: list[str] = field(default_factory=list)
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    started_at: float = 0.0
    last_advanced_at: float = 0.0


@dataclass(slots=True)
class Action:
    id: str
    plan_id: str
    capability_name: str
    params: dict[str, Any]
    order: int = 0
    status: ActionStatus = ActionStatus.PENDING
    result_summary: str = ""
    error_message: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass(slots=True)
class Episode:
    id: str
    summary: str
    participants: list[str]
    status: EpisodeStatus = EpisodeStatus.PENDING
    pending_on: str | None = None
    created_at: float = 0.0
    closed_at: float | None = None
