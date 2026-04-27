import asyncio
from typing import Dict, Callable, Any, Awaitable
from polaris.brain.core.models import Action
from polaris.utils.Logger import get_logger

logger = get_logger()

# Type for an executor function, supporting both sync and async
ExecutorFunc = Callable[[Action], Awaitable[Any] | Any]


class ActionExecutorRegistry:
    def __init__(self):
        self._executors: Dict[str, ExecutorFunc] = {}

    def register(self, action_type: str, func: ExecutorFunc):
        self._executors[action_type] = func

    async def execute(self, action: Action) -> Any:
        func = self._executors.get(action.type, self._default_executor)
        result = func(action)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _default_executor(self, action: Action) -> Any:
        logger.info(
            f"[Stub Executor] Executed Action: '{action.type}' (cost: {action.energy_cost}) with params {action.params}"
        )
        return True


# Global registry instance
executor_registry = ActionExecutorRegistry()
