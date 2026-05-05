from __future__ import annotations

import asyncio
import time
import uuid

import src.brain.core.queues as runtime_queues
from src.brain.core import engine
from src.brain.core.models import TodoItem, Urgency
from src.brain.core.reply_store import reply_store
from src.brain.core.session import session_buffer
from src.brain.core.queues import (
    actions_queue,
    plans_queue,
    reset_runtime_queues,
    restore_runtime_snapshot,
    todo_queue,
)
from src.brain.memory.semantic import semantic_memory
from src.brain.memory.snapshot import memory_snapshot
from src.brain.memory.tools import register_memory_tools
from src.brain.model.ModelService import chat_completion, trim_text
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
        register_memory_tools()
        self._stop_event = asyncio.Event()

        if (
            Config.RUN_MODE == "core"
            and Config.BOOTSTRAP_DEMO_TODOS
            and _runtime_empty()
        ):
            self.bootstrap_demo_todos()

        logger.info("[Agent] Starting PAA engine in mode=%s", Config.RUN_MODE)
        self._task = asyncio.create_task(engine.run_loop(self._stop_event))

    def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
        self._task = None
        reply_store.clear()

    def push_todo(self, todo: TodoItem) -> None:
        self._capture_working_memory(todo)
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

    async def _tool_generate_response(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        latest_message = str(messages[-1].get("text", "")) if messages else ""
        user_id = str(messages[-1].get("user_id", "__global__")) if messages else "__global__"
        reply = await self._generate_personalized_reply(
            session_id=session_id,
            user_id=user_id,
            incoming_messages=messages,
            latest_message=latest_message,
        )
        self._session_replies[session_id] = reply
        reply_store.set(session_id, reply)
        logger.info("[Agent] generate_response session=%s reply=%s", session_id, reply)

    def _tool_send_console_message(
        self,
        session_id: str,
        messages: list[dict[str, object]],
    ) -> None:
        reply = self._session_replies.get(session_id) or reply_store.get(session_id) or "已收到，稍后处理。"
        logger.info(
            "[DemoTool] send_console_message session=%s reply=%s source_messages=%s",
            session_id,
            reply,
            len(messages),
        )

    async def _generate_personalized_reply(
        self,
        session_id: str,
        user_id: str,
        incoming_messages: list[dict[str, object]],
        latest_message: str,
    ) -> str:
        soul_prompt = self._read_prompt("SOUL.md", fallback="你是小光，真实自然地回复。")
        if memory_snapshot.should_refresh():
            await memory_snapshot.refresh()

        user_memories, global_memories = await asyncio.gather(
            semantic_memory.search(query=latest_message, user_id=user_id),
            semantic_memory.search(query=latest_message, user_id="__global__"),
        )
        recent_messages = session_buffer.get_context(session_id)[-Config.QQ_MODEL_CONTEXT_LIMIT :]
        chat_messages: list[dict[str, object]] = [
            {"role": "system", "content": soul_prompt},
            {
                "role": "system",
                "content": (
                    "你现在在 QQ 上回复消息。"
                    f"回复控制在 {Config.QQ_REPLY_CHAR_LIMIT} 字以内，纯文本，不要 markdown。"
                    "语气像熟人聊天，避免客服腔。"
                    "如果需要分成多条消息，使用 | 分隔，最多 3 段。"
                ),
            },
        ]

        snapshot_text = memory_snapshot.get().strip()
        if snapshot_text:
            chat_messages.append(
                {
                    "role": "system",
                    "content": f"这是你的长期语义记忆摘要，可按相关性自然参考：\n{trim_text(snapshot_text, 1200)}",
                }
            )
        if user_memories:
            chat_messages.append(
                {
                    "role": "system",
                    "content": "这是和当前用户相关的记忆:\n" + "\n".join(f"- {item}" for item in user_memories[:5]),
                }
            )
        if global_memories:
            chat_messages.append(
                {
                    "role": "system",
                    "content": "这是可参考的全局记忆:\n" + "\n".join(f"- {item}" for item in global_memories[:5]),
                }
            )

        for item in recent_messages:
            if item.role not in {"user", "assistant"}:
                continue
            chat_messages.append({"role": item.role, "content": item.content})

        incoming_lines = [
            f"{message.get('user_id', 'user')}: {message.get('text', '')}"
            for message in incoming_messages
            if str(message.get("text", "")).strip()
        ]
        if incoming_lines:
            chat_messages.append(
                {
                    "role": "user",
                    "content": "本轮待回复消息:\n" + "\n".join(incoming_lines),
                }
            )

        try:
            response = await chat_completion(messages=chat_messages)
            content = str(response.choices[0].message.content or "").strip().replace("\n", " ")
            reply = trim_text(content, Config.QQ_REPLY_CHAR_LIMIT)
            if reply:
                return reply
        except Exception as exc:
            logger.warning("[Agent] generate_response failed for session=%s: %s", session_id, exc)
        return self._fallback_reply(latest_message)

    def _fallback_reply(self, latest_message: str) -> str:
        text = latest_message.strip()
        if not text:
            return "我在捏，你继续说"
        return trim_text(f"我记住啦，{text}", Config.QQ_REPLY_CHAR_LIMIT)

    def _read_prompt(self, filename: str, fallback: str) -> str:
        path = Config.PROMPTS_DIR / filename
        if not path.exists():
            return fallback
        try:
            return path.read_text(encoding="utf-8-sig").strip() or fallback
        except Exception:
            return fallback

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

    def _capture_working_memory(self, todo: TodoItem) -> None:
        session_id = todo.payload.get("session_id")
        text = todo.payload.get("text")
        if session_id and text:
            session_buffer.append_text(
                session_id=str(session_id),
                role="user",
                content=str(text),
            )


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
