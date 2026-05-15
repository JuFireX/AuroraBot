from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.brain.kernel.base import (
    FileDescriptor,
    FilePattern,
    FileUpdate,
    Node,
    NodeState,
)
from src.config import Config
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("ExecuteNode")

_DATA_DIR = Config.KERNEL_DATA_DIR


class ExecuteNode(Node):
    """执行 action 的节点。

    守护 ``actions/action_*.json`` 文件，当新的 action 到达时，
    调用宿主命令执行，并更新 action / plan 的状态。

    Old → New 对应
    --------------
    - 旧 ExecuteAgent.propose() + step() → execute()
    - 旧 load_json_list → 直接读独立 action 文件
    - 旧 host.invoke_command() → 同上
    - 旧 update_*_status → 写回独立 plan / action 文件
    """

    def __init__(
        self,
        node_id: str,
        host: ApplicationHost,  # noqa: F821 — migration shim
    ) -> None:
        super().__init__(node_id)
        self._host = host
        self._actions_dir = _DATA_DIR / "actions"
        self._plans_dir = _DATA_DIR / "plans"

    @property
    def type(self) -> str:
        return "router"  # 调用命令但不调用 LLM

    @property
    def guards(self) -> list[FilePattern]:
        return [FilePattern("actions/action_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        return [
            FileDescriptor("actions/action.json"),
            FileDescriptor("plans/plan.json"),
        ]

    async def execute(self) -> list[FileUpdate]:
        """扫描 pending 状态的 action，执行命令并更新状态。"""
        if not self._actions_dir.exists():
            return []

        pending_actions = self._scan_pending_actions()
        if not pending_actions:
            return []

        updates: list[FileUpdate] = []
        for action_path, action_data in pending_actions:
            try:
                command_name = str(action_data.get("command", ""))
                if not command_name:
                    logger.warning(
                        f"action 缺少命令名: {action_path.name}"
                    )
                    continue

                # 执行命令
                action_data["status"] = "running"
                action_data["updated_at"] = now_text()
                updates.append(
                    self._make_action_update(action_path, action_data)
                )

                try:
                    result = await self._host.invoke_command(
                        command_name,
                        **self._normalize_kwargs(
                            action_data.get("kwargs")
                        ),
                    )
                    action_data["status"] = "done"
                    action_data["result"] = result
                    action_data["updated_at"] = now_text()
                    logger.info(
                        f"命令执行完成: {command_name} -> {result}"
                    )

                    # 更新对应 plan 状态
                    plan_update = self._update_plan_status(
                        str(action_data.get("plan_id", "")),
                        "done",
                    )
                    if plan_update is not None:
                        updates.append(plan_update)

                except Exception as exc:  # noqa: BLE001
                    action_data["status"] = "failed"
                    action_data["error"] = str(exc)
                    action_data["updated_at"] = now_text()
                    logger.warning(
                        f"命令执行失败: {command_name}, error={exc}"
                    )

                    plan_update = self._update_plan_status(
                        str(action_data.get("plan_id", "")),
                        "failed",
                    )
                    if plan_update is not None:
                        updates.append(plan_update)

                # 写回 action 最终状态
                updates.append(
                    self._make_action_update(action_path, action_data)
                )

            except Exception:  # noqa: BLE001
                logger.exception(
                    f"ExecuteNode 执行 action 失败: {action_path.name}"
                )

        return updates

    def _scan_pending_actions(
        self,
    ) -> list[tuple[Path, dict[str, Any]]]:
        """扫描 actions 目录，返回 status == pending 的 action。"""
        pending: list[tuple[Path, dict[str, Any]]] = []
        for action_path in sorted(
            self._actions_dir.glob("action_*.json")
        ):
            try:
                data = json.loads(action_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("status") == "pending":
                    pending.append((action_path, data))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"读取 action 文件失败 {action_path.name}: {exc}"
                )
        return pending

    def _make_action_update(
        self,
        action_path: Path,
        action_data: dict[str, Any],
    ) -> FileUpdate:
        return FileUpdate(
            descriptor=FileDescriptor(
                path=f"actions/{action_path.name}",
                schema="json",
            ),
            content=action_data,
        )

    def _update_plan_status(
        self,
        plan_id: str,
        status: str,
    ) -> FileUpdate | None:
        if not plan_id:
            return None
        plan_path = self._plans_dir / f"plan_{plan_id}.json"
        if not plan_path.exists():
            return None
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan_data, dict):
                return None
            plan_data["status"] = status
            plan_data["updated_at"] = now_text()
            return FileUpdate(
                descriptor=FileDescriptor(
                    path=f"plans/{plan_path.name}",
                    schema="json",
                ),
                content=plan_data,
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                f"更新 plan 状态失败 {plan_path.name}: {exc}"
            )
            return None

    @staticmethod
    def _normalize_kwargs(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
