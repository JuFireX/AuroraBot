from pathlib import Path
import sys
import asyncio

sys.path.append(str(Path(__file__).resolve().parent.parent))

from polaris.config import Config
from polaris.utils.Logger import get_logger
from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

# from polaris.brain.core.agent import instance


Config.ensure_dirs()
logger = get_logger()
driver = get_driver()


@driver.on_startup
async def startup_agent():
    """在 NoneBot 启动时，开启智能体的后台心跳循环"""
    # asyncio.create_task(instance.start())
    logger.info("Bot 心跳循环已启动")


@driver.on_shutdown
async def shutdown_agent():
    """在 NoneBot 关闭时，停止智能体的后台心跳循环"""
    # instance.stop()
    logger.info("Bot 心跳循环已中止")
