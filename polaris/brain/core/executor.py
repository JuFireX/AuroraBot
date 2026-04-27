import asyncio
from typing import Dict, Callable, Any, Awaitable
from polaris.brain.core.models import Action
from polaris.utils.Logger import get_logger

logger = get_logger()

# Type for an executor function, supporting both sync and async
ExecutorFunc = Callable[[Action], Awaitable[Any] | Any]
PreconditionFunc = Callable[[Action], Awaitable[bool] | bool]


class ActionExecutorRegistry:
    def __init__(self):
        self._executors: Dict[str, ExecutorFunc] = {}
        self._preconditions: Dict[str, PreconditionFunc] = {}

    def register(self, action_type: str, func: ExecutorFunc):
        self._executors[action_type] = func

    def register_precondition(self, name: str, func: PreconditionFunc):
        self._preconditions[name] = func

    async def check_preconditions(self, action: Action) -> bool:
        for name in action.preconditions:
            checker = self._preconditions.get(name)
            if checker is None:
                logger.warning(f"[Executor] Missing precondition checker: {name}")
                return False

            result = checker(action)
            if asyncio.iscoroutine(result):
                result = await result

            if not result:
                logger.info(
                    f"[Executor] Preconditions blocked action '{action.type}' via '{name}'"
                )
                return False

        return True

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


async def execute_log_action(action: Action) -> bool:
    logger.info(f"[Action] {action.params.get('message', action.type)}")
    return True


async def execute_organize_memory(action: Action) -> bool:
    del action
    logger.info("[Self Maintenance] Organizing memory stubs")
    return True


async def execute_summarize(action: Action) -> bool:
    del action
    logger.info("[Self Maintenance] Summarizing current context stubs")
    return True


executor_registry.register("log_action", execute_log_action)
executor_registry.register("organize_memory", execute_organize_memory)
executor_registry.register("summarize", execute_summarize)
