from __future__ import annotations

import time
import uuid

import src.brain.core.queues as queues
from src.brain.core import capability_registry
from src.brain.core.context_builder import context_builder
from src.brain.core.models import (
    Action,
    Attention,
    AttentionState,
    Episode,
    Plan,
    PlanStatus,
)
from src.brain.memory.episodic import episode_store
from src.brain.model.ModelService import LLMToolCall, llm_call
from src.utils.Logger import get_logger

logger = get_logger("Expander")

QQ_CAPABILITIES = {
    "im.polaris.qq.send_qq_message",
    "im.polaris.qq.send_qq_private_message",
    "im.polaris.qq.at_user_in_group",
}


async def run() -> Attention | None:
    # attention 存在时说明当前计划仍在执行，不再并发展开新的计划。
    if queues.current_attention is not None or not queues.actions_queue.empty():
        return queues.current_attention

    plan = queues.plans_queue.highest_priority()
    if plan is None:
        return None

    actions = await _expand_plan(plan)
    if not actions:
        # 展开失败时保留计划并记录失败信息，后续可由 planner 重新整理或再次触发。
        plan.expand_fail_count += 1
        plan.last_expanded_at = time.time()
        plan.last_error = "未能生成可执行动作"
        plan.status = (
            PlanStatus.FAILED if plan.expand_fail_count >= 3 else PlanStatus.BLOCKED
        )
        plan.last_touched_at = time.time()
        queues.plans_queue.push(plan)
        return None

    now = time.time()
    action_ids = [action.id for action in actions]
    attention = Attention(
        id=str(uuid.uuid4()),
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        action_ids=action_ids,
        source_todo_ids=list(plan.source_todo_ids),
        state=AttentionState.ACTIVE,
        started_at=now,
        last_advanced_at=now,
    )
    plan.status = PlanStatus.ACTIVE
    plan.attention_count += 1
    plan.last_expanded_at = now
    plan.last_error = ""
    plan.last_touched_at = now
    queues.plans_queue.push(plan)
    queues.set_current_attention(attention)
    queues.actions_queue.push_all(actions)
    return attention


async def _expand_plan(plan: Plan) -> list[Action]:
    llm_actions = await _expand_plan_with_llm(plan)
    if llm_actions:
        return llm_actions
    return _expand_plan_deterministic(plan)


