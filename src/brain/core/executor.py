from __future__ import annotations

import src.brain.core.queues as queues
from src.brain.core import capability_registry
from src.brain.core.models import AttentionState
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Executor")


async def run() -> int:
    executed = 0
    while not queues.actions_queue.empty() and executed < Config.MAX_ACTIONS_PER_BEAT:
        action = queues.actions_queue.peek()
        if action is None:
            break
        queues.actions_queue.pop()
        try:
            await capability_registry.call(action.capability_name, action.params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Capability %s failed: %s", action.capability_name, exc)
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
        queues.clear_current_attention()
