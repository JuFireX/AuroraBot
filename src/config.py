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

    ## 回复配置
    REPLY_DEBOUNCE_SECONDS = 2.0
    RECENT_MESSAGE_LIMIT = 6
    MESSAGE_WINDOW = 300
    MESSAGE_PARSE_DEBUG = os.getenv("MESSAGE_PARSE_DEBUG", "0") == "1"
    AI_QUERY_DEBUG = os.getenv("AI_QUERY_DEBUG", "0") == "1"

    # 系统重要目录
    PROJECT_ROOT = PROJECT_ROOT
    LOG_DIR = PROJECT_ROOT / "logs"
    DATA_DIR = PROJECT_ROOT / "data"
    SRC_ROOT = PROJECT_ROOT / "src"

    @staticmethod
    def ensure_dirs():
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.SRC_ROOT.mkdir(parents=True, exist_ok=True)


Config.ensure_dirs()
