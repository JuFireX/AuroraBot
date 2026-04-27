from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from polaris.config import Config
from polaris.utils.Logger import get_logger
from nonebot import get_driver

from polaris.brain.core.agent import instance

# from polaris.services.AlarmService.core import alarm_service_instance
from polaris.services.QQService.core import qq_service_instance

Config.ensure_dirs()
logger = get_logger()
driver = get_driver()


@driver.on_startup
async def startup_agent():
    """在 NoneBot 启动时，开启智能体的后台心跳循环"""
    await instance.start()
    # await alarm_service_instance.start()
    await qq_service_instance.start()
    logger.info("Bot 心跳循环与外围服务已启动")


@driver.on_shutdown
async def shutdown_agent():
    """在 NoneBot 关闭时，停止智能体的后台心跳循环"""
    instance.stop()
    # alarm_service_instance.stop()
    qq_service_instance.stop()
    logger.info("Bot 心跳循环与外围服务已中止")
