from __future__ import annotations

import src.brain.core.queues as queues
from src.brain.core.models import AttentionState
from src.brain.core import tool_registry
from src.brain.core.state import bot_state
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Executor")


async def run() -> int:
    executed = 0
    while not queues.actions_queue.empty() and executed < Config.MAX_ACTIONS_PER_BEAT:
        action = queues.actions_queue.peek()
        if action is None:
            break

        if not bot_state.has_energy(action.energy_cost):
            if queues.current_attention is not None:
                queues.current_attention.state = AttentionState.PAUSED
            logger.info(
                "[Executor] Pause attention because energy %.1f < cost %.1f",
                bot_state.energy_current,
                action.energy_cost,
            )
            break

        queues.actions_queue.pop()
        try:
            await tool_registry.call(action.tool_name, action.params)
            bot_state.consume_energy(action.energy_cost)
            logger.info(
                "[Executor] Executed %s cost=%.1f energy_left=%.1f",
                action.tool_name,
                action.energy_cost,
                bot_state.energy_current,
            )
        except Exception as exc:
            logger.error("[Executor] Action %s failed: %s", action.tool_name, exc)
        finally:
            executed += 1
            _advance_attention()

    return executed


def _advance_attention() -> None:
    if queues.current_attention is None:
        return

    queues.current_attention.current_index += 1
    if queues.current_attention.current_index >= queues.current_attention.action_count:
        queues.current_attention.state = AttentionState.COMPLETED
        logger.info(
            "[Executor] Attention completed intent=%s",
            queues.current_attention.intent,
        )
        queues.clear_current_attention()
        return

    if queues.current_attention.state == AttentionState.PAUSED:
        queues.current_attention.state = AttentionState.ACTIVE
