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

    # 重要目录
    PROJECT_ROOT = PROJECT_ROOT
    LOG_DIR = PROJECT_ROOT / "logs"

    @staticmethod
    def ensure_dirs():
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
