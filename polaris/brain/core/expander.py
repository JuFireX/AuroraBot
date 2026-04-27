from typing import Callable, Dict, List

from polaris.config import Config
from polaris.brain.core.models import TodoItem, Action
from polaris.utils.Logger import get_logger

logger = get_logger()

# Type for an expander function
ExpanderFunc = Callable[[str, List[TodoItem]], List[Action]]


class ActionExpanderRegistry:
    def __init__(self):
        self._expanders: Dict[str, ExpanderFunc] = {}
        self._prefix_expanders: list[tuple[str, ExpanderFunc]] = []

    def register(self, intent: str, func: ExpanderFunc):
        self._expanders[intent] = func

    def register_prefix(self, prefix: str, func: ExpanderFunc):
        self._prefix_expanders.append((prefix, func))

    def expand(self, intent: str, items: List[TodoItem]) -> List[Action]:
        if intent in self._expanders:
            return self._expanders[intent](intent, items)

        for prefix, func in self._prefix_expanders:
            if intent.startswith(prefix):
                return func(intent, items)

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
    del intent
    session_id = items[0].group_key or items[0].payload.get("session_id", "unknown")
    messages = [item.payload for item in items]
    return [
        Action(
            type="qq_recall_memory",
            params={"session_id": session_id, "messages": messages},
            energy_cost=Config.action_energy_cost("qq_recall_memory"),
        ),
        Action(
            type="qq_generate_response",
            params={"session_id": session_id, "messages": messages},
            energy_cost=Config.action_energy_cost("qq_generate_response"),
        ),
        Action(
            type="qq_send_msg",
            params={"session_id": session_id, "messages": messages},
            energy_cost=Config.action_energy_cost("qq_send_msg"),
        ),
        Action(
            type="qq_update_memory",
            params={"session_id": session_id},
            energy_cost=Config.action_energy_cost("qq_update_memory"),
        ),
    ]


def alarm_reminder_expander(intent: str, items: List[TodoItem]) -> List[Action]:
    del intent
    reminder = items[0].payload if items else {}
    return [
        Action(
            type="evaluate_ignore",
            params={"alarm": reminder},
            energy_cost=Config.action_energy_cost("evaluate_ignore"),
        ),
        Action(
            type="alert_user",
            params={"alarm": reminder, "items_count": len(items)},
            energy_cost=Config.action_energy_cost("alert_user"),
            preconditions=["alarm_should_alert"],
        ),
        Action(
            type="finalize_alarm",
            params={"alarm": reminder},
            energy_cost=Config.action_energy_cost("finalize_alarm"),
        ),
    ]


def self_maintenance_expander(intent: str, items: List[TodoItem]) -> List[Action]:
    del intent, items
    return [
        Action(
            type="organize_memory",
            params={},
            energy_cost=Config.action_energy_cost("organize_memory"),
        ),
        Action(
            type="summarize",
            params={},
            energy_cost=Config.action_energy_cost("summarize"),
        ),
    ]


expander_registry.register("handle_qq_messages", handle_qq_messages_expander)
expander_registry.register("alarm_reminder", alarm_reminder_expander)
expander_registry.register("self_maintenance", self_maintenance_expander)
