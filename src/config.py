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
    APP_DATA_DIR = DATA_DIR / "app_data"
    PROMPTS_DIR = SRC_ROOT / "brain" / "prompts"
    QUEUES_DATA_DIR = DATA_DIR / "queues"
    MEMORY_DATA_DIR = DATA_DIR / "memory"
    QUEUES_SNAPSHOT_FILE = QUEUES_DATA_DIR / "runtime_queues.json"
    EPISODIC_MEMORY_FILE = MEMORY_DATA_DIR / "episodes.json"
    SEMANTIC_MEMORY_FILE = MEMORY_DATA_DIR / "semantic_memory.json"
    SEMANTIC_SNAPSHOT_FILE = MEMORY_DATA_DIR / "semantic_snapshot.txt"

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RUN_MODE: str = os.getenv("RUN_MODE", "core")
    HEARTBEAT_INTERVAL: float = float(os.getenv("HEARTBEAT_INTERVAL", "1.0"))
    MAX_ACTIONS_PER_BEAT: int = int(os.getenv("MAX_ACTIONS_PER_BEAT", "50"))
    SELF_MAINTENANCE_INTERVAL: int = int(os.getenv("SELF_MAINTENANCE_INTERVAL", "12"))
    QUEUES_RESTORE_ON_START: bool = _get_bool("QUEUES_RESTORE_ON_START", True)

    ENABLE_QQ_SERVICE: bool = _get_bool("ENABLE_QQ_SERVICE", True)
    ENABLE_ALARM_SERVICE: bool = _get_bool("ENABLE_ALARM_SERVICE", True)
    ENABLE_DIARY_SERVICE: bool = _get_bool("ENABLE_DIARY_SERVICE", True)
    ENABLE_MCP_CONTAINER: bool = _get_bool("ENABLE_MCP_CONTAINER", False)

    MODEL: str = os.getenv("MODEL", "deepseek/deepseek-v4-flash")
    AI_CONTEXT_CHAR_LIMIT: int = int(os.getenv("AI_CONTEXT_CHAR_LIMIT", "6000"))
    MEM0_API_KEY: str = os.getenv("MEM0_API_KEY", "m0-xxx")
    MEM0_API_BASE_URL: str = os.getenv("MEM0_API_BASE_URL", "https://api.mem0.ai")

    SESSION_MAX_TOKENS: int = int(os.getenv("SESSION_MAX_TOKENS", "4000"))
    QQ_REPLY_CHAR_LIMIT: int = int(os.getenv("QQ_REPLY_CHAR_LIMIT", "120"))
    QQ_HISTORY_LIMIT: int = int(os.getenv("QQ_HISTORY_LIMIT", "50"))
    ALARM_DEFAULT_INTERVAL_SECONDS: int = int(
        os.getenv("ALARM_DEFAULT_INTERVAL_SECONDS", "1800")
    )
    DIARY_TIME: str = os.getenv("DIARY_TIME", "22:00")
    SNAPSHOT_REFRESH_INTERVAL: int = int(
        os.getenv("SNAPSHOT_REFRESH_INTERVAL", "86400")
    )
    SNAPSHOT_REFRESH_DEBOUNCE_SECONDS: float = float(
        os.getenv("SNAPSHOT_REFRESH_DEBOUNCE_SECONDS", "3.0")
    )

    @staticmethod
    def ensure_dirs() -> None:
        for path in (
            Config.LOG_DIR,
            Config.DATA_DIR,
            Config.APP_DATA_DIR,
            Config.SRC_ROOT,
            Config.PROMPTS_DIR,
            Config.QUEUES_DATA_DIR,
            Config.MEMORY_DATA_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


Config.ensure_dirs()
