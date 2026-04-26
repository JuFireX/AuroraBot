import os
from pathlib import Path
from polaris.config import Config
from polaris.utils.Logger import get_logger
from polaris.brain.model.ModelService import get_format_response

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

    async def organize_reply(self, context: str, trigger_event: str) -> str:
        """组织完整回复"""
        query = f"【灵魂设定】\n{self.SOUL}\n\n【历史上下文】\n{context}\n\n【当前事件/对方说的话】\n{trigger_event}\n\n请直接生成你的回复内容。"
        format_req = '{"reply": "回复的具体内容(纯文本)"}'
        
        response = await get_format_response(query, format_req)
        reply = response.get("reply", "")
        if not reply:
            logger.warning("模型返回的 JSON 中没有 reply 字段或为空")
            reply = "..."
        return reply


# 单例模式
language_service = LanguageService()
