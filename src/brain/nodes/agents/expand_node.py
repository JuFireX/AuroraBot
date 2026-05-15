from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

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

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost
    from src.platform.contracts import CommandSpec

logger = get_logger("ExpandNode")

_DATA_DIR = Config.KERNEL_DATA_DIR


class ExpandNode(Node):
    """将 plan 展开为具体 action 的节点。

    守护 ``plans/plan_*.json`` 文件，当新的 plan 到达时，
    从宿主获取可用命令，选择最匹配的命令并为 plan 生成
    对应的 action 文件。

    每个 action 写入独立的 ``actions/action_<id>.json`` 文件。
    Plan 的状态在展开后更新为 ``expanded``。

    Old → New 对应
    --------------
    - 旧 ExpandAgent.propose() + step() → execute()
    - 旧 load_json_list/read  → 直接读独立 plan 文件
    - 旧 append 到 actions.json → 每个 action 独立文件
    """

    def __init__(
        self,
        node_id: str,
        host: ApplicationHost,  # noqa: F821 — migration shim, 后续砍掉
    ) -> None:
        super().__init__(node_id)
        self._host = host
        self._plans_dir = _DATA_DIR / "plans"
        self._actions_dir = _DATA_DIR / "actions"

    @property
    def type(self) -> str:
        return "router"  # 纯数据转换

    @property
    def guards(self) -> list[FilePattern]:
        return [FilePattern("plans/plan_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        return [
            FileDescriptor("actions/action.json"),
            FileDescriptor("plans/plan.json"),
        ]

    async def execute(self) -> list[FileUpdate]:
        """扫描 pending 状态的 plan 文件，生成 action 文件。"""
        commands = self._host.list_command_specs()
        if not commands:
            return []

        if not self._plans_dir.exists():
            return []

        pending_plans = self._scan_pending_plans()
        if not pending_plans:
            return []

        self._actions_dir.mkdir(parents=True, exist_ok=True)

        updates: list[FileUpdate] = []
        for plan_path, plan_data in pending_plans:
            try:
                command = self._select_command(commands, plan_data)
                action = self._build_action(plan_data, command)

                # 写 action 文件
                action_id = str(action["id"])
                updates.append(
                    FileUpdate(
                        descriptor=FileDescriptor(
                            path=f"actions/action_{action_id}.json",
                            schema="json",
                        ),
                        content=action,
                    )
                )

                # 更新 plan 状态
                plan_data["status"] = "expanded"
                plan_data["updated_at"] = now_text()
                plan_data["action_ids"] = [action_id]
                plan_file_name = plan_path.name
                updates.append(
                    FileUpdate(
                        descriptor=FileDescriptor(
                            path=f"plans/{plan_file_name}",
                            schema="json",
                        ),
                        content=plan_data,
                    )
                )

            except Exception:  # noqa: BLE001
                logger.exception(
                    f"ExpandNode 展开 plan 失败: {plan_path.name}"
                )

        return updates

    def _scan_pending_plans(
        self,
    ) -> list[tuple[Path, dict[str, Any]]]:
        """扫描 plans 目录，返回 status == pending 的 plan。"""
        pending: list[tuple[Path, dict[str, Any]]] = []
        for plan_path in sorted(self._plans_dir.glob("plan_*.json")):
            try:
                data = json.loads(plan_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("status") == "pending":
                    pending.append((plan_path, data))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"读取 plan 文件失败 {plan_path.name}: {exc}"
                )
        return pending

    def _select_command(
        self,
        commands: list[CommandSpec],  # noqa: F821
        plan: dict[str, Any],
    ) -> CommandSpec:  # noqa: F821
        """从旧 ExpandAgent._select_command 移植。"""
        preferred_suffixes = (
            ".dynamic_ping",
            ".echo_message",
            ".save_note",
            ".publish_demo_event",
        )
        goal_text = str(plan.get("goal", "")).lower()
        event_type = str(plan.get("source_event_type", "")).lower()

        # 优先匹配已知后缀
        for suffix in preferred_suffixes:
            for command in commands:
                if command.name.endswith(suffix):
                    return command

        # 按 event_type 和 goal 模糊匹配
        for command in commands:
            lowered_name = command.name.lower()
            if event_type and event_type in lowered_name:
                return command
            if goal_text and any(
                token and token in lowered_name for token in goal_text.split()
            ):
                return command

        return commands[0]

    def _build_action(
        self,
        plan: dict[str, Any],
        command: CommandSpec,  # noqa: F821
    ) -> dict[str, Any]:
        """从旧 ExpandAgent._build_action 移植。"""
        timestamp = now_text()
        kwargs = self._build_kwargs(plan, command)
        return {
            "id": next_record_id("action"),
            "plan_id": plan.get("id", ""),
            "source_event_id": plan.get("source_event_id", ""),
            "command": command.name,
            "kwargs": kwargs,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def _build_kwargs(
        self,
        plan: dict[str, Any],
        command: CommandSpec,  # noqa: F821
    ) -> dict[str, Any]:
        """从旧 ExpandAgent._build_kwargs 移植。"""
        schema = (
            command.parameters_schema
            if isinstance(command.parameters_schema, dict)
            else {}
        )
        properties = schema.get("properties", {})
        required = {
            str(name)
            for name in schema.get("required", [])
            if isinstance(name, str) and name in properties
        }
        kwargs: dict[str, Any] = {}

        for name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue
            value = self._infer_argument(plan, name, field_schema)
            if value is None and name not in required:
                continue
            kwargs[name] = value

        return kwargs

    def _infer_argument(
        self,
        plan: dict[str, Any],
        field_name: str,
        field_schema: dict[str, Any],
    ) -> Any:
        """从旧 ExpandAgent._infer_argument 移植。"""
        payload = plan.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        schema_type = str(field_schema.get("type", "string")).strip().lower()
        normalized_name = field_name.strip().lower()
        summary = str(plan.get("summary", "")).strip()
        event_type = str(plan.get("source_event_type", "")).strip()
        session_id = str(plan.get("session_id", "")).strip()

        preferred_sources: dict[str, list[Any]] = {
            "session_id": [
                payload.get("session_id"),
                session_id,
                "kernel-session",
            ],
            "group_id": [payload.get("group_id"), session_id, "kernel-group"],
            "user_id": [payload.get("user_id"), session_id, "kernel-user"],
            "text": [payload.get("text"), payload.get("message"), summary],
            "message": [
                payload.get("message"),
                summary,
                f"事件触发: {event_type or 'unknown'}",
            ],
            "summary": [
                summary,
                payload.get("summary"),
                f"计划记录: {event_type}",
            ],
            "date": [
                payload.get("date"),
                datetime.now().strftime("%Y-%m-%d"),
            ],
            "reflections": [
                payload.get("reflections"),
                f"由事件 {event_type or 'unknown'} 生成的规划记录",
            ],
            "interactions": [
                payload.get("interactions"),
                [summary] if summary else [],
            ],
            "interval_seconds": [payload.get("interval_seconds"), 60],
            "alarm_type": [
                payload.get("alarm_type"),
                event_type,
                "generic",
            ],
        }

        if normalized_name in preferred_sources:
            value = _first_non_empty(preferred_sources[normalized_name])
            if value is not None:
                return self._coerce_value(value, schema_type)

        if field_name in payload:
            return self._coerce_value(payload[field_name], schema_type)

        if schema_type == "array":
            return []
        if schema_type == "number":
            return 0
        if schema_type == "integer":
            return 0
        if schema_type == "boolean":
            return False
        if schema_type == "object":
            return {}
        return summary or event_type or str(plan.get("goal", "")).strip()

    @staticmethod
    def _coerce_value(value: Any, schema_type: str) -> Any:
        if schema_type == "array":
            if isinstance(value, list):
                return value
            return (
                [str(value)]
                if value is not None and str(value).strip()
                else []
            )
        if schema_type == "number":
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
        if schema_type == "integer":
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        if schema_type == "boolean":
            return bool(value)
        if schema_type == "object":
            return value if isinstance(value, dict) else {}
        return str(value).strip()

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE


def _first_non_empty(values: list[Any]) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None