async def _expand_plan_with_llm(plan: Plan) -> list[Action]:
    try:
        related_episodes = _load_related_episodes(plan)
        session_id = _infer_session_id(plan)
        system_prompt = await context_builder.build_system(related_episodes)
        user_message = context_builder.build_user(plan, session_id)
        raw_calls = await llm_call(
            system=system_prompt,
            tools=capability_registry.get_all_schemas(),
            message=user_message,
        )
        actions = [
            _tool_call_to_action(plan, index, call)
            for index, call in enumerate(raw_calls)
        ]
        if actions and _actions_satisfy_plan(plan, actions):
            return actions
        if actions:
            logger.info(
                "LLM actions rejected for %s: %s",
                plan.intent,
                [action.capability_name for action in actions],
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM expansion failed for %s: %s", plan.intent, exc)
    return []


def _expand_plan_deterministic(plan: Plan) -> list[Action]:
    payload = _latest_payload(plan)
    if plan.intent == "handle_qq_messages":
        session_id = str(payload.get("session_id", ""))
        latest_text = str(payload.get("text", "")).strip()
        user_id = str(payload.get("user_id", "__global__"))
        actions = [
            _make_action(
                plan, "memory.recall", {"query": latest_text, "user_id": user_id}, 0
            ),
        ]
        if session_id and capability_registry.get("im.polaris.qq.send_qq_message"):
            reply = "I saw the message and noted it down."
            actions.append(
                _make_action(
                    plan,
                    "im.polaris.qq.send_qq_message",
                    {"session_id": session_id, "text": reply},
                    1,
                )
            )
        actions.append(
            _make_action(
                plan,
                "memory.store",
                {
                    "content": latest_text or "QQ interaction happened.",
                    "user_id": user_id,
                },
                len(actions),
            )
        )
        return actions

    if plan.intent == "handle_alarm":
        session_id = str(payload.get("session_id", "")).strip()
        message = (
            str(payload.get("message", "Reminder time.")).strip() or "Reminder time."
        )
        if session_id and capability_registry.get("im.polaris.qq.send_qq_message"):
            return [
                _make_action(
                    plan,
                    "im.polaris.qq.send_qq_message",
                    {"session_id": session_id, "text": message},
                    0,
                )
            ]
        return [
            _make_action(
                plan,
                "memory.store",
                {"content": message, "user_id": "__global__"},
                0,
            )
        ]

    if plan.intent == "write_diary":
        summary = str(
            payload.get("summary", payload.get("message", "Daily reflection"))
        )
        date = str(payload.get("date", time.strftime("%Y-%m-%d")))
        return [
            _make_action(
                plan,
                "memory.recall",
                {
                    "query": "important events and relationships",
                    "user_id": "__global__",
                },
                0,
            ),
            _make_action(
                plan,
                "im.polaris.diary.write_diary",
                {
                    "date": date,
                    "summary": summary,
                    "interactions": list(payload.get("interactions", [])),
                    "reflections": str(payload.get("reflections", "")),
                },
                1,
            ),
        ]

    return [
        _make_action(
            plan,
            "memory.store",
            {"content": plan.intent, "user_id": "__global__"},
            0,
        )
    ]


def _tool_call_to_action(plan: Plan, order: int, call: LLMToolCall) -> Action:
    capability_name = capability_registry.resolve_name(call.name)
    return _make_action(
        plan,
        capability_name,
        _normalize_action_params(plan, capability_name, call.arguments),
        order,
    )


def _make_action(
    plan: Plan,
    capability_name: str,
    params: dict[str, object],
    order: int,
) -> Action:
    return Action(
        id=str(uuid.uuid4()),
        plan_id=plan.id,
        capability_name=capability_name,
        params=params,
        order=order,
        created_at=time.time(),
    )


def _load_related_episodes(plan: Plan) -> list[Episode]:
    episodes: list[Episode] = []
    for episode_id in plan.related_episodes:
        episode = episode_store.get(episode_id)
        if episode is not None:
            episodes.append(episode)
    return episodes


def _infer_session_id(plan: Plan) -> str | None:
    return plan.session_id or None


def _latest_payload(plan: Plan) -> dict[str, object]:
    todos = queues.todo_queue.get_many(plan.source_todo_ids)
    if not todos:
        return {}
    return dict(todos[-1].payload)


def _normalize_action_params(
    plan: Plan,
    capability_name: str,
    params: dict[str, object],
) -> dict[str, object]:
    normalized = dict(params)
    latest_payload = _latest_payload(plan)
    if capability_name in QQ_CAPABILITIES:
        if "text" not in normalized and "message" in normalized:
            normalized["text"] = normalized.pop("message")
    if capability_name == "im.polaris.qq.send_qq_message":
        if not str(normalized.get("session_id", "")).strip():
            session_id = str(latest_payload.get("session_id", plan.session_id)).strip()
            if session_id:
                normalized["session_id"] = session_id
    if capability_name == "im.polaris.qq.send_qq_private_message":
        if not str(normalized.get("user_id", "")).strip():
            user_id = str(latest_payload.get("user_id", plan.session_id)).strip()
            if user_id:
                normalized["user_id"] = user_id
    if capability_name == "im.polaris.qq.at_user_in_group":
        if not str(normalized.get("group_id", "")).strip():
            group_id = str(latest_payload.get("group_id", plan.session_id)).strip()
            if group_id:
                normalized["group_id"] = group_id
        if not str(normalized.get("user_id", "")).strip():
            user_id = str(latest_payload.get("user_id", "")).strip()
            if user_id:
                normalized["user_id"] = user_id
    return normalized


def _actions_satisfy_plan(plan: Plan, actions: list[Action]) -> bool:
    capability_names = [action.capability_name for action in actions]
    if plan.intent == "handle_qq_messages":
        return any(name in QQ_CAPABILITIES for name in capability_names)
    if plan.intent == "write_diary":
        return "im.polaris.diary.write_diary" in capability_names
    return bool(actions)
