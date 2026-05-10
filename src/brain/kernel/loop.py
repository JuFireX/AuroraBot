from __future__ import annotations
import asyncio

from src.brain.kernel.agent_base import Agent
from src.utils.Logger import get_logger

logger = get_logger("AgentLoop")


async def run_agent_loop(
    agent: Agent,
    stop_event: asyncio.Event,
    interval: float,
) -> None:
    while not stop_event.is_set():
        try:
            await agent.tick()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"智能体心跳错误: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.05, interval))
        except asyncio.TimeoutError:
            continue
