from typing import List, Dict, Callable
from polaris.brain.core.models import TodoItem, Action
from polaris.utils.Logger import get_logger

logger = get_logger()

# Type for an expander function
ExpanderFunc = Callable[[str, List[TodoItem]], List[Action]]


class ActionExpanderRegistry:
    def __init__(self):
        self._expanders: Dict[str, ExpanderFunc] = {}

    def register(self, intent: str, func: ExpanderFunc):
        self._expanders[intent] = func

    def expand(self, intent: str, items: List[TodoItem]) -> List[Action]:
        if intent in self._expanders:
            return self._expanders[intent](intent, items)

        logger.warning(
            f"No expander registered for intent: {intent}. Using default expander."
        )
        return self._default_expander(intent, items)

    def _default_expander(self, intent: str, items: List[TodoItem]) -> List[Action]:
        # Default action generation for stub
        return [
            Action(
                type="log_action",
                params={"message": f"Default execution for intent {intent}"},
                energy_cost=5.0,
            )
        ]


# Global registry instance
expander_registry = ActionExpanderRegistry()


# M1 Default Stub Expanders
def handle_qq_messages_expander(intent: str, items: List[TodoItem]) -> List[Action]:
    return [
        Action(
            type="recall_memory", params={"items_count": len(items)}, energy_cost=5.0
        ),
        Action(
            type="generate_response",
            params={"items_count": len(items)},
            energy_cost=15.0,
        ),
        Action(type="send_msg", params={"items_count": len(items)}, energy_cost=2.0),
        Action(type="update_memory", params={}, energy_cost=3.0),
    ]


def alarm_reminder_expander(intent: str, items: List[TodoItem]) -> List[Action]:
    return [
        Action(type="evaluate_ignore", params={}, energy_cost=1.0),
        Action(type="alert_user", params={"items_count": len(items)}, energy_cost=5.0),
        Action(type="finalize_alarm", params={}, energy_cost=1.0),
    ]


def self_maintenance_expander(intent: str, items: List[TodoItem]) -> List[Action]:
    return [
        Action(type="organize_memory", params={}, energy_cost=10.0),
        Action(type="summarize", params={}, energy_cost=15.0),
    ]


expander_registry.register("handle_qq_messages", handle_qq_messages_expander)
expander_registry.register("alarm_reminder", alarm_reminder_expander)
expander_registry.register("self_maintenance", self_maintenance_expander)
