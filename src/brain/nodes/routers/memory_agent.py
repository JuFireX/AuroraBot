from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.brain.kernel.base import (
    FileDescriptor,
    FilePattern,
    FileUpdate,
    NodeState,
    Router,
)
from src.brain.kernel.state_store import next_record_id
from src.config import Config
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

logger = get_logger("MemoryAgent")

_DATA_DIR = Config.KERNEL_DATA_DIR


class MemoryAgent(Router):
    """简单事实记忆 Router —— 从 plan 和 action 中提取结构化事实。

    纯机械逻辑，零 LLM 调用。后续由 mem0 集成替换。

    守护 ``plans/plan_*.json`` 和 ``actions/action_*.json``。
    扫描已完成（status=done）的记录，提取关键字段，
    追加写入 ``memory/facts.json``。每条记录处理一次（通过
    ``processed_at`` 标记避免重复）。

    提供静态辅助函数 ``lookup_facts(session_id)`` 供其他 Agent
    检索用户相关记忆。
    """

    def __init__(self, node_id: str, **config: Any) -> None:
        super().__init__(node_id)
        self._memory_dir = _DATA_DIR / "memory"
        self._plans_dir = _DATA_DIR / "plans"
        self._actions_dir = _DATA_DIR / "actions"
        self._facts_path = self._memory_dir / "facts.json"

    @property
    def type(self) -> str:
        return "router"

    @property
    def guards(self) -> list[FilePattern]:
        return [
            FilePattern("plans/plan_*.json"),
            FilePattern("actions/action_*.json"),
        ]

    @property
    def produces(self) -> list[FileDescriptor]:
        return [FileDescriptor("memory/facts.json")]

    async def execute(self) -> list[FileUpdate]:
        new_facts: list[dict[str, Any]] = []

        # 从 plan 提取
        if self._plans_dir.exists():
            for plan_path in sorted(self._plans_dir.glob("plan_*.json")):
                fact = self._extract_plan_fact(plan_path)
                if fact:
                    new_facts.append(fact)

        # 从 action 提取
        if self._actions_dir.exists():
            for action_path in sorted(self._actions_dir.glob("action_*.json")):
                fact = self._extract_action_fact(action_path)
                if fact:
                    new_facts.append(fact)

        if not new_facts:
            return []

        # 追加写入（与现有事实去重）
        existing = self._load_facts()
        existing_ids = {f.get("id", "") for f in existing}
        added = 0
        for fact in new_facts:
            if fact["id"] not in existing_ids:
                existing.append(fact)
                existing_ids.add(fact["id"])
                added += 1

        if added == 0:
            return []

        self._memory_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"MemoryAgent: 新增 {added} 条事实")

        return [
            FileUpdate(
                descriptor=FileDescriptor(
                    path="memory/facts.json",
                    schema="json",
                ),
                content=existing,
            )
        ]

    def _extract_plan_fact(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            if data.get("status") != "done":
                return None
            # 避免重复提取
            if data.get("memory_processed"):
                return None
        except (OSError, json.JSONDecodeError):
            return None

        # 标记已处理
        data["memory_processed"] = True
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

        return {
            "id": f"fact_plan_{data.get('id', next_record_id('fact'))}",
            "type": "plan",
            "session_id": str(data.get("session_id", "")),
            "source": str(data.get("source", "")),
            "source_event_type": str(data.get("source_event_type", "")),
            "goal": str(data.get("goal", "")),
            "summary": str(data.get("summary", "")),
            "created_at": data.get("created_at", now_text()),
        }

    def _extract_action_fact(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            if data.get("status") != "done":
                return None
            if data.get("memory_processed"):
                return None
        except (OSError, json.JSONDecodeError):
            return None

        # 标记已处理
        data["memory_processed"] = True
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

        kwargs = data.get("kwargs", {})
        result = data.get("result", {})

        return {
            "id": f"fact_action_{data.get('id', next_record_id('fact'))}",
            "type": "action",
            "command": str(data.get("command", "")),
            "kwargs_summary": str(kwargs)[:200] if kwargs else "",
            "result_summary": str(result)[:200] if result else "",
            "plan_id": str(data.get("plan_id", "")),
            "reasoning": str(data.get("reasoning", "")),
            "created_at": data.get("created_at", now_text()),
        }

    def _load_facts(self) -> list[dict[str, Any]]:
        if not self._facts_path.exists():
            return []
        try:
            data = json.loads(self._facts_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def lookup_facts(
        session_id: str | None = None,
        *,
        fact_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """静态辅助函数 —— 检索记忆事实。

        可供 PlanAgent / GoalGeneratorAgent 在运行时调用，
        获取用户相关历史。

        Parameters
        ----------
        session_id : str | None
            按 session_id 过滤，None 则返回全部。
        fact_type : str | None
            按类型过滤（``"plan"`` / ``"action"``）。
        limit : int
            最大返回条数。

        Returns
        -------
        list[dict[str, Any]]
            匹配的事实记录列表（按时间倒序）。
        """
        facts_path = _DATA_DIR / "memory" / "facts.json"
        if not facts_path.exists():
            return []
        try:
            all_facts = json.loads(facts_path.read_text(encoding="utf-8"))
            if not isinstance(all_facts, list):
                return []
        except (OSError, json.JSONDecodeError):
            return []

        result: list[dict[str, Any]] = []
        for fact in reversed(all_facts):
            if not isinstance(fact, dict):
                continue
            if session_id and str(fact.get("session_id", "")) != session_id:
                continue
            if fact_type and str(fact.get("type", "")) != fact_type:
                continue
            result.append(fact)
            if len(result) >= limit:
                break
        return result

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
