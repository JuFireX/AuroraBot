from __future__ import annotations

import asyncio
import time
import uuid

import src.brain.core.queues as runtime_queues
from src.brain.core import engine
from src.brain.core.models import TodoItem, Urgency
from src.brain.core.queues import (
    actions_queue,
    plans_queue,
    reset_runtime_queues,
    restore_runtime_snapshot,
    todo_queue,
)
from src.brain.core.state import bot_state
from src.brain.core.tool_registry import Tool, clear, register
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Agent")


class Agent:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._session_replies: dict[str, str] = {}
        self._alarm_decisions: dict[str, bool] = {}

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return

        if not (Config.QUEUES_RESTORE_ON_START and restore_runtime_snapshot()):
            reset_runtime_queues()
        bot_state.reset()
        clear()
        self._register_core_tools()
        self._stop_event = asyncio.Event()

        if Config.BOOTSTRAP_DEMO_TODOS and _runtime_empty():
            self.bootstrap_demo_todos()

        logger.info("[Agent] Starting PAA engine in mode=%s", Config.RUN_MODE)
        self._task = asyncio.create_task(engine.run_loop(self._stop_event))

    def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
        self._task = None

    def push_todo(self, todo: TodoItem) -> None:
        todo_queue.push(todo)
        logger.info("[Agent] Todo queued type=%s", todo.type)

    def bootstrap_demo_todos(self) -> None:
        now = time.time()
        self.push_todo(
            TodoItem(
                id=str(uuid.uuid4()),
                type="qq_msg",
                payload={
                    "session_id": "demo-group-10001",
                    "text": "大家早上好，今天的状态怎么样？",
                    "user_id": "demo-user-1",
                },
                urgency=Urgency.URGENT,
                created_at=now,
            )
        )
        self.push_todo(
            TodoItem(
                id=str(uuid.uuid4()),
                type="qq_msg",
                payload={
                    "session_id": "demo-group-10001",
                    "text": "顺便提醒下今天要同步里程碑。",
                    "user_id": "demo-user-2",
                },
                urgency=Urgency.NORMAL,
                created_at=now,
            )
        )
        self.push_todo(
            TodoItem(
                id=str(uuid.uuid4()),
                type="alarm_reminder",
                payload={
                    "id": "stretch-alarm-demo",
                    "message": "该起来活动一下了。",
                    "session_id": "alarm-room",
                },
                urgency=Urgency.GENTLE,
                created_at=now,
            )
        )

    def _register_core_tools(self) -> None:
        register(
            Tool(
                name="recall_memory",
                description="读取当前会话的上下文摘要",
                parameters_schema=_object_schema("session_id", "messages"),
                handler=self._tool_recall_memory,
            )
        )
        register(
            Tool(
                name="generate_response",
                description="根据输入消息生成本地模拟回复",
                parameters_schema=_object_schema("session_id", "messages"),
                handler=self._tool_generate_response,
            )
        )
        register(
            Tool(
                name="send_console_message",
                description="将模拟回复打印到命令行日志",
                parameters_schema=_object_schema("session_id", "messages"),
                handler=self._tool_send_console_message,
            )
        )
        register(
            Tool(
                name="update_memory",
                description="更新本地模拟记忆摘要",
                parameters_schema=_object_schema("session_id", "messages"),
                handler=self._tool_update_memory,
            )
        )
        register(
            Tool(
                name="evaluate_ignore",
                description="根据精力和忙碌程度判断是否忽略柔性闹钟",
                parameters_schema=_object_schema("alarm"),
                handler=self._tool_evaluate_ignore,
            )
        )
        register(
            Tool(
                name="alert_user",
                description="打印闹钟提醒结果",
                parameters_schema=_object_schema("alarm"),
                handler=self._tool_alert_user,
            )
        )
        register(
            Tool(
                name="finalize_alarm",
                description="完成本次闹钟处理",
                parameters_schema=_object_schema("alarm"),
                handler=self._tool_finalize_alarm,
            )
        )
        register(
            Tool(
                name="run_self_maintenance",
                description="执行一次最小自维护任务",
                parameters_schema=_object_schema("intent"),
                handler=self._tool_run_self_maintenance,
            )
        )

    def _tool_recall_memory(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        logger.info(
            "[DemoTool] recall_memory session=%s message_count=%s",
            session_id,
            len(messages),
        )

    def _tool_generate_response(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        latest_message = str(messages[-1].get("text", ""))
        self._session_replies[session_id] = (
            f"收到 {len(messages)} 条消息，当前先处理最后一条：{latest_message}"
        )
        logger.info("[DemoTool] generate_response session=%s", session_id)

    def _tool_send_console_message(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        reply = self._session_replies.get(session_id, "已收到，稍后处理。")
        logger.info(
            "[DemoTool] send_console_message session=%s reply=%s source_messages=%s",
            session_id,
            reply,
            len(messages),
        )

    def _tool_update_memory(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        logger.info(
            "[DemoTool] update_memory session=%s tracked_messages=%s",
            session_id,
            len(messages),
        )

    def _tool_evaluate_ignore(self, alarm: dict[str, object]) -> None:
        alarm_id = str(alarm.get("id", "alarm"))
        should_alert = not (
            bot_state.cognitive_load >= bot_state.busy_threshold
            and bot_state.energy_current < 6
        )
        self._alarm_decisions[alarm_id] = should_alert
        logger.info(
            "[DemoTool] evaluate_ignore alarm=%s should_alert=%s",
            alarm_id,
            should_alert,
        )

    def _tool_alert_user(self, alarm: dict[str, object]) -> None:
        alarm_id = str(alarm.get("id", "alarm"))
        if not self._alarm_decisions.get(alarm_id, True):
            logger.info("[DemoTool] alert_user skipped alarm=%s", alarm_id)
            return
        logger.info(
            "[DemoTool] alert_user alarm=%s message=%s",
            alarm_id,
            alarm.get("message", "提醒时间到了"),
        )

    def _tool_finalize_alarm(self, alarm: dict[str, object]) -> None:
        alarm_id = str(alarm.get("id", "alarm"))
        self._alarm_decisions.pop(alarm_id, None)
        logger.info("[DemoTool] finalize_alarm alarm=%s", alarm_id)

    def _tool_run_self_maintenance(self, intent: str) -> None:
        logger.info("[DemoTool] run_self_maintenance intent=%s", intent)


def _object_schema(*required_fields: str) -> dict[str, object]:
    properties = {
        field: {
            "type": "string" if field != "messages" and field != "alarm" else "object"
        }
        for field in required_fields
    }
    for field, schema in properties.items():
        if field == "messages":
            schema["type"] = "array"
        elif field == "alarm":
            schema["type"] = "object"
    return {
        "type": "object",
        "properties": properties,
        "required": list(required_fields),
    }


instance = Agent()


def _runtime_empty() -> bool:
    return (
        todo_queue.size() == 0
        and plans_queue.size() == 0
        and actions_queue.size() == 0
        and runtime_queues.current_attention is None
    )
