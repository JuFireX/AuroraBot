from dotenv import load_dotenv
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

if Path(PROJECT_ROOT / ".env.dev").exists():
    load_dotenv(PROJECT_ROOT / ".env.dev")


class Config:
    # 模型配置
    URL_BASE: str = os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    MODEL: str = os.getenv("MODEL", "deepseek/deepseek-v4-flash")

    # 服务配置
    ENABLE_QQ_SERVICE: bool = True
    ENABLE_ALARM_SERVICE: bool = False

    # 系统重要目录
    PROJECT_ROOT = PROJECT_ROOT
    LOG_DIR = PROJECT_ROOT / "logs"

    # Bot 重要目录
    POLARIS_ROOT = PROJECT_ROOT / "polaris"
    POLARIS_BRAIN = POLARIS_ROOT / "brain"
    TOOL_SERVICES = POLARIS_ROOT / "services"

    PROMPTS_DIR = POLARIS_BRAIN / "prompts"
    DATA_DIR = POLARIS_BRAIN / "data"

    # PAA 调度参数
    HEARTBEAT_INTERVAL_SECONDS: float = 3.0
    ENERGY_MAX: float = 1024
    ENERGY_REGEN_PER_BEAT: float = 1
    BASE_PLAN_INTERVAL: int = 3
    BUSY_THRESHOLD: float = 0.6
    IDLE_TRIGGER_COUNT: int = 10
    SELF_MAINTENANCE_INTERVAL: int = 50
    MAX_ACTIONS_PER_BEAT: int = 10
    ACTIVITY_WINDOW_SIZE: int = 10
    GENTLE_IGNORE_CHANCE: float = 0.5
    QQ_HISTORY_LIMIT: int = 20
    QQ_MODEL_CONTEXT_LIMIT: int = 12
    AI_CONTEXT_CHAR_LIMIT: int = 5000
    QQ_REPLY_CHAR_LIMIT: int = 60
    ALARM_LOOP_INTERVAL_SECONDS: float = 1.0
    ALARM_DEFAULT_INTERVAL_SECONDS: int = 1800

    ACTION_ENERGY_COSTS = {
        "qq_recall_memory": 2.0,
        "qq_generate_response": 15.0,
        "qq_send_msg": 5.0,
        "qq_update_memory": 2.0,
        "evaluate_ignore": 1.0,
        "alert_user": 5.0,
        "finalize_alarm": 1.0,
        "organize_memory": 10.0,
        "summarize": 15.0,
        "log_action": 5.0,
    }

    TODO_TO_INTENT = {
        "read_qq_msg": "handle_qq_messages",
        "alarm_reminder": "alarm_reminder",
        "self_maintenance": "self_maintenance",
    }

    @staticmethod
    def action_energy_cost(action_type: str, default: float = 5.0) -> float:
        return Config.ACTION_ENERGY_COSTS.get(action_type, default)

    @staticmethod
    def resolve_intent(todo_type: str) -> str:
        return Config.TODO_TO_INTENT.get(todo_type, todo_type)

    @staticmethod
    def ensure_dirs():
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        Config.POLARIS_BRAIN.mkdir(parents=True, exist_ok=True)
        Config.TOOL_SERVICES.mkdir(parents=True, exist_ok=True)
        Config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)


Config.ensure_dirs()
