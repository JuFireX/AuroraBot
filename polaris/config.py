from dotenv import load_dotenv
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

if Path(PROJECT_ROOT / ".env.dev").exists():
    load_dotenv(PROJECT_ROOT / ".env.dev")


class Config:
    URL_BASE: str = os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    MODEL: str = os.getenv("MODEL", "deepseek/deepseek-v4-flash")

    # 系统重要目录
    PROJECT_ROOT = PROJECT_ROOT
    LOG_DIR = PROJECT_ROOT / "logs"

    # Bot 重要目录
    POLARIS_ROOT = PROJECT_ROOT / "polaris"
    POLARIS_BRAIN = POLARIS_ROOT / "brain"
    TOOL_SERVICES = POLARIS_ROOT / "services"

    MEMORY_DIR = POLARIS_BRAIN / "memory"
    PROMPTS_DIR = POLARIS_BRAIN / "prompts"

    @staticmethod
    def ensure_dirs():
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        Config.POLARIS_BRAIN.mkdir(parents=True, exist_ok=True)
        Config.TOOL_SERVICES.mkdir(parents=True, exist_ok=True)
        Config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        Config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
