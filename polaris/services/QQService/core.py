from typing import Any

from litellm import acompletion
from nonebot import get_bot, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent

from polaris.brain.core.agent import instance
from polaris.brain.core.expander import expander_registry
from polaris.brain.core.executor import executor_registry
from polaris.brain.core.models import Action, TodoItem, Urgency
from polaris.config import Config
from polaris.utils.Logger import get_logger

logger = get_logger("QQService")


class QQService:
    def __init__(self):
        self._running = False
        self._registered = False
        self._message_handler = None
        self._original_expand = None
        self._session_responses: dict[str, str] = {}
        self._session_histories: dict[str, list[dict[str, Any]]] = {}

    async def start(self):
        if not self._registered:
            self._register_message_listener()
            self._register_expander()
            self._register_executors()
            self._registered = True

        if self._running:
            return

        self._running = True
        logger.info("[QQService] Started")

    def stop(self):
        self._running = False
        logger.info("[QQService] Stopped")

    def _register_message_listener(self):
        if self._message_handler is not None:
            return

        self._message_handler = on_message(priority=5, block=False)

        @self._message_handler.handle()
        async def handle_message(bot: Bot, event: MessageEvent):
            await self.handle_message(bot, event)

    def _register_expander(self):
        if self._original_expand is not None:
            return

        self._original_expand = expander_registry.expand

        def hooked_expand(intent: str, items: list[TodoItem]) -> list[Action]:
            if intent.startswith("handle_qq_messages_"):
                return self.qq_message_expander(intent, items)
            return self._original_expand(intent, items)

        expander_registry.expand = hooked_expand

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
        )

        todo = TodoItem(
            type=f"handle_qq_messages_{session_id}",
            payload={
                "session_id": session_id,
                "message": msg,
                "user_id": event.user_id,
                "self_id": bot.self_id,
                "is_group": is_group,
                "group_id": event.group_id if is_group else None,
            },
            urgency=Urgency.URGENT,
        )
        instance.push_todo(todo)
        logger.info(f"[QQService] Todo queued for {session_id}")

    def qq_message_expander(self, intent: str, items: list[TodoItem]) -> list[Action]:
        del intent
        messages = [item.payload for item in items]
        session_id = messages[0]["session_id"]

        return [
            Action(
                type="qq_recall_memory",
                params={"session_id": session_id, "messages": messages},
                energy_cost=2.0,
            ),
            Action(
                type="qq_generate_response",
                params={"session_id": session_id, "messages": messages},
                energy_cost=15.0,
            ),
            Action(
                type="qq_send_msg",
                params={"session_id": session_id, "messages": messages},
                energy_cost=5.0,
            ),
            Action(
                type="qq_update_memory",
                params={"session_id": session_id},
                energy_cost=2.0,
            ),
        ]

    async def execute_qq_recall_memory(self, action: Action):
        logger.info(f"[QQService] Recalling memory for {action.params['session_id']}")

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
        chat_history = [
            {"role": "system", "content": soul_prompt},
            {"role": "user", "content": combined_msg},
        ]

        try:
            response = await acompletion(model=Config.MODEL, messages=chat_history)
            reply = response.choices[0].message.content.strip()
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
            if is_group:
                group_id = messages[0]["group_id"]
                await bot.send_group_msg(group_id=group_id, message=reply)
                logger.info(f"[QQService] Sent group msg to {group_id}")
            else:
                user_id = messages[0]["user_id"]
                await bot.send_private_msg(user_id=user_id, message=reply)
                logger.info(f"[QQService] Sent private msg to {user_id}")

            self._append_history(session_id, role="assistant", content=reply)
        except Exception as e:
            logger.error(f"[QQService] Failed to send msg: {e}")

    async def execute_qq_update_memory(self, action: Action):
        session_id = action.params["session_id"]
        logger.info(f"[QQService] Updating memory for {session_id}")
        self._session_responses.pop(session_id, None)

    def _append_history(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
    ):
        record = {"role": role, "content": content}
        if user_id is not None:
            record["user_id"] = user_id

        self._session_histories.setdefault(session_id, []).append(record)


qq_service_instance = QQService()
