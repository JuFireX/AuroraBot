import asyncio
from datetime import datetime
from polaris.utils.Logger import get_logger

logger = get_logger("MemoryService")

class MemoryService:
    def __init__(self):
        # 存储记忆，每条格式为 {"time": iso_string, "role": "user"|"self", "content": str, "metadata": dict}
        self.memories = [] 
        # 设定阈值，超过则触发程序性遗忘
        self.MAX_MEMORIES = 50 

    async def add_memory(self, role: str, content: str, metadata: dict = None):
        """
        向记忆中添加一条新记录
        :param role: 角色，例如 'user' 或 'self'
        :param content: 记忆内容
        :param metadata: 其他元数据（如 user_id, group_id）
        """
        memory = {
            "time": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        self.memories.append(memory)
        logger.debug(f"记忆已刻入: [{role}] {content[:20]}...")
        await self.procedural_forgetting()

    async def recall(self, limit: int = 15) -> str:
        """
        提取最近的记忆作为上下文
        """
        recent = self.memories[-limit:]
        if not recent:
            return "记忆的河流干涸了，一片空白。"
        
        context = []
        for m in recent:
            try:
                time_str = datetime.fromisoformat(m["time"]).strftime("%H:%M:%S")
            except Exception:
                time_str = "未知时间"
            role_display = "我" if m["role"] == "self" else "外部"
            context.append(f"[{time_str}] {role_display}: {m['content']}")
        
        return "\n".join(context)

    async def procedural_forgetting(self):
        """
        程序性遗忘机制。
        人类无法记住所有的对话细节，只能留下印象。
        当前使用简单的截断机制。
        """
        if len(self.memories) > self.MAX_MEMORIES:
            logger.info("记忆池超载，一些遥远的碎语消散了...")
            # 保留最近的记忆
            self.memories = self.memories[-self.MAX_MEMORIES:]

# 全局单例
memory_service = MemoryService()
