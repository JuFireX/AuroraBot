from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nonebot import get_bot, get_bots, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent

from src.platform.contracts import AppEvent
from src.utils.time_utils import now_text
from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI

logger = get_logger("QQApplication")


class QQApplication:
    def __init__(self, enable_listener: bool = True) -> None:
        self._api: PlatformAPI | None = None
        self._enable_listener = enable_listener
        self._running = False
        self._message_handler = None
        self._events_file: Path | None = None
        self._targets_file: Path | None = None
        self._events: list[dict[str, Any]] = []
        self._session_targets: dict[str, dict[str, Any]] = {}

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api
        self._events_file = api.data_dir / "qq_events.json"
        self._targets_file = api.data_dir / "session_targets.json"

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        if self._enable_listener:
            self._register_message_listener()
        self._load_persistent_state()
        self._running = True
        logger.info("QQ application started")

    async def on_stop(self) -> None:
        self._running = False
        self._save_persistent_state()
        logger.info("QQ application stopped")

    async def on_tick(self) -> None:
        return None

    def _register_message_listener(self) -> None:
        if self._message_handler is not None:
            return
        try:
            self._message_handler = on_message(priority=5, block=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("QQ listener registration skipped: %s", exc)
            return

        @self._message_handler.handle()
        async def handle_message(bot: Bot, event: MessageEvent) -> None:
            await self.handle_message(bot, event)

    async def handle_message(self, bot: Bot, event: MessageEvent) -> None:
        if not self._running:
            return
        if str(event.user_id) == str(bot.self_id):
            return

        message_text = event.get_plaintext().strip() or str(event.get_message())
        is_group = isinstance(event, GroupMessageEvent)
        session_id = str(event.group_id) if is_group else str(event.user_id)
        await self.ingest_message(
            session_id=session_id,
            user_id=str(event.user_id),
            text=message_text,
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
        api = self._require_api()
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
        api.emit_event(
            AppEvent(
                source=api.package,
                type="message.received",
                session_id=session_id,
                summary=text.strip(),
                payload={
                    "session_id": session_id,
                    "text": text,
                    "user_id": user_id,
                    "is_group": is_group,
                    "group_id": group_id,
                    "bot_id": bot_id,
                },
            )
        )
        self._save_persistent_state()

    async def send_qq_message(self, session_id: str, text: str) -> dict[str, object]:
        target = self._session_targets.get(str(session_id))
        if target is None:
            logger.warning("Missing target for session %s; logging only", session_id)
            return {"success": False, "delivered_at": now_text()}
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
        return {"success": True, "delivered_at": now_text()}

    async def send_qq_private_message(
        self, user_id: str, text: str
    ) -> dict[str, object]:
        session_id = str(user_id)
        target = self._session_targets.get(session_id, {})
        await self._send_private_message(
            user_id=session_id,
            text=text,
            bot_id=str(target.get("bot_id", "")),
            session_id=session_id,
        )
        return {"success": True}

    async def at_user_in_group(
        self, group_id: str, user_id: str, text: str
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
        return {"success": True}

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
            logger.warning(
                "Bot %s not found; falling back to the first active bot", bot_id
            )
        try:
            bots = get_bots()
        except Exception:
            return None
        if bots:
            first_bot = next(iter(bots.values()))
            return first_bot if isinstance(first_bot, Bot) else None
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
                "created_at": now_text(),
            }
        )
        max_events = max(20, 4 * 50)
        if len(self._events) > max_events:
            self._events = self._events[-max_events:]

    def _load_persistent_state(self) -> None:
        loaded_events = self._read_json(self._events_file, [])
        self._events = [dict(item) for item in loaded_events if isinstance(item, dict)]
        self._session_targets = self._read_json(self._targets_file, {})

    def _save_persistent_state(self) -> None:
        self._write_json(self._events_file, self._events)
        self._write_json(self._targets_file, self._session_targets)

    def _split_reply_segments(self, reply: str) -> list[str]:
        # 兼容旧输出: 主设计应由 brain 直接产出多条发送动作, 这里只保留对历史 "|" 写法的兜底拆分.
        parts = [part.strip() for part in reply.split("|")]
        parts = [part for part in parts if part]
        return parts or [reply]

    def _typing_delay_seconds(self, text: str) -> float:
        text_length = len(text.strip())
        if text_length <= 0:
            return 0.0
        return min(1.8, max(0.25, text_length * 0.06))

    def _read_json(self, file_path: Path | None, default: Any) -> Any:
        if file_path is None or not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return default

    def _write_json(self, file_path: Path | None, data: Any) -> None:
        if file_path is None:
            return
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _require_api(self) -> "PlatformAPI":
        if self._api is None:
            raise RuntimeError("QQApplication is not bound to PlatformAPI")
        return self._api
