import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:

    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")
if (PROJECT_ROOT / ".env.dev").exists():
    load_dotenv(PROJECT_ROOT / ".env.dev", override=True)
if (PROJECT_ROOT / ".env.prod").exists():
    load_dotenv(PROJECT_ROOT / ".env.prod", override=False)


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    PROJECT_ROOT = PROJECT_ROOT
    SRC_ROOT = PROJECT_ROOT / "src"
    LOG_DIR = PROJECT_ROOT / "logs"
    DATA_DIR = PROJECT_ROOT / "data"
    PROMPTS_DIR = SRC_ROOT / "brain" / "prompts"
    QQ_DATA_DIR = DATA_DIR / "qq"
    ALARM_DATA_DIR = DATA_DIR / "alarm"
    QUEUES_DATA_DIR = DATA_DIR / "queues"
    QUEUES_SNAPSHOT_FILE = QUEUES_DATA_DIR / "runtime_queues.json"

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RUN_MODE: str = os.getenv("RUN_MODE", "core")
    ENABLE_QQ_SERVICE: bool = _get_bool("ENABLE_QQ_SERVICE", False)
    ENABLE_ALARM_SERVICE: bool = _get_bool("ENABLE_ALARM_SERVICE", False)
    ENABLE_TEST_SERVICE: bool = _get_bool("ENABLE_TEST_SERVICE", False)
    BOOTSTRAP_DEMO_TODOS: bool = _get_bool("BOOTSTRAP_DEMO_TODOS", True)

    HEARTBEAT_INTERVAL: float = float(os.getenv("HEARTBEAT_INTERVAL", "1.0"))
    ENERGY_MAX: float = float(os.getenv("ENERGY_MAX", "24.0"))
    ENERGY_REGEN_PER_BEAT: float = float(os.getenv("ENERGY_REGEN_PER_BEAT", "4.0"))
    BASE_PLAN_INTERVAL: int = int(os.getenv("BASE_PLAN_INTERVAL", "3"))
    IDLE_HEARTBEATS_THRESHOLD: int = int(os.getenv("IDLE_HEARTBEATS_THRESHOLD", "4"))
    BUSY_THRESHOLD: float = float(os.getenv("BUSY_THRESHOLD", "0.6"))
    MAX_ACTIONS_PER_BEAT: int = int(os.getenv("MAX_ACTIONS_PER_BEAT", "4"))
    DEFAULT_ENERGY_COST: float = float(os.getenv("DEFAULT_ENERGY_COST", "2.0"))
    GENTLE_IGNORE_CHANCE: float = float(os.getenv("GENTLE_IGNORE_CHANCE", "0.5"))
    SELF_MAINTENANCE_INTERVAL: int = int(os.getenv("SELF_MAINTENANCE_INTERVAL", "12"))

    TEST_EVENT_INTERVAL_SECONDS: float = float(
        os.getenv("TEST_EVENT_INTERVAL_SECONDS", "2.0")
    )
    TEST_SCENARIO: str = os.getenv("TEST_SCENARIO", "default")
    TEST_SCENARIO_LOOP: bool = _get_bool("TEST_SCENARIO_LOOP", False)
    QUEUES_AUTOSAVE: bool = _get_bool("QUEUES_AUTOSAVE", True)
    QUEUES_RESTORE_ON_START: bool = _get_bool("QUEUES_RESTORE_ON_START", True)

    URL_BASE: str = os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com")
    API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    MODEL: str = os.getenv("MODEL", "deepseek/deepseek-v4-flash")
    AI_CONTEXT_CHAR_LIMIT: int = int(os.getenv("AI_CONTEXT_CHAR_LIMIT", "6000"))

    MEM0_API_KEY: str = os.getenv("MEM0_API_KEY", "m0-xxx")

    REPLY_DEBOUNCE_SECONDS: float = float(os.getenv("REPLY_DEBOUNCE_SECONDS", "2.0"))
    RECENT_MESSAGE_LIMIT: int = int(os.getenv("RECENT_MESSAGE_LIMIT", "6"))
    MESSAGE_WINDOW: int = int(os.getenv("MESSAGE_WINDOW", "300"))
    MESSAGE_PARSE_DEBUG: bool = _get_bool("MESSAGE_PARSE_DEBUG", False)
    AI_QUERY_DEBUG: bool = _get_bool("AI_QUERY_DEBUG", False)
    QQ_MODEL_CONTEXT_LIMIT: int = int(os.getenv("QQ_MODEL_CONTEXT_LIMIT", "12"))
    QQ_REPLY_CHAR_LIMIT: int = int(os.getenv("QQ_REPLY_CHAR_LIMIT", "120"))
    QQ_HISTORY_LIMIT: int = int(os.getenv("QQ_HISTORY_LIMIT", "50"))
    ALARM_LOOP_INTERVAL_SECONDS: float = float(
        os.getenv("ALARM_LOOP_INTERVAL_SECONDS", "1.0")
    )
    ALARM_DEFAULT_INTERVAL_SECONDS: int = int(
        os.getenv("ALARM_DEFAULT_INTERVAL_SECONDS", "1800")
    )

    @staticmethod
    def ensure_dirs() -> None:
        for path in (
            Config.LOG_DIR,
            Config.DATA_DIR,
            Config.SRC_ROOT,
            Config.PROMPTS_DIR,
            Config.QQ_DATA_DIR,
            Config.ALARM_DATA_DIR,
            Config.QUEUES_DATA_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


Config.ensure_dirs()
