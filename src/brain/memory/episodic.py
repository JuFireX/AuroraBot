import json
from pathlib import Path
from typing import List, Dict, Any

from src.brain.memory.base import MemoryItem
from src.config import Config

class EpisodicMemory:
    """L2 缓存：情景记忆。
    记录按时间线发生的所有事件，相当于一个带有时间戳的 Log 库。
    主要解决：提供系统运行和用户交互的历史回溯能力。
    """
    def __init__(self):
        # 复用项目现有的数据目录规范，将情景记忆持久化为 JSON 文件
        self._file_path = Config.MEMORY_DATA_DIR / "episodes.json"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def record_event(self, event_type: str, content: str, user_id: str) -> None:
        """写策略：追加写入 (Append Only)
        记录发生过的一件事（例如：用户提问、闹钟触发、计划执行完成）。
        """
        # 利用基类生成带时间戳的记录
        item = MemoryItem(content=content, metadata={"type": event_type, "user_id": user_id})
        
        records = self._load()
        records.append({
            "timestamp": item.timestamp,
            "type": event_type,
            "user_id": user_id,
            "content": content
        })
        self._save(records)

    def search_recent_events(self, limit: int = 5, user_id: str = None) -> List[str]:
        """读策略：按时间倒序截取 (Time-based retrieval)
        查询最近发生的事情，通常作为上下文补充给 LLM，帮助它理解当前所处的阶段。
        """
        records = self._load()
        if user_id:
            records = [r for r in records if r.get("user_id") == user_id]
        
        recent = records[-limit:]
        return [f"[{r['timestamp']}] {r['type']}: {r['content']}" for r in recent]

    def _load(self) -> List[Dict[str, Any]]:
        """辅助方法：从文件加载数据"""
        if not self._file_path.exists():
            return []
        try:
            return json.loads(self._file_path.read_text(encoding="utf-8"))
        except Exception:
            # 如果文件损坏，这里简单处理返回空列表，实际工程中可能需要备份和恢复机制
            return []

    def _save(self, data: List[Dict[str, Any]]) -> None:
        """辅助方法：将数据写回文件"""
        self._file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")