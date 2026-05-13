from __future__ import annotations

import asyncio

from src.platform.application_host import ApplicationHost
from src.utils.log_utils import get_logger

logger = get_logger("AppLoop")


async def run_app_loop(
    host: ApplicationHost,
    stop_event: asyncio.Event,
    interval: float,
) -> None:
    logger.info("应用循环已启动")

    # 主调度
    while not stop_event.is_set():
        try:
            await host.tick()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"应用帧错误: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.05, interval))
        except asyncio.TimeoutError:
            continue
