from __future__ import annotations

import asyncio
import contextlib

from nonebot import get_driver

from src.brain.platform.application_host import app_host
from src.brain.platform.loop import run_app_loop
from src.config import Config
from src.utils.Logger import get_logger

from apps.alarm import AlarmApplication
from apps.diary import DiaryApplication
from apps.qq import QQApplication

logger = get_logger("Main")
driver = get_driver()
_engine_task: asyncio.Task[None] | None = None
_stop_event: asyncio.Event | None = None


@driver.on_startup
async def startup_agent() -> None:
    global _engine_task, _stop_event

    Config.ensure_dirs()

    if Config.ENABLE_QQ_SERVICE:
        await app_host.register(QQApplication())
    if Config.ENABLE_DIARY_SERVICE:
        await app_host.register(DiaryApplication())
    if Config.ENABLE_ALARM_SERVICE:
        await app_host.register(AlarmApplication())

    _stop_event = asyncio.Event()

    if Config.RUN_MODE in ["app", "prod"]:
        # 启动应用循环
        _engine_task = asyncio.create_task(
            run_app_loop(app_host, _stop_event, Config.APP_FRAME_INTERVAL)
        )
        logger.info("应用循环已启动")

    if Config.RUN_MODE in ["core", "prod"]:
        # TODO: 启动agent循环
        # asyncio.create_task(run_agent_loop(_stop_event, Config.HEARTBEAT_INTERVAL))
        # logger.info("Agent循环已启动")
        pass


@driver.on_shutdown
async def shutdown_agent() -> None:
    global _engine_task

    if _stop_event is not None:
        _stop_event.set()
    if _engine_task is not None:
        _engine_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _engine_task
    _engine_task = None

    # 等待应用循环结束
    await app_host.stop_all()
    logger.info("应用循环已中止")

    # TODO: 等待agent循环结束
    # logger.info("Agent循环已中止")
