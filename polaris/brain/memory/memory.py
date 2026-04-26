import asyncio
from datetime import datetime
from polaris.config import Config
from polaris.utils.Logger import get_logger

logger = get_logger("MemoryService")
MEMORY_DB = Config.POLARIS_BRAIN / "memory" / "database"
MAX_MEMORY_RECALLS = 50


class MemoryService:
    def __init__(self):
        self.recalls = []

    async def record(self):
        """记录一条记忆"""
        # TODO 向数据库中存一条记忆记录
        pass

    async def recall(self) -> str:
        """提取拼接记忆上下文"""
        # TODO 从数据库中读取最近的记忆, 空间相关的记忆, 时间相关的记忆, 事件相关的记忆, 概念相关的记忆等等
        pass

    async def summarize(self) -> str:
        """总结记忆"""
        # TODO 总结给定的记忆记录列表
        pass

    async def forget(self):
        """遗忘记忆"""
        # TODO 移除给定的记忆记录列表
        pass


# 全局单例
memory_service = MemoryService()
