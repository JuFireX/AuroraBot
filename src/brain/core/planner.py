from __future__ import annotations

import time
import uuid

from src.brain.core.models import Plan, TodoItem, Urgency
from src.brain.core.queues import plans_queue, todo_queue
from src.brain.core.state import bot_state

URGENCY_BONUS = {
    Urgency.GENTLE: 0.0,
    Urgency.NORMAL: 10.0,
    Urgency.URGENT: 30.0,
}


async def run() -> list[Plan]:
    items = todo_queue.drain()
    had_todos = bool(items)
    bot_state.record_activity(had_todos)

    if not items:
        bot_state.idle_counter += 1
        bot_state.update_cognitive_load(plans_queue.size())
        bot_state.adjust_plan_interval(False)
        return []

    bot_state.idle_counter = 0
    grouped_items = _group_items(items)
    created_or_updated: list[Plan] = []

    for group_key, group_items in grouped_items.items():
        intent = _type_to_intent(group_items[0].type)
        highest_urgency = max(group_items, key=lambda item: URGENCY_BONUS[item.urgency]).urgency
        priority = _base_priority(intent) + URGENCY_BONUS[highest_urgency]

        existing = _find_existing_plan(intent, group_key)
        if existing is not None:
            existing.sub_items.extend(group_items)
            existing.priority = max(existing.priority, priority)
            existing.last_touched_at = time.time()
            created_or_updated.append(existing)
            continue

        plan = Plan(
            id=str(uuid.uuid4()),
            intent=intent,
            sub_items=group_items,
            priority=priority,
            base_priority=_base_priority(intent),
            created_at=time.time(),
            last_touched_at=time.time(),
        )
        plans_queue.push(plan)
        created_or_updated.append(plan)

    bot_state.update_cognitive_load(plans_queue.size() + len(items))
    bot_state.adjust_plan_interval(True)
    return created_or_updated


def _group_items(items: list[TodoItem]) -> dict[tuple[str, str], list[TodoItem]]:
    grouped: dict[tuple[str, str], list[TodoItem]] = {}
    for item in items:
        session_id = str(item.payload.get("session_id", item.payload.get("group_key", "__default__")))
        key = (item.type, session_id)
        grouped.setdefault(key, []).append(item)
    return grouped


def _find_existing_plan(intent: str, group_key: tuple[str, str]) -> Plan | None:
    _, session_id = group_key
    for plan in plans_queue.iter_all():
        if plan.intent != intent:
            continue
        existing_session = str(
            plan.sub_items[0].payload.get(
                "session_id",
                plan.sub_items[0].payload.get("group_key", "__default__"),
            )
        )
        if existing_session == session_id:
            return plan
    return None


def _type_to_intent(item_type: str) -> str:
    mapping = {
        "qq_msg": "handle_qq_messages",
        "read_qq_msg": "handle_qq_messages",
        "alarm_reminder": "handle_alarm",
        "system_task": "self_maintenance",
    }
    return mapping.get(item_type, item_type)


def _base_priority(intent: str) -> float:
    mapping = {
        "handle_qq_messages": 50.0,
        "handle_alarm": 20.0,
        "self_maintenance": 5.0,
    }
    return mapping.get(intent, 10.0)
