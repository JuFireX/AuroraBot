from __future__ import annotations
from datetime import datetime
import random
from typing import Any, TYPE_CHECKING

from src.brain.kernel.agent_base import Agent, AgentProposal, AgentResult
from src.platform.contracts import AppEvent, CommandSpec
from src.utils.log_utils import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("TestAgent")


class TestAgent(Agent):
    def __init__(
        self,
        host: "ApplicationHost",
        *,
        random_source: random.Random | None = None,
        max_events_per_tick: int = 8,
        max_commands_per_event: int = 3,
    ) -> None:
        super().__init__(host)
        self._random = random_source or random.Random()
        self._max_events_per_tick = max(1, max_events_per_tick)
        self._max_commands_per_event = max(1, max_commands_per_event)

    def propose(self) -> AgentProposal | None:
        pending_events = self.host.peek_events()
        if not pending_events:
            return None

        command_count = len(self.host.list_command_specs())
        if command_count == 0:
            return AgentProposal(
                priority=1,
                reason=f"检测到 {len(pending_events)} 个待处理事件, 但当前没有可执行命令",
                metadata={
                    "event_count": len(pending_events),
                    "command_count": 0,
                    "blocked": True,
                },
            )

        return AgentProposal(
            priority=min(100, len(pending_events)),
            reason=f"检测到 {len(pending_events)} 个待处理事件",
            metadata={
                "event_count": len(pending_events),
                "command_count": command_count,
            },
        )

    async def step(self, proposal: AgentProposal) -> AgentResult:
        commands = self.host.list_command_specs()
        if not commands:
            logger.warning(proposal.reason)
            return AgentResult(summary=proposal.reason, metadata=proposal.metadata)

        events = self.host.drain_events(limit=self._max_events_per_tick)
        if not events:
            return AgentResult(summary="提案时有事件, 执行时已被其他 Agent 消费")

        commands_attempted = 0
        commands_succeeded = 0
        for event in events:
            attempted, succeeded = await self._dispatch_event(event, commands)
            commands_attempted += attempted
            commands_succeeded += succeeded

        return AgentResult(
            handled=commands_attempted > 0,
            summary=f"处理了 {len(events)} 个事件",
            events_consumed=len(events),
            commands_attempted=commands_attempted,
            commands_succeeded=commands_succeeded,
            metadata={
                "proposal": proposal.metadata,
                "commands_failed": commands_attempted - commands_succeeded,
            },
        )

    async def _dispatch_event(
        self,
        event: AppEvent,
        commands: list[CommandSpec],
    ) -> tuple[int, int]:
        selected_commands = self._pick_commands(commands)
        logger.info(
            f"消费事件 {event.type}({event.id}), 随机选择 {len(selected_commands)} 个命令"
        )
        commands_attempted = 0
        commands_succeeded = 0
        for command in selected_commands:
            commands_attempted += 1
            kwargs = self._build_kwargs(event, command)
            try:
                result = await self.host.invoke_command(command.name, **kwargs)
                commands_succeeded += 1
                logger.info(f"命令执行完成: {command.name} -> {result}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"命令执行失败: {command.name}, error={exc}")
        return commands_attempted, commands_succeeded

    def _pick_commands(self, commands: list[CommandSpec]) -> list[CommandSpec]:
        sample_size = min(
            len(commands),
            self._random.randint(1, min(self._max_commands_per_event, len(commands))),
        )
        return self._random.sample(commands, sample_size)

    def _build_kwargs(
        self,
        event: AppEvent,
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
            value = self._infer_argument(event, name, field_schema)
            if value is None and name not in required:
                continue
            kwargs[name] = value

        return kwargs

    def _infer_argument(
        self,
        event: AppEvent,
        field_name: str,
        field_schema: dict[str, Any],
    ) -> Any:
        payload = event.payload if isinstance(event.payload, dict) else {}
        schema_type = str(field_schema.get("type", "string")).strip().lower()
        normalized_name = field_name.strip().lower()

        preferred_sources: dict[str, list[Any]] = {
            "session_id": [
                payload.get("session_id"),
                event.session_id,
                "unknown-session",
            ],
            "group_id": [payload.get("group_id"), event.session_id, "unknown-group"],
            "user_id": [payload.get("user_id"), event.session_id, "unknown-user"],
            "text": [payload.get("text"), payload.get("message"), event.summary],
            "message": [
                payload.get("message"),
                event.summary,
                f"事件触发: {event.type}",
            ],
            "summary": [
                event.summary,
                payload.get("summary"),
                f"事件记录: {event.type}",
            ],
            "date": [payload.get("date"), datetime.now().strftime("%Y-%m-%d")],
            "reflections": [
                payload.get("reflections"),
                f"由事件 {event.type} 触发的自动记录",
            ],
            "interactions": [
                payload.get("interactions"),
                [event.summary] if event.summary else [],
            ],
            "interval_seconds": [payload.get("interval_seconds"), 60],
            "alarm_type": [payload.get("alarm_type"), event.type, "generic"],
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
        return event.summary or f"{event.type}:{event.id[:8]}"

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
