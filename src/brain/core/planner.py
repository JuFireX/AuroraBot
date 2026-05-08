# ------------------------------------------------------------
# @author: Churk
# @status: 待完善
# @description: 计划模块, 理想功能是由LLM根据待办项抽取生成计划
#
# planner的理想功能是ai能根据todo队列的事件, 抽取部分想要完成的事项, 和当前plan队列已有的事项合并, 整理, 重排优先级.
# ------------------------------------------------------------


from __future__ import annotations

import time
import uuid

from src.brain.core.models import Plan, PlanStatus, TodoItem, TodoStatus, Urgency
from src.brain.core.queues import plans_queue, todo_queue
from src.brain.core.state import bot_state
from src.brain.memory.episodic import episode_store
from src.config import Config

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
    had_new_items = todo_queue.consume_new_item_flag()
    bot_state.record_tick(had_new_items)
    pending_items = todo_queue.iter_pending()
    if not pending_items:
        return []

    created_or_updated: list[Plan] = []
    grouped = _group_items(pending_items)
    for group_key, group_items in grouped.items():
        intent = _type_to_intent(group_items[0].type)
        highest_urgency = max(
            group_items, key=lambda item: URGENCY_BONUS[item.urgency]
        ).urgency
        priority = BASE_PRIORITY.get(intent, 10.0) + URGENCY_BONUS[highest_urgency]
        participants = _extract_participants(group_items)
        related = episode_store.find_pending_by_participants(participants)
        session_id = group_key[1]
        existing = plans_queue.find_merge_target(intent=intent, session_id=session_id)
        if _should_defer_group(intent, group_items, existing):
            continue
        if existing is not None:
            _merge_into_plan(existing, group_items, priority, related)
            plans_queue.push(existing)
            todo_queue.claim(_todo_ids(group_items), existing.id)
            created_or_updated.append(existing)
            continue

        plan = _build_plan(
            intent=intent,
            session_id=session_id,
            group_items=group_items,
            priority=priority,
            related_episode_ids=[episode.id for episode in related],
        )
        plans_queue.push(plan)
        todo_queue.claim(plan.source_todo_ids, plan.id)
        created_or_updated.append(plan)
    return created_or_updated


def _build_plan(
    intent: str,
    session_id: str,
    group_items: list[TodoItem],
    priority: float,
    related_episode_ids: list[str],
) -> Plan:
    now = time.time()
    return Plan(
        id=str(uuid.uuid4()),
        intent=intent,
        summary=_summarize_group(intent, group_items),
        session_id=session_id,
        priority=priority,
        base_priority=BASE_PRIORITY.get(intent, 10.0),
        status=PlanStatus.PENDING,
        source_todo_ids=_todo_ids(group_items),
        related_episodes=related_episode_ids,
        created_at=now,
        last_touched_at=now,
    )


def _merge_into_plan(
    plan: Plan,
    group_items: list[TodoItem],
    priority: float,
    related: list[object],
) -> None:
    plan.source_todo_ids = list(
        dict.fromkeys(plan.source_todo_ids + _todo_ids(group_items))
    )
    plan.summary = _summarize_group(plan.intent, group_items)
    plan.priority = max(plan.priority, priority)
    plan.related_episodes = list(
        dict.fromkeys(
            plan.related_episodes + [getattr(episode, "id") for episode in related]
        )
    )
    if plan.status in {PlanStatus.BLOCKED, PlanStatus.FAILED, PlanStatus.COMPLETED}:
        plan.status = PlanStatus.PENDING
    plan.last_touched_at = time.time()


def _todo_ids(items: list[TodoItem]) -> list[str]:
    return [item.id for item in items]


def _summarize_group(intent: str, items: list[TodoItem]) -> str:
    latest_payload = items[-1].payload if items else {}
    if intent == "handle_qq_messages":
        snippets = [
            str(item.payload.get("text", "")).strip()
            for item in items[-3:]
            if str(item.payload.get("text", "")).strip()
        ]
        merged = " / ".join(snippets)
        return f"处理QQ消息({len(items)}条): {merged[:60]}".strip()
    if intent == "handle_alarm":
        message = str(latest_payload.get("message", "")).strip()
        return f"处理提醒: {message[:40]}".strip()
    if intent == "write_diary":
        summary = str(
            latest_payload.get("summary", latest_payload.get("message", ""))
        ).strip()
        return f"写日记: {summary[:40]}".strip()
    return intent


def _group_items(items: list[TodoItem]) -> dict[tuple[str, str], list[TodoItem]]:
    grouped: dict[tuple[str, str], list[TodoItem]] = {}
    for item in items:
        if item.status != TodoStatus.PENDING:
            continue
        session_id = str(item.payload.get("session_id", "__default__"))
        key = (item.type, session_id)
        grouped.setdefault(key, []).append(item)
    return grouped


def _should_defer_group(
    intent: str,
    group_items: list[TodoItem],
    existing: Plan | None,
) -> bool:
    if intent != "handle_qq_messages" or not group_items:
        return False
    # QQ 连续消息需要一个很短的聚合窗口，避免用户刚连发两三句就被逐条打断式回复。
    if existing is not None and existing.status == PlanStatus.ACTIVE:
        return True
    latest_created_at = max(item.created_at for item in group_items)
    return time.time() - latest_created_at < Config.QQ_REPLY_DEBOUNCE_SECONDS


def _extract_participants(items: list[TodoItem]) -> list[str]:
    participants: list[str] = []
    for item in items:
        payload = item.payload
        if isinstance(payload.get("participants"), list):
            participants.extend(
                str(participant) for participant in payload["participants"]
            )
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
