import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from nonebot import get_bot, get_bots, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent

from src.brain.core.models import TodoItem, Urgency
from src.brain.core.queues import todo_queue
from src.brain.core.reply_store import reply_store
from src.brain.core.session import session_buffer
from src.brain.core.tool_registry import Tool, register
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("QQService")


class QQService:
    def __init__(self) -> None:
        self._running = False
        self._registered = False
        self._message_handler = None
        self._events_file = Config.QQ_DATA_DIR / "qq_events.json"
        self._targets_file = Config.QQ_DATA_DIR / "session_targets.json"
        self._events: list[dict[str, Any]] = []
        self._session_targets: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        if not self._registered:
            self._register_message_listener()
            self._register_tools()
            self._registered = True

        if self._running:
            return

        self._load_persistent_state()
        self._running = True
        logger.info("[QQService] Started")

    def stop(self) -> None:
        self._running = False
        self._save_persistent_state()
        logger.info("[QQService] Stopped")

    def _register_message_listener(self) -> None:
        if self._message_handler is not None:
            return

        self._message_handler = on_message(priority=5, block=False)

        @self._message_handler.handle()
        async def handle_message(bot: Bot, event: MessageEvent) -> None:
            await self.handle_message(bot, event)

    def _register_tools(self) -> None:
        register(
            Tool(
                name="send_qq_message",
                description="向指定 QQ 会话发送文本消息，session_id 为群号或用户号字符串",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["session_id", "text"],
                },
                handler=self.send_qq_message,
            )
        )
        register(
            Tool(
                name="send_session_reply",
                description="发送当前 session 里已经生成好的回复文本",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
                handler=self.send_session_reply,
            )
        )
        register(
            Tool(
                name="send_qq_private_message",
                description="向指定 QQ 用户发送私聊消息",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["user_id", "text"],
                },
                handler=self.send_qq_private_message,
            )
        )
        register(
            Tool(
                name="at_user_in_group",
                description="在群里 @某个用户并附带一段文本",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string"},
                        "user_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["group_id", "user_id", "text"],
                },
                handler=self.at_user_in_group,
            )
        )

    async def handle_message(self, bot: Bot, event: MessageEvent) -> None:
        if not self._running:
            logger.debug("[QQService] Ignored message because service is stopped")
            return

        if str(event.user_id) == str(bot.self_id):
            return

        msg = event.get_plaintext().strip() or str(event.get_message())
        is_group = isinstance(event, GroupMessageEvent)
        session_id = str(event.group_id) if is_group else str(event.user_id)
        await self.ingest_message(
            session_id=session_id,
            user_id=str(event.user_id),
            text=msg,
            is_group=is_group,
            group_id=str(event.group_id) if is_group else None,
            bot_id=str(bot.self_id),
        )

    async def ingest_message(
        self,
        session_id: str,
        user_id: str,
        text: str,
        is_group: bool,
        group_id: str | None,
        bot_id: str,
    ) -> None:
        logger.info("[QQService] Received message from %s: %s", session_id, text)
        session_buffer.append_text(session_id=session_id, role="user", content=text)
        self._session_targets[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "group_id": group_id,
            "is_group": is_group,
            "bot_id": bot_id,
        }
        self._append_event(
            direction="inbound",
            session_id=session_id,
            text=text,
            user_id=user_id,
            is_group=is_group,
            group_id=group_id,
            bot_id=bot_id,
        )

        todo = TodoItem(
            id=str(uuid.uuid4()),
            type="qq_msg",
            payload={
                "session_id": session_id,
                "text": text,
                "user_id": user_id,
                "is_group": is_group,
                "group_id": group_id,
                "bot_id": bot_id,
            },
            urgency=Urgency.NORMAL,
            created_at=time.time(),
        )
        todo_queue.push(todo)
        self._save_persistent_state()
        logger.info("[QQService] Todo queued for %s", session_id)

    async def send_qq_message(self, session_id: str, text: str) -> dict[str, object]:
        target = self._session_targets.get(str(session_id))
        if target is None:
            logger.warning("[QQService] Missing target for session %s, fallback log only", session_id)
            return {"session_id": session_id, "status": "missing_target"}

        if bool(target.get("is_group")):
            await self._send_group_message(
                group_id=str(target.get("group_id", session_id)),
                text=text,
                bot_id=str(target.get("bot_id", "")),
                session_id=str(session_id),
                user_id=str(target.get("user_id", "")),
            )
        else:
            await self._send_private_message(
                user_id=str(target.get("user_id", session_id)),
                text=text,
                bot_id=str(target.get("bot_id", "")),
                session_id=str(session_id),
            )
        return {"session_id": session_id, "status": "sent"}

    async def send_session_reply(self, session_id: str) -> dict[str, object]:
        reply = reply_store.pop(session_id)
        if not reply:
            logger.warning("[QQService] No generated reply found for session %s", session_id)
            return {"session_id": session_id, "status": "missing_reply"}
        return await self.send_qq_message(session_id=session_id, text=reply)

    async def send_qq_private_message(self, user_id: str, text: str) -> dict[str, object]:
        session_id = str(user_id)
        target = self._session_targets.get(session_id, {})
        await self._send_private_message(
            user_id=session_id,
            text=text,
            bot_id=str(target.get("bot_id", "")),
            session_id=session_id,
        )
        return {"user_id": session_id, "status": "sent"}

    async def at_user_in_group(
        self,
        group_id: str,
        user_id: str,
        text: str,
    ) -> dict[str, object]:
        session_id = str(group_id)
        target = self._session_targets.get(session_id, {})
        final_text = f"[CQ:at,qq={user_id}] {text}".strip()
        await self._send_group_message(
            group_id=str(group_id),
            text=final_text,
            bot_id=str(target.get("bot_id", "")),
            session_id=session_id,
            user_id=str(user_id),
        )
        return {"group_id": group_id, "user_id": user_id, "status": "sent"}

    async def _send_group_message(
        self,
        group_id: str,
        text: str,
        bot_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        bot = self._resolve_bot(bot_id)
        for part in self._split_reply_segments(text):
            await asyncio.sleep(self._typing_delay_seconds(part))
            if bot is not None:
                await bot.send_group_msg(group_id=int(group_id), message=part)
            logger.info("[QQService] Sent group msg to %s: %s", group_id, part)
            session_buffer.append_text(session_id=session_id, role="assistant", content=part)
            self._append_event(
                direction="outbound",
                session_id=session_id,
                text=part,
                user_id=user_id,
                is_group=True,
                group_id=group_id,
                bot_id=bot_id,
            )
        self._save_persistent_state()

    async def _send_private_message(
        self,
        user_id: str,
        text: str,
        bot_id: str,
        session_id: str,
    ) -> None:
        bot = self._resolve_bot(bot_id)
        for part in self._split_reply_segments(text):
            await asyncio.sleep(self._typing_delay_seconds(part))
            if bot is not None:
                await bot.send_private_msg(user_id=int(user_id), message=part)
            logger.info("[QQService] Sent private msg to %s: %s", user_id, part)
            session_buffer.append_text(session_id=session_id, role="assistant", content=part)
            self._append_event(
                direction="outbound",
                session_id=session_id,
                text=part,
                user_id=user_id,
                is_group=False,
                group_id=None,
                bot_id=bot_id,
            )
        self._save_persistent_state()

    def _resolve_bot(self, bot_id: str) -> Bot | None:
        try:
            if bot_id:
                return get_bot(bot_id)
        except Exception:
            logger.warning("[QQService] Bot %s not found, fallback to first available bot", bot_id)

        try:
            bots = get_bots()
        except Exception:
            logger.warning("[QQService] NoneBot not initialized, send action will only be logged")
            return None
        if bots:
            first_bot = next(iter(bots.values()))
            return first_bot if isinstance(first_bot, Bot) else None
        logger.warning("[QQService] No active bot available, send action will only be logged")
        return None

    def _append_event(
        self,
        direction: str,
        session_id: str,
        text: str,
        user_id: str,
        is_group: bool,
        group_id: str | None,
        bot_id: str,
    ) -> None:
        self._events.append(
            {
                "direction": direction,
                "session_id": session_id,
                "text": text,
                "user_id": user_id,
                "is_group": is_group,
                "group_id": group_id,
                "bot_id": bot_id,
                "created_at": time.time(),
            }
        )
        if len(self._events) > Config.QQ_HISTORY_LIMIT * 4:
            self._events = self._events[-(Config.QQ_HISTORY_LIMIT * 4) :]

    def _load_persistent_state(self) -> None:
        self._events = self._read_json(self._events_file, [])
        self._session_targets = self._read_json(self._targets_file, {})

    def _save_persistent_state(self) -> None:
        self._write_json(self._events_file, self._events)
        self._write_json(self._targets_file, self._session_targets)

    def _split_reply_segments(self, reply: str) -> list[str]:
        parts = [part.strip() for part in reply.split("|")]
        parts = [part for part in parts if part]
        return parts or [reply]

    def _typing_delay_seconds(self, text: str) -> float:
        text_length = len(text.strip())
        if text_length <= 0:
            return 0.0
        return min(1.8, max(0.25, text_length * 0.06))

    def _read_json(self, file_path: Path, default: Any) -> Any:
        if not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.error(f"[QQService] Failed to read {file_path.name}: {e}")
            return default

    def _write_json(self, file_path: Path, data: Any) -> None:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[QQService] Failed to write {file_path.name}: {e}")


qq_service_instance = QQService()
