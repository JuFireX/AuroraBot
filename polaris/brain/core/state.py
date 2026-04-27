import json
from dataclasses import dataclass, asdict
from polaris.config import Config

STATE_FILE = Config.DATA_DIR / "state.json"


@dataclass
class State:
    energy_current: float = 100.0
    energy_max: float = 100.0
    energy_regen_per_beat: float = 5.0

    cognitive_load: float = 0.0
    plan_interval: int = 3
    base_plan_interval: int = 3

    busy_threshold: float = 0.6
    idle_trigger_count: int = 10

    idle_counter: int = 0
    heartbeat_count: int = 0

    def regenerate_energy(self):
        self.energy_current = min(
            self.energy_max, self.energy_current + self.energy_regen_per_beat
        )

    def is_idle_mode(self) -> bool:
        return self.idle_counter >= self.idle_trigger_count

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
