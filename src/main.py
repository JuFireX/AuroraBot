from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.utils.Logger import get_logger
from nonebot import get_driver

from src.brain.core.agent import instance

Config.ensure_dirs()
logger = get_logger()
driver = get_driver()
_running_services: list[object] = []


@driver.on_startup
async def startup_agent():
    """在 NoneBot 启动时，开启 M1 的内核循环。"""
    await instance.start()
    await _start_optional_services()
    logger.info("PAA 内核已启动")


@driver.on_shutdown
async def shutdown_agent():
    """在 NoneBot 关闭时，停止智能体与外围服务。"""
    instance.stop()
    for service in reversed(_running_services):
        stop = getattr(service, "stop", None)
        if callable(stop):
            stop()
    _running_services.clear()
    logger.info("PAA 内核已中止")


async def _start_optional_services() -> None:
    if Config.RUN_MODE == "core":
        logger.info("当前为 core 模式，仅启动 PAA 内核与内置 demo todo")
        return

    if Config.RUN_MODE == "prod" and Config.ENABLE_QQ_SERVICE:
        from src.services.QQService.core import qq_service_instance

        await qq_service_instance.start()
        _running_services.append(qq_service_instance)

    if Config.RUN_MODE == "prod" and Config.ENABLE_ALARM_SERVICE:
        from src.services.AlarmService.core import alarm_service_instance

        await alarm_service_instance.start()
        _running_services.append(alarm_service_instance)

    if Config.RUN_MODE == "prod" and Config.ENABLE_DIARY_SERVICE:
        from src.services.DiaryService.core import diary_service_instance

        await diary_service_instance.start()
        _running_services.append(diary_service_instance)

    if Config.RUN_MODE == "test" and Config.ENABLE_TEST_SERVICE:
        from src.services.TestService.core import test_service_instance

        await test_service_instance.start()
        _running_services.append(test_service_instance)
