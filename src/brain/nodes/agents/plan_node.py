from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.brain.kernel.base import (
    Agent,
    FileDescriptor,
    FilePattern,
    FileUpdate,
    NodeState,
)
from src.brain.kernel.state_store import next_record_id, parse_llm_json
from src.config import Config
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

logger = get_logger("PlanAgent")

_DATA_DIR = Config.KERNEL_DATA_DIR

_PLAN_SYSTEM_PROMPT = """\
你是 AuroraBot 的规划节点。根据外部事件生成结构化的行动计划。

你会收到一个 JSON 事件对象，包含 type、source、session_id、summary、payload 等字段。

输出严格 JSON：
{
  "goal": "清晰可执行的目标描述",
  "reasoning": "为什么做出这个规划（一句话）",
  "priority": 50,
  "suggested_actions": 1
}

规则：
- goal 要具体可执行，不能是泛泛的"处理事件"
- 用户消息事件：goal 应回应用户意图
- 系统提醒事件（alarm_reminder、diary_prompt）：判断是否需要行动
- 无意义或噪音事件：priority 设为 0，goal 说明跳过原因
- priority 参考：紧急/用户直接相关 80+，普通事件 50，低优先级后台任务 20-，跳过 0
- suggested_actions：建议展开为几个命令，通常 1-3
"""


class PlanNode(Agent):
    """从外部事件生成计划的 Agent 节点。

    守护 ``inbox/event_*.json`` 文件，当新的外部事件到达时，
    调用 LLM 理解事件意图并生成 plan 记录，
    写入 ``plans/plan_<id>.json``。

    LLM 不可用或输出不可解析时回退到机械规划。
    已处理的 inbox 文件在计划写入后删除。
    """

    def __init__(self, node_id: str) -> None:
        super().__init__(node_id, system_prompt=_PLAN_SYSTEM_PROMPT)
        self._plans_dir = _DATA_DIR / "plans"
        self._inbox_dir = _DATA_DIR / "inbox"

    @property
    def type(self) -> str:
        return "agent"

    @property
    def guards(self) -> list[FilePattern]:
        if self._config_watch is not None:
            return [FilePattern(p) for p in self._config_watch]
        return [FilePattern("inbox/event_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        if self._config_emit is not None:
            return [FileDescriptor(p) for p in self._config_emit]
        return [FileDescriptor("plans/plan.json")]

    async def execute(self) -> list[FileUpdate]:
        """扫描 inbox 事件文件，调用 LLM 生成 plan。"""
        if not self._inbox_dir.exists():
            return []

        event_files = sorted(self._inbox_dir.glob("event_*.json"))
        if not event_files:
            return []

        self._plans_dir.mkdir(parents=True, exist_ok=True)
        plan_updates: list[FileUpdate] = []

        for event_file in event_files:
            try:
                event_data = self._read_event(event_file)
                if event_data is None:
                    self._safe_unlink(event_file)
                    continue

                event_id = event_data.get("id", "")
                if not event_id:
                    self._safe_unlink(event_file)
                    continue

                plan_path = self._plans_dir / f"plan_{event_id}.json"
                if plan_path.exists():
                    self._safe_unlink(event_file)
                    continue

                plan = await self._generate_plan(event_data)
                if plan is None:
                    continue

                plan_updates.append(
                    FileUpdate(
                        descriptor=FileDescriptor(
                            path=f"plans/plan_{event_id}.json",
                            schema="json",
                        ),
                        content=plan,
                    )
                )
                self._safe_unlink(event_file)

            except Exception:
                logger.exception(f"PlanAgent 处理事件文件失败: {event_file.name}")

        return plan_updates

    async def _generate_plan(self, event_data: dict[str, Any]) -> dict[str, Any] | None:
        """调用 LLM 理解事件意图并生成计划。"""
        event_json = json.dumps(event_data, indent=2, ensure_ascii=False)
        user_msg = f"事件:\n{event_json}\n\n请为这个事件生成计划。"
        messages = [{"role": "user", "content": user_msg}]

        try:
            raw = await self.think(messages, max_tokens=512)
        except Exception:
            logger.exception("PlanAgent LLM 调用失败，回退到机械规划")
            return self._fallback_plan(event_data)

        parsed = parse_llm_json(raw)
        if parsed is None:
            logger.warning(f"PlanAgent LLM 输出不可解析，回退到机械规划: {raw!r}")
            return self._fallback_plan(event_data)

        return self._build_plan(event_data, parsed)

    def _build_plan(
        self, event_data: dict[str, Any], llm_output: dict[str, Any]
    ) -> dict[str, Any]:
        timestamp = now_text()
        return {
            "id": next_record_id("plan"),
            "source_event_id": event_data.get("id", ""),
            "source_event_type": str(event_data.get("type", "unknown")),
            "source": str(event_data.get("source", "")),
            "session_id": str(event_data.get("session_id", "")),
            "goal": str(llm_output.get("goal", "")),
            "reasoning": str(llm_output.get("reasoning", "")),
            "summary": str(event_data.get("summary", "")),
            "payload": event_data.get("payload", {}),
            "status": "pending",
            "priority": int(llm_output.get("priority", 50)),
            "suggested_actions": int(llm_output.get("suggested_actions", 1)),
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def _fallback_plan(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """LLM 不可用时的机械回退。"""
        timestamp = now_text()
        event_type = str(event_data.get("type", "unknown"))
        summary = str(event_data.get("summary", "") or "")
        return {
            "id": next_record_id("plan"),
            "source_event_id": event_data.get("id", ""),
            "source_event_type": event_type,
            "source": str(event_data.get("source", "")),
            "session_id": str(event_data.get("session_id", "")),
            "goal": summary or f"处理事件 {event_type}",
            "reasoning": "LLM 不可用，使用机械回退",
            "summary": summary,
            "payload": event_data.get("payload", {}),
            "status": "pending",
            "priority": 50,
            "suggested_actions": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    @staticmethod
    def _read_event(path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"读取事件文件失败 {path}: {exc}")
            return None

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"删除文件失败 {path}: {exc}")

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
