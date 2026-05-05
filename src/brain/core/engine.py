from __future__ import annotations

import asyncio

import src.brain.core.queues as queues
from src.brain.core import executor, expander, planner
from src.brain.core.state import bot_state
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Engine")


async def run_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await tick()
        except Exception as exc:
            logger.error("[Engine] Heartbeat error: %s", exc)
        await asyncio.sleep(Config.HEARTBEAT_INTERVAL)


async def tick() -> None:
    bot_state.heartbeat_count += 1
    bot_state.regenerate_energy()
    logger.info(
        "[Engine] Beat=%s energy=%.1f todo=%s plans=%s actions=%s interval=%s load=%.2f",
        bot_state.heartbeat_count,
        bot_state.energy_current,
        queues.todo_queue.size(),
        queues.plans_queue.size(),
        queues.actions_queue.size(),
        bot_state.plan_interval,
        bot_state.cognitive_load,
    )

    created_or_updated = []
    if bot_state.heartbeat_count % bot_state.plan_interval == 0:
        created_or_updated = await planner.run()
        if created_or_updated:
            intents = ", ".join(plan.intent for plan in created_or_updated)
            logger.info("[Engine] Planner updated plans: %s", intents)

    if queues.actions_queue.empty() and queues.current_attention is None:
        attention = await expander.run()
        if attention is not None:
            logger.info(
                "[Engine] Attention selected intent=%s actions=%s estimate=%.1f",
                attention.intent,
                attention.action_count,
                attention.total_energy_estimate,
            )

    if queues.current_attention is not None or not queues.actions_queue.empty():
        await executor.run()
