from __future__ import annotations

import asyncio

import src.brain.core.queues as queues
from src.brain.core import executor, expander, planner
from src.brain.core.state import bot_state
from src.brain.platform.application_host import app_host
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Engine")


async def run_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await tick()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"在第 {bot_state.heartbeat_count} 心跳时出错: {exc}")
        await asyncio.sleep(Config.HEARTBEAT_INTERVAL)


async def tick() -> None:
    bot_state.heartbeat_count += 1
    await app_host.tick()
    await planner.run()
    if queues.actions_queue.empty() and queues.current_attention is None:
        await expander.run()
    if queues.current_attention is not None or not queues.actions_queue.empty():
        await executor.run()
    queues.persist_runtime_snapshot("heartbeat_tick")
