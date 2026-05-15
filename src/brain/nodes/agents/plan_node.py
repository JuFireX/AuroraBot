from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.brain.kernel.base import (
    FileDescriptor,
    FilePattern,
    FileUpdate,
    Node,
    NodeState,
)
from src.brain.kernel.state_store import next_record_id
from src.config import Config
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

logger = get_logger("PlanNode")

_DATA_DIR = Config.KERNEL_DATA_DIR


class PlanNode(Node):
    """从外部事件生成计划的节点。

    守护 ``inbox/event_*.json`` 文件，当新的外部事件到达时，
    读取事件内容，生成 plan 记录并写入 ``plans/plan_<id>.json``。

    每个事件对应一个独立的 plan 文件，避免多节点并发写入同一文件时的竞态。
    已处理的 inbox 文件会在计划写入后删除。

    Old → New 对应
    --------------
    - 旧 PlanAgent.propose() + step() → execute()
    - 旧 host.drain_events() → 读取 inbox 文件
    - 旧 append 到 plans.json → 每个 plan 独立文件
    """

    def __init__(self, node_id: str) -> None:
        super().__init__(node_id)
        self._plans_dir = _DATA_DIR / "plans"
        self._inbox_dir = _DATA_DIR / "inbox"

    @property
    def type(self) -> str:
        return "router"  # 纯数据转换，不调用 LLM

    @property
    def guards(self) -> list[FilePattern]:
        return [FilePattern("inbox/event_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        return [FileDescriptor("plans/plan.json")]

    async def execute(self) -> list[FileUpdate]:
        """扫描 inbox 事件文件，生成 plan 文件。"""
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
                    continue

                # 检查是否已有对应的 plan（防重入）
                event_id = event_data.get("id", "")
                if not event_id:
                    continue
                plan_path = self._plans_dir / f"plan_{event_id}.json"
                if plan_path.exists():
                    # 已处理过，清理 inbox 文件
                    self._safe_unlink(event_file)
                    continue

                plan = self._build_plan(event_data)

                # 写 plan 文件
                plan_updates.append(
                    FileUpdate(
                        descriptor=FileDescriptor(
                            path=f"plans/plan_{event_id}.json",
                            schema="json",
                        ),
                        content=plan,
                    )
                )

                # 删除已处理的 inbox 文件
                self._safe_unlink(event_file)

            except Exception:  # noqa: BLE001
                logger.exception(f"PlanNode 处理事件文件失败: {event_file.name}")

        return plan_updates

    def _read_event(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"读取事件文件失败 {path}: {exc}")
            return None

    def _build_plan(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """从旧 PlanAgent._build_plan 移植。"""
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
            "summary": summary,
            "payload": event_data.get("payload", {}),
            "status": "pending",
            "priority": 50,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"删除文件失败 {path}: {exc}")

    def on_complete(self) -> None:
        """执行完后保持 IDLE。"""
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
