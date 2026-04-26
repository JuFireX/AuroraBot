from pathlib import Path
import sys
import asyncio

sys.path.append(str(Path(__file__).resolve().parent.parent))

from polaris.config import Config
from polaris.utils.Logger import get_logger

Config.ensure_dirs()
logger = get_logger()

from nonebot import on_message, get_driver
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

# 导入智能体核心
from polaris.core.agent import agent_instance

driver = get_driver()


@driver.on_startup
async def startup_agent():
    """在 NoneBot 启动时，开启智能体的后台心跳循环"""
    asyncio.create_task(agent_instance.start())
    logger.info("智能体后台任务已注册。")


@driver.on_shutdown
async def shutdown_agent():
    """在 NoneBot 关闭时，停止智能体"""
    agent_instance.stop()


# ============================================================
# 1. 群聊消息处理器（监听所有群消息）
# ============================================================
group_msg = on_message(priority=10, block=False)


@group_msg.handle()
async def receive_group_event(bot: Bot, event: GroupMessageEvent):
    plain_text = event.get_plaintext().strip()
    if not plain_text:
        return

    # 将事件推入注意力队列，不立刻回复
    await agent_instance.attention_queue.put(
        {
            "type": "qq_msg",
            "bot_id": bot.self_id,
            "group_id": event.group_id,
            "user_id": event.user_id,
            "content": plain_text,
        }
    )
    logger.debug(f"收到群聊消息并放入注意力池: {plain_text[:10]}...")


# ============================================================
# 2. 私聊消息处理器
# ============================================================
private_msg = on_message(priority=5, block=False)


@private_msg.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent):
    plain_text = event.get_plaintext().strip()
    if not plain_text:
        return

    # 将事件推入注意力队列，不立刻回复
    await agent_instance.attention_queue.put(
        {
            "type": "qq_msg",
            "bot_id": bot.self_id,
            "user_id": event.user_id,
            "content": plain_text,
        }
    )
    logger.debug(f"收到私聊消息并放入注意力池: {plain_text[:10]}...")
