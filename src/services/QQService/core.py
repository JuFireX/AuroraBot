import json
import asyncio
from pathlib import Path
from typing import Any

from nonebot import get_bot, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent

from src.brain.core.agent import instance
from src.brain.core.executor import executor_registry
from src.brain.core.models import Action, TodoItem, Urgency
from src.brain.model.ModelService import chat_completion, trim_text
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("QQService")


class QQService:
    def __init__(self):
        self._running = False
        self._registered = False
        self._message_handler = None
        self._session_responses: dict[str, str] = {}
        self._session_contexts: dict[str, dict[str, Any]] = {}
        self._session_histories: dict[str, list[dict[str, Any]]] = {}
        self._session_memories: dict[str, str] = {}
        self._person_histories: dict[str, list[dict[str, Any]]] = {}
        self._person_memories: dict[str, str] = {}
        self._history_file = Config.QQ_DATA_DIR / "session_histories.json"
        self._memory_file = Config.QQ_DATA_DIR / "session_memories.json"
        self._person_history_file = Config.QQ_DATA_DIR / "person_histories.json"
        self._person_memory_file = Config.QQ_DATA_DIR / "person_memories.json"

    async def start(self):
        if not self._registered:
            self._register_message_listener()
            self._register_executors()
            self._registered = True

        if self._running:
            return

        self._load_persistent_state()
        self._running = True
        logger.info("[QQService] Started")

    def stop(self):
        self._running = False
        self._save_persistent_state()
        logger.info("[QQService] Stopped")

    def _register_message_listener(self):
        if self._message_handler is not None:
            return

        self._message_handler = on_message(priority=5, block=False)

        @self._message_handler.handle()
        async def handle_message(bot: Bot, event: MessageEvent):
            await self.handle_message(bot, event)

    def _register_executors(self):
        executor_registry.register("qq_recall_memory", self.execute_qq_recall_memory)
        executor_registry.register(
            "qq_generate_response", self.execute_qq_generate_response
        )
        executor_registry.register("qq_send_msg", self.execute_qq_send_msg)
        executor_registry.register("qq_update_memory", self.execute_qq_update_memory)

    async def handle_message(self, bot: Bot, event: MessageEvent):
        if not self._running:
            logger.debug("[QQService] Ignored message because service is stopped")
            return

        if str(event.user_id) == str(bot.self_id):
            return

        msg = str(event.get_message())
        is_group = isinstance(event, GroupMessageEvent)
        session_id = event.get_session_id()

        logger.info(f"[QQService] Received message from {session_id}: {msg}")

        self._append_history(
            session_id,
            role="user",
            content=msg,
            user_id=str(event.user_id),
            is_group=is_group,
        )

        todo = TodoItem(
            type="read_qq_msg",
            group_key=session_id,
            payload={
                "session_id": session_id,
                "group_key": session_id,
                "message": msg,
                "user_id": str(event.user_id),
                "self_id": str(bot.self_id),
                "is_group": is_group,
                "group_id": event.group_id if is_group else None,
            },
            urgency=Urgency.URGENT,
        )
        instance.push_todo(todo)
        self._save_persistent_state()
        logger.info(f"[QQService] Todo queued for {session_id}")

    async def execute_qq_recall_memory(self, action: Action):
        session_id = action.params["session_id"]
        messages = action.params["messages"]
        primary_user_id = str(messages[-1]["user_id"]) if messages else "unknown"
        history = self._session_histories.get(session_id, [])
        person_history = self._person_histories.get(primary_user_id, [])
        session_memory = self._session_memories.get(session_id, "")
        person_memory = self._person_memories.get(primary_user_id, "")
        pending_count = len(messages)
        history_before_current = (
            history[:-pending_count] if pending_count <= len(history) else []
        )
        person_history_before_current = [
            item for item in person_history if item.get("session_id") != session_id
        ]
        recent_history = history_before_current[-Config.QQ_MODEL_CONTEXT_LIMIT :]
        shared_history = person_history_before_current[-Config.QQ_MODEL_CONTEXT_LIMIT :]
        self._session_contexts[session_id] = {
            "recent_history": recent_history,
            "shared_history": shared_history,
            "session_memory": session_memory,
            "person_memory": person_memory,
            "primary_user_id": primary_user_id,
        }
        logger.info(
            f"[QQService] Recalled memory for {session_id} with session={len(recent_history)} shared={len(shared_history)}"
        )

    async def execute_qq_generate_response(self, action: Action):
        session_id = action.params["session_id"]
        messages = action.params["messages"]

        logger.info(
            f"[QQService] Generating response for {len(messages)} messages in {session_id}"
        )

        soul_prompt = "You are a helpful assistant."
        soul_path = Config.PROMPTS_DIR / "SOUL.md"
        if soul_path.exists():
            soul_prompt = soul_path.read_text(encoding="utf-8")

        combined_msg = "\n".join(f"{m['user_id']}: {m['message']}" for m in messages)
        recalled_context = self._session_contexts.get(session_id, {})
        person_memory = recalled_context.get("person_memory", "")
        session_memory = recalled_context.get("session_memory", "")
        recent_history = recalled_context.get("recent_history", [])
        shared_history = recalled_context.get("shared_history", [])

        chat_history = [{"role": "system", "content": soul_prompt}]
        chat_history.append(
            {
                "role": "system",
                "content": (
                    f"每次回复尽量控制在{Config.QQ_REPLY_CHAR_LIMIT}字以内，只发一小段自然口语。"
                    "除非用户明确提到，否则不要主动聊云、天空、窗外风景。"
                ),
            }
        )
        if person_memory:
            chat_history.append(
                {
                    "role": "system",
                    "content": f"这是你对这个人的共享记忆，群聊和私聊都可参考：\n{person_memory}",
                }
            )
        if session_memory:
            chat_history.append(
                {
                    "role": "system",
                    "content": f"这是当前会话的局部记忆：\n{session_memory}",
                }
            )
        for item in shared_history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                chat_history.append({"role": role, "content": content})
        for item in recent_history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                chat_history.append({"role": role, "content": content})
        chat_history.append({"role": "user", "content": combined_msg})

        try:
            response = await chat_completion(messages=chat_history)
            reply = trim_text(
                response.choices[0].message.content.strip(),
                Config.QQ_REPLY_CHAR_LIMIT,
            )
            self._session_responses[session_id] = reply
            logger.info(f"[QQService] Generated reply: {reply}")
        except Exception as e:
            logger.error(f"[QQService] Failed to generate response: {e}")
            self._session_responses[session_id] = "（思考中似乎遇到了点小问题呢...）"

    async def execute_qq_send_msg(self, action: Action):
        session_id = action.params["session_id"]
        messages = action.params["messages"]
        reply = self._session_responses.get(session_id)

        if not reply:
            return

        try:
            bot = get_bot(str(messages[0]["self_id"]))
            is_group = messages[0].get("is_group", False)
            reply_parts = self._split_reply_segments(reply)
            if is_group:
                group_id = messages[0]["group_id"]
                for part in reply_parts:
                    await asyncio.sleep(self._typing_delay_seconds(part))
                    await bot.send_group_msg(group_id=group_id, message=part)
                logger.info(f"[QQService] Sent group msg to {group_id}")
            else:
                user_id = messages[0]["user_id"]
                for part in reply_parts:
                    await asyncio.sleep(self._typing_delay_seconds(part))
                    await bot.send_private_msg(user_id=user_id, message=part)
                logger.info(f"[QQService] Sent private msg to {user_id}")

            self._append_history(
                session_id,
                role="assistant",
                content=reply,
                user_id=str(messages[0]["user_id"]),
                is_group=is_group,
            )
            self._save_persistent_state()
        except Exception as e:
            logger.error(f"[QQService] Failed to send msg: {e}")

    async def execute_qq_update_memory(self, action: Action):
        session_id = action.params["session_id"]
        logger.info(f"[QQService] Updating memory for {session_id}")
        history = self._session_histories.get(session_id, [])
        tail = history[-Config.QQ_HISTORY_LIMIT :]
        summary_lines = []
        for item in tail[-8:]:
            speaker = item.get("role", "user")
            content = item.get("content", "")
            if content:
                summary_lines.append(f"{speaker}: {content}")
        if summary_lines:
            session_summary = "\n".join(summary_lines)
            self._session_memories[session_id] = trim_text(session_summary, 800)

            primary_user_id = self._session_contexts.get(session_id, {}).get(
                "primary_user_id"
            )
            if primary_user_id:
                person_tail = self._person_histories.get(primary_user_id, [])
                person_lines = []
                for item in person_tail[-12:]:
                    speaker = item.get("role", "user")
                    content = item.get("content", "")
                    if content:
                        person_lines.append(f"{speaker}: {content}")
                if person_lines:
                    self._person_memories[primary_user_id] = trim_text(
                        "\n".join(person_lines),
                        1000,
                    )
        self._session_responses.pop(session_id, None)
        self._session_contexts.pop(session_id, None)
        self._save_persistent_state()

    def _append_history(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        is_group: bool | None = None,
    ):
        record = {"role": role, "content": content}
        if user_id is not None:
            record["user_id"] = user_id
        if is_group is not None:
            record["is_group"] = is_group

        history = self._session_histories.setdefault(session_id, [])
        history.append(record)
        if len(history) > Config.QQ_HISTORY_LIMIT:
            self._session_histories[session_id] = history[-Config.QQ_HISTORY_LIMIT :]

        if user_id is not None:
            person_history = self._person_histories.setdefault(user_id, [])
            person_history.append(
                {
                    "role": role,
                    "content": content,
                    "session_id": session_id,
                    "is_group": is_group,
                }
            )
            if len(person_history) > Config.QQ_HISTORY_LIMIT * 2:
                self._person_histories[user_id] = person_history[
                    -(Config.QQ_HISTORY_LIMIT * 2) :
                ]

    def _load_persistent_state(self):
        self._session_histories = self._read_json(self._history_file, {})
        self._session_memories = self._read_json(self._memory_file, {})
        self._person_histories = self._read_json(self._person_history_file, {})
        self._person_memories = self._read_json(self._person_memory_file, {})

    def _save_persistent_state(self):
        self._write_json(self._history_file, self._session_histories)
        self._write_json(self._memory_file, self._session_memories)
        self._write_json(self._person_history_file, self._person_histories)
        self._write_json(self._person_memory_file, self._person_memories)

    def _split_reply_segments(self, reply: str) -> list[str]:
        parts = [part.strip() for part in reply.split("|")]
        parts = [part for part in parts if part]
        return parts or [reply]

    def _typing_delay_seconds(self, text: str) -> float:
        text_length = len(text.strip())
        if text_length <= 0:
            return 0.0
        return min(1.8, max(0.25, text_length * 0.06))

    def _read_json(self, file_path: Path, default: Any):
        if not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[QQService] Failed to read {file_path.name}: {e}")
            return default

    def _write_json(self, file_path: Path, data: Any):
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[QQService] Failed to write {file_path.name}: {e}")


qq_service_instance = QQService()
