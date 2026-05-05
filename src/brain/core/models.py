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


@dataclass
class TodoItem:
    id: str
    type: str  # 用于 Plan 阶段分组合并
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    created_at: float = 0.0  # unix timestamp
    suggested_window: dict | None = None  # 柔性提醒时间窗口


@dataclass
class Plan:
    id: str
    intent: str  # 决定 Attention 阶段如何展开
    sub_items: list[TodoItem]
    priority: float
    base_priority: float
    related_episodes: list[str] = field(default_factory=list)
    weight: float = 1.0
    created_at: float = 0.0
    last_touched_at: float = 0.0


@dataclass
class Action:
    id: str
    tool_name: str  # 对应 tool_registry 中的注册名
    params: dict[str, Any]
    energy_cost: float = 1.0
    preconditions: list = field(default_factory=list)


@dataclass
class Attention:
    plan_id: str
    intent: str
    priority: float
    total_energy_estimate: float
    action_count: int  # 展开时的动作总数
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = 0.0


@dataclass
class Episode:
    id: str
    summary: str
    participants: list[str]
    status: EpisodeStatus = EpisodeStatus.PENDING
    pending_on: str | None = None
    notify: str | None = None
    created_at: float = 0.0
    closed_at: float | None = None
