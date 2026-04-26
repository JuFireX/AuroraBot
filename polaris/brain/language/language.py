import os
from pathlib import Path
from polaris.config import Config
from polaris.utils.Logger import get_logger


logger = get_logger("LanguageService")
SOUL = Config.PROMPTS_DIR / "SOUL.md"


class LanguageService:
    def __init__(self):
        self.SOUL = self._load_soul()

    def _load_soul(self) -> str:
        logger.info("加载灵魂文档...")
        with open(SOUL, "r", encoding="utf-8") as f:
            content = f.read()
            return content

    async def organize_reply(self) -> str:
        """组织完整回复"""
        # TODO 根据灵魂文档和由记忆服务拼接的上下文，调用统一的模型服务组织回复内容(文本)
        pass


# 单例模式
language_service = LanguageService()
