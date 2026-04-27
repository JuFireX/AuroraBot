import json
from collections import deque
from dataclasses import asdict, dataclass, field
from polaris.config import Config

STATE_FILE = Config.DATA_DIR / "state.json"


@dataclass
class State:
    energy_current: float = Config.ENERGY_MAX
    energy_max: float = Config.ENERGY_MAX
    energy_regen_per_beat: float = Config.ENERGY_REGEN_PER_BEAT

    cognitive_load: float = 0.0
    activity_index: float = 0.0
    plan_interval: int = Config.BASE_PLAN_INTERVAL
    base_plan_interval: int = Config.BASE_PLAN_INTERVAL

    busy_threshold: float = Config.BUSY_THRESHOLD
    idle_trigger_count: int = Config.IDLE_TRIGGER_COUNT

    idle_counter: int = 0
    heartbeat_count: int = 0
    activity_window: list[int] = field(default_factory=list)

    def regenerate_energy(self):
        self.energy_current = min(
            self.energy_max, self.energy_current + self.energy_regen_per_beat
        )

    def record_activity(self, has_todo: bool):
        window = deque(self.activity_window, maxlen=Config.ACTIVITY_WINDOW_SIZE)
        window.append(1 if has_todo else 0)
        self.activity_window = list(window)
        self.activity_index = (
            sum(self.activity_window) / len(self.activity_window)
            if self.activity_window
            else 0.0
        )
        self.cognitive_load = self.activity_index

    def refresh_plan_interval(self, backlog_size: int, has_active_attention: bool):
        if backlog_size > 5:
            self.plan_interval = 1
            return

        if self.activity_index >= self.busy_threshold:
            self.plan_interval = 1 if backlog_size > 0 else max(1, self.base_plan_interval)
            return

        if self.is_idle_mode() and not has_active_attention:
            self.plan_interval = max(self.base_plan_interval, self.base_plan_interval + 1)
            return

        self.plan_interval = self.base_plan_interval

    def is_idle_mode(self) -> bool:
        return (
            self.idle_counter >= self.idle_trigger_count
            and self.activity_index < self.busy_threshold
        )

    def save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> "State":
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                import logging

                logging.getLogger("polaris").error(f"Failed to load state.json: {e}")
        return cls()
