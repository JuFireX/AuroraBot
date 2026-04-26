from pathlib import Path
import sys
import asyncio

sys.path.append(str(Path(__file__).resolve().parent.parent))

from polaris.config import Config
from polaris.utils.Logger import get_logger
from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

from polaris.brain.core.agent import brain_instance


Config.ensure_dirs()
logger = get_logger()
driver = get_driver()


@driver.on_startup
async def startup_agent():
    """在 NoneBot 启动时，开启智能体的后台心跳循环"""
    asyncio.create_task(brain_instance.start())
    logger.info("Bot 心跳循环已启动")


@driver.on_shutdown
async def shutdown_agent():
    """在 NoneBot 关闭时，停止智能体的后台心跳循环"""
    brain_instance.stop()
    logger.info("Bot 心跳循环已中止")


# ============================================================
# QQ 消息注意力事件处理器
# ============================================================
group_msg = on_message(priority=10, block=False)
private_msg = on_message(priority=5, block=False)


@group_msg.handle()
async def receive_group_event(bot: Bot, event: GroupMessageEvent):
    logger.info(f"收到群聊消息: {event}")
    plain_text = event.get_plaintext().strip()
    if not plain_text:
        return

    await brain_instance.attention_queue.put(
        {
            "type": "qq_msg",
            "bot_id": bot.self_id,
            "group_id": event.group_id,
            "target_id": event.user_id,
            "trigger_event": plain_text,
            "content": plain_text,
        }
    )
    from polaris.brain.memory.memory import memory_service
    await memory_service.record(
        role=f"user_{event.user_id}",
        content=plain_text,
        metadata={"group_id": event.group_id, "user_id": event.user_id}
    )
    logger.debug(f"收到群聊消息并放入注意力池和记忆: {plain_text}")


@private_msg.handle()
async def receive_private_event(bot: Bot, event: PrivateMessageEvent):
    logger.info(f"收到私聊消息: {event}")
    plain_text = event.get_plaintext().strip()
    if not plain_text:
        return

    await brain_instance.attention_queue.put(
        {
            "type": "qq_msg",
            "bot_id": bot.self_id,
            "target_id": event.user_id,
            "trigger_event": plain_text,
            "content": plain_text,
        }
    )
    from polaris.brain.memory.memory import memory_service
    await memory_service.record(
        role=f"user_{event.user_id}",
        content=plain_text,
        metadata={"user_id": event.user_id}
    )
    logger.debug(f"收到私聊消息并放入注意力池和记忆: {plain_text}")
