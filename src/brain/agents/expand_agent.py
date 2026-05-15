from __future__ import annotations
from datetime import datetime
from typing import Any, TYPE_CHECKING

from src.brain.kernel.agent_base import Agent, AgentProposal, AgentResult
from src.brain.kernel.state_store import (
    kernel_file,
    load_json_list,
    next_record_id,
    save_json_list,
)
from src.platform.contracts import CommandSpec
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("ExpandAgent")


class ExpandAgent(Agent):
    def __init__(
        self,
        host: "ApplicationHost",
        *,
        max_plans_per_step: int = 4,
    ) -> None:
        super().__init__(host)
        self._max_plans_per_step = max(1, max_plans_per_step)
        self._plans_file = kernel_file("plans.json")
        self._actions_file = kernel_file("actions.json")

    def propose(self) -> AgentProposal | None:
        plans = load_json_list(self._plans_file)
        pending_count = sum(1 for plan in plans if plan.get("status") == "pending")
        if pending_count == 0:
            return None
        return AgentProposal(
            priority=min(60, pending_count + 20),
            reason=f"待展开 plan {pending_count} 个",
            metadata={"plan_count": pending_count, "stage": "expand"},
        )

    async def step(self, proposal: AgentProposal) -> AgentResult:
        commands = self.host.list_command_specs()
        if not commands:
            return AgentResult(summary="当前没有可展开的命令规格")

        plans = load_json_list(self._plans_file)
        actions = load_json_list(self._actions_file)

        pending_plans = [plan for plan in plans if plan.get("status") == "pending"][
            : self._max_plans_per_step
        ]
        if not pending_plans:
            return AgentResult(summary="提案时有 plan, 执行时已无待展开项")

        created_actions = 0
        for plan in pending_plans:
            command = self._select_command(commands, plan)
            action = self._build_action(plan, command)
            actions.append(action)
            plan["status"] = "expanded"
            plan["updated_at"] = now_text()
            plan["action_ids"] = [action["id"]]
            created_actions += 1

        save_json_list(self._plans_file, plans)
        save_json_list(self._actions_file, actions)

        logger.info(f"已展开 {created_actions} 个 action")
        return AgentResult(
            handled=created_actions > 0,
            summary=f"新增 {created_actions} 个 action",
            commands_attempted=created_actions,
            metadata={
                "proposal": proposal.metadata,
                "produced_actions": created_actions,
            },
        )

    def _select_command(
        self,
        commands: list[CommandSpec],
        plan: dict[str, Any],
    ) -> CommandSpec:
        preferred_suffixes = (
            ".dynamic_ping",
            ".echo_message",
            ".save_note",
            ".publish_demo_event",
        )
        goal_text = str(plan.get("goal", "")).lower()
        event_type = str(plan.get("source_event_type", "")).lower()

        for suffix in preferred_suffixes:
            for command in commands:
                if command.name.endswith(suffix):
                    return command

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
        command: CommandSpec,
    ) -> dict[str, Any]:
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
        command: CommandSpec,
    ) -> dict[str, Any]:
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
        payload = plan.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        schema_type = str(field_schema.get("type", "string")).strip().lower()
        normalized_name = field_name.strip().lower()
        summary = str(plan.get("summary", "")).strip()
        event_type = str(plan.get("source_event_type", "")).strip()
        session_id = str(plan.get("session_id", "")).strip()

        preferred_sources: dict[str, list[Any]] = {
            "session_id": [payload.get("session_id"), session_id, "kernel-session"],
            "group_id": [payload.get("group_id"), session_id, "kernel-group"],
            "user_id": [payload.get("user_id"), session_id, "kernel-user"],
            "text": [payload.get("text"), payload.get("message"), summary],
            "message": [
                payload.get("message"),
                summary,
                f"事件触发: {event_type or 'unknown'}",
            ],
            "summary": [summary, payload.get("summary"), f"计划记录: {event_type}"],
            "date": [payload.get("date"), datetime.now().strftime("%Y-%m-%d")],
            "reflections": [
                payload.get("reflections"),
                f"由事件 {event_type or 'unknown'} 生成的规划记录",
            ],
            "interactions": [
                payload.get("interactions"),
                [summary] if summary else [],
            ],
            "interval_seconds": [payload.get("interval_seconds"), 60],
            "alarm_type": [payload.get("alarm_type"), event_type, "generic"],
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

    def _coerce_value(self, value: Any, schema_type: str) -> Any:
        if schema_type == "array":
            if isinstance(value, list):
                return value
            return [str(value)] if value is not None and str(value).strip() else []
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


def _first_non_empty(values: list[Any]) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None
