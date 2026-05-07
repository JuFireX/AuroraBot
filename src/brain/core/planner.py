from __future__ import annotations

import time
import uuid

from src.brain.core.models import Plan, TodoItem, Urgency
from src.brain.core.queues import plans_queue, todo_queue
from src.brain.core.state import bot_state
from src.brain.memory.episodic import episode_store

URGENCY_BONUS = {
    Urgency.GENTLE: 0.0,
    Urgency.NORMAL: 10.0,
    Urgency.URGENT: 50.0,
}

BASE_PRIORITY = {
    "handle_qq_messages": 50.0,
    "handle_alarm": 20.0,
    "write_diary": 8.0,
    "self_maintenance": 5.0,
}


async def run() -> list[Plan]:
    items = todo_queue.drain()
    bot_state.record_tick(bool(items))
    if not items:
        return []

    grouped = _group_items(items)
    created_or_updated: list[Plan] = []
    for group_key, group_items in grouped.items():
        intent = _type_to_intent(group_items[0].type)
        highest_urgency = max(group_items, key=lambda item: URGENCY_BONUS[item.urgency]).urgency
        priority = BASE_PRIORITY.get(intent, 10.0) + URGENCY_BONUS[highest_urgency]
        participants = _extract_participants(group_items)
        related = episode_store.find_pending_by_participants(participants)
        existing = _find_existing_plan(intent=intent, group_key=group_key)
        if existing is not None:
            existing.sub_items.extend(group_items)
            existing.priority = max(existing.priority, priority)
            existing.related_episodes = list(
                dict.fromkeys(existing.related_episodes + [episode.id for episode in related])
            )
            existing.last_touched_at = time.time()
            created_or_updated.append(existing)
            continue

        plan = Plan(
            id=str(uuid.uuid4()),
            intent=intent,
            sub_items=group_items,
            priority=priority,
            base_priority=BASE_PRIORITY.get(intent, 10.0),
            related_episodes=[episode.id for episode in related],
            created_at=time.time(),
            last_touched_at=time.time(),
        )
        plans_queue.push(plan)
        created_or_updated.append(plan)
    return created_or_updated


def _group_items(items: list[TodoItem]) -> dict[tuple[str, str], list[TodoItem]]:
    grouped: dict[tuple[str, str], list[TodoItem]] = {}
    for item in items:
        session_id = str(item.payload.get("session_id", "__default__"))
        key = (item.type, session_id)
        grouped.setdefault(key, []).append(item)
    return grouped


def _find_existing_plan(intent: str, group_key: tuple[str, str]) -> Plan | None:
    _, session_id = group_key
    for plan in plans_queue.iter_all():
        if plan.intent != intent or not plan.sub_items:
            continue
        existing_session_id = str(plan.sub_items[0].payload.get("session_id", "__default__"))
        if existing_session_id == session_id:
            return plan
    return None


def _extract_participants(items: list[TodoItem]) -> list[str]:
    participants: list[str] = []
    for item in items:
        payload = item.payload
        if isinstance(payload.get("participants"), list):
            participants.extend(str(participant) for participant in payload["participants"])
        if "user_id" in payload:
            participants.append(str(payload["user_id"]))
        if "session_id" in payload:
            participants.append(str(payload["session_id"]))
    return list(dict.fromkeys(participants))


def _type_to_intent(item_type: str) -> str:
    return {
        "qq_msg": "handle_qq_messages",
        "alarm_reminder": "handle_alarm",
        "diary_prompt": "write_diary",
        "system_task": "self_maintenance",
    }.get(item_type, item_type)
