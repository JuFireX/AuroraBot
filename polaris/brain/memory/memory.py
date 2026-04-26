import json
import asyncio
from datetime import datetime
from polaris.config import Config
from polaris.utils.Logger import get_logger

logger = get_logger("MemoryService")
MEMORY_DB = Config.POLARIS_BRAIN / "memory" / "database"
MAX_MEMORY_RECALLS = 50


class MemoryService:
    def __init__(self):
        # 记忆数据库目录
        MEMORY_DB.mkdir(parents=True, exist_ok=True)

    def _get_db_file(self):
        # 根据当天日期生成文件名，例如 2026-04-26.json
        today = datetime.now().strftime("%Y-%m-%d")
        db_file = MEMORY_DB / f"{today}.json"
        if not db_file.exists() or db_file.stat().st_size == 0:
            with open(db_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        return db_file

    async def record(self, role: str, content: str, metadata: dict = None):
        """记录一条记忆"""
        db_file = self._get_db_file()
        record_item = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        try:
            with open(db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

        data.append(record_item)

        with open(db_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def recall(self, limit: int = MAX_MEMORY_RECALLS) -> str:
        """提取拼接记忆上下文"""
        db_file = self._get_db_file()
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

        recent = data[-limit:] if limit > 0 else data
        context_lines = []
        for item in recent:
            role = item.get("role", "unknown")
            content = item.get("content", "")
            time_str = item.get("time", "")
            context_lines.append(f"[{time_str}] {role}: {content}")

        return "\n".join(context_lines)

    async def summarize(self) -> str:
        """总结记忆"""
        # 待实现更高级的总结逻辑
        pass

    async def forget(self):
        """遗忘当天的所有记忆（或执行截断操作）"""
        db_file = self._get_db_file()
        with open(db_file, "w", encoding="utf-8") as f:
            json.dump([], f)


# 全局单例
memory_service = MemoryService()
