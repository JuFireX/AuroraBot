from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class BotState:
    heartbeat_count: int = 0
    _recent_activity: deque[int] = field(default_factory=lambda: deque(maxlen=20))
    _event_intervals: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    _last_event_at: float = 0.0

    def reset(self) -> None:
        self.heartbeat_count = 0
        self._recent_activity.clear()
        self._event_intervals.clear()
        self._last_event_at = 0.0

    def record_tick(self, had_events: bool) -> None:
        self._recent_activity.append(1 if had_events else 0)
        if had_events:
            now = time.time()
            if self._last_event_at > 0:
                self._event_intervals.append(now - self._last_event_at)
            self._last_event_at = now

    @property
    def activity_rate(self) -> float:
        if not self._recent_activity:
            return 0.0
        return sum(self._recent_activity) / len(self._recent_activity)

    @property
    def activity_variability(self) -> float:
        if len(self._event_intervals) < 2:
            return 0.0
        intervals = list(self._event_intervals)
        mean = sum(intervals) / len(intervals)
        if mean <= 0:
            return 0.0
        variance = sum((item - mean) ** 2 for item in intervals) / len(intervals)
        return (variance**0.5) / mean

    def is_idle(self) -> bool:
        return self.activity_rate < 0.2 and self.activity_variability < 0.3

    def is_stressed(self) -> bool:
        return self.activity_rate > 0.8 and self.activity_variability < 0.3

    def is_in_flow(self) -> bool:
        return 0.4 < self.activity_rate < 0.8 and self.activity_variability > 0.5


bot_state = BotState()
