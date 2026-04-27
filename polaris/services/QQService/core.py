from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event
from polaris.brain.core.agent import instance
from polaris.brain.core.models import TodoItem, Urgency
from polaris.utils.Logger import get_logger

logger = get_logger()

# Simple hook to capture all QQ messages
qq_message_handler = on_message(priority=5, block=False)


@qq_message_handler.handle()
async def handle_message(bot: Bot, event: Event):
    msg = str(event.get_message())
    logger.info(f"[QQService] Received message: {msg}")

    todo = TodoItem(
        type="handle_qq_messages",
        payload={
            "session_id": event.get_session_id(),
            "message": msg,
            "user_id": event.get_user_id(),
        },
        urgency=Urgency.NORMAL,
    )
    instance.push_todo(todo)
