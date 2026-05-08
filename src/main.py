from __future__ import annotations

import asyncio
import contextlib

from nonebot import get_driver

from src.applications.alarm import AlarmApplication
from src.applications.diary import DiaryApplication
from src.applications.mcp_container import MCPContainer
from src.applications.qq import QQApplication
from src.brain.core import engine
from src.brain.core.capability_registry import clear
from src.brain.core.context_builder import reset_app_planning_hints
from src.brain.core.queues import reset_runtime_queues, restore_runtime_snapshot
from src.brain.core.state import bot_state
from src.brain.memory.tools import register_memory_capabilities
from src.brain.platform.application_host import app_host
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Main")
driver = get_driver()
_engine_task: asyncio.Task[None] | None = None
_stop_event: asyncio.Event | None = None


@driver.on_startup
async def startup_agent() -> None:
    global _engine_task, _stop_event

    Config.ensure_dirs()
    clear()
    reset_app_planning_hints()
    bot_state.reset()
    if not (Config.QUEUES_RESTORE_ON_START and restore_runtime_snapshot()):
        reset_runtime_queues()
    register_memory_capabilities()

    if Config.ENABLE_QQ_SERVICE:
        await app_host.register(QQApplication())
    if Config.ENABLE_DIARY_SERVICE:
        await app_host.register(DiaryApplication())
    if Config.ENABLE_ALARM_SERVICE:
        await app_host.register(AlarmApplication())
    if Config.ENABLE_MCP_CONTAINER:
        await app_host.register(MCPContainer())

    _stop_event = asyncio.Event()
    _engine_task = asyncio.create_task(engine.run_loop(_stop_event))
    logger.info("PAA 内核已启动")


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
    await app_host.stop_all()
    logger.info("PAA 内核已停止")
