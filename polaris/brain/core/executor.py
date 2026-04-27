from typing import Dict, Callable, Any
from polaris.brain.core.models import Action
from polaris.utils.Logger import get_logger

logger = get_logger()

# Type for an executor function
ExecutorFunc = Callable[[Action], Any]


class ActionExecutorRegistry:
    def __init__(self):
        self._executors: Dict[str, ExecutorFunc] = {}

    def register(self, action_type: str, func: ExecutorFunc):
        self._executors[action_type] = func

    def execute(self, action: Action) -> Any:
        if action.type in self._executors:
            return self._executors[action.type](action)

        return self._default_executor(action)

    def _default_executor(self, action: Action) -> Any:
        logger.info(
            f"[Stub Executor] Executed Action: '{action.type}' (cost: {action.energy_cost}) with params {action.params}"
        )
        return True


# Global registry instance
executor_registry = ActionExecutorRegistry()
