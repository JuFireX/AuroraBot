from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from src.config import Config


@dataclass
class BotState:
    energy_current: float = Config.ENERGY_MAX
    energy_max: float = Config.ENERGY_MAX
    energy_regen_per_beat: float = Config.ENERGY_REGEN_PER_BEAT
    cognitive_load: float = 0.0
    plan_interval: int = Config.BASE_PLAN_INTERVAL
    base_plan_interval: int = Config.BASE_PLAN_INTERVAL
    idle_counter: int = 0
    heartbeat_count: int = 0
    busy_threshold: float = Config.BUSY_THRESHOLD
    idle_heartbeats_threshold: int = Config.IDLE_HEARTBEATS_THRESHOLD
    recent_activity: deque[bool] = field(default_factory=lambda: deque(maxlen=10))

    def reset(self) -> None:
        self.energy_current = self.energy_max
        self.cognitive_load = 0.0
        self.plan_interval = self.base_plan_interval
        self.idle_counter = 0
        self.heartbeat_count = 0
        self.recent_activity.clear()

    def regenerate_energy(self) -> None:
        self.energy_current = min(
            self.energy_max,
            self.energy_current + self.energy_regen_per_beat,
        )

    def has_energy(self, cost: float) -> bool:
        return self.energy_current >= cost

    def consume_energy(self, cost: float) -> None:
        self.energy_current = max(0.0, self.energy_current - cost)

    def record_activity(self, had_todos: bool) -> None:
        self.recent_activity.append(had_todos)

    def activity_ratio(self) -> float:
        if not self.recent_activity:
            return 0.0
        active_beats = sum(1 for item in self.recent_activity if item)
        return active_beats / len(self.recent_activity)

    def update_cognitive_load(self, pending_items: int) -> None:
        backlog_factor = min(1.0, pending_items / 10.0)
        activity_factor = self.activity_ratio()
        self.cognitive_load = min(1.0, max(backlog_factor, activity_factor))

    def adjust_plan_interval(self, had_todos: bool) -> None:
        if had_todos:
            self.plan_interval = 1 if self.cognitive_load >= self.busy_threshold else self.base_plan_interval
            return

        self.plan_interval = min(
            self.base_plan_interval * 3,
            self.plan_interval + 1,
        )

    def is_idle(self) -> bool:
        return (
            self.idle_counter >= self.idle_heartbeats_threshold
            and self.cognitive_load < 0.2
        )


bot_state = BotState()
