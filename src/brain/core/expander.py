from __future__ import annotations

import time
import uuid

import src.brain.core.queues as queues
from src.brain.core import capability_registry
from src.brain.core.context_builder import context_builder
from src.brain.core.models import Action, Attention, AttentionState, Episode, Plan
from src.brain.core.state import bot_state
from src.brain.memory.episodic import episode_store
from src.brain.model.ModelService import LLMToolCall, llm_call
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Expander")

QQ_CAPABILITIES = {
    "im.polaris.qq.send_qq_message",
    "im.polaris.qq.send_qq_private_message",
    "im.polaris.qq.at_user_in_group",
}


async def run() -> Attention | None:
    if queues.current_attention is not None or not queues.actions_queue.empty():
        return queues.current_attention

    if queues.plans_queue.empty():
        if bot_state.is_idle():
            _generate_self_maintenance_plan()
        else:
            return None

    plan = queues.plans_queue.pop_lowest() if bot_state.is_idle() else queues.plans_queue.pop_highest()
    if plan is None:
        return None

    actions = await _expand_plan(plan)
    if not actions:
        return None

    attention = Attention(
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        action_count=len(actions),
        state=AttentionState.ACTIVE,
        created_at=time.time(),
    )
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
        actions = [_tool_call_to_action(call) for call in raw_calls]
        if actions and _actions_satisfy_plan(plan, actions):
            return actions
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM expansion failed for %s: %s", plan.intent, exc)
    return []


def _expand_plan_deterministic(plan: Plan) -> list[Action]:
    if plan.intent == "handle_qq_messages":
        payload = plan.sub_items[-1].payload if plan.sub_items else {}
        session_id = str(payload.get("session_id", ""))
        latest_text = str(payload.get("text", "")).strip()
        user_id = str(payload.get("user_id", "__global__"))
        actions = [
            _make_action("memory.recall", {"query": latest_text, "user_id": user_id}),
        ]
        if session_id and capability_registry.get("im.polaris.qq.send_qq_message"):
            reply = "I saw the message and noted it down."
            actions.append(
                _make_action(
                    "im.polaris.qq.send_qq_message",
                    {"session_id": session_id, "text": reply},
                )
            )
        actions.append(
            _make_action(
                "memory.store",
                {
                    "content": latest_text or "QQ interaction happened.",
                    "user_id": user_id,
                },
            )
        )
        return actions

    if plan.intent == "handle_alarm":
        payload = plan.sub_items[-1].payload if plan.sub_items else {}
        session_id = str(payload.get("session_id", "")).strip()
        message = str(payload.get("message", "Reminder time.")).strip() or "Reminder time."
        if session_id and capability_registry.get("im.polaris.qq.send_qq_message"):
            return [
                _make_action(
                    "im.polaris.qq.send_qq_message",
                    {"session_id": session_id, "text": message},
                )
            ]
        return [_make_action("memory.store", {"content": message, "user_id": "__global__"})]

    if plan.intent == "write_diary":
        payload = plan.sub_items[-1].payload if plan.sub_items else {}
        summary = str(payload.get("summary", payload.get("message", "Daily reflection")))
        date = str(payload.get("date", time.strftime("%Y-%m-%d")))
        return [
            _make_action(
                "memory.recall",
                {"query": "important events and relationships", "user_id": "__global__"},
            ),
            _make_action(
                "im.polaris.diary.write_diary",
                {
                    "date": date,
                    "summary": summary,
                    "interactions": list(payload.get("interactions", [])),
                    "reflections": str(payload.get("reflections", "")),
                },
            ),
        ]

    return [_make_action("memory.store", {"content": plan.intent, "user_id": "__global__"})]


def _tool_call_to_action(call: LLMToolCall) -> Action:
    return _make_action(capability_registry.resolve_name(call.name), call.arguments)


def _make_action(capability_name: str, params: dict[str, object]) -> Action:
    return Action(id=str(uuid.uuid4()), capability_name=capability_name, params=params)


def _generate_self_maintenance_plan() -> None:
    plan = Plan(
        id=str(uuid.uuid4()),
        intent="self_maintenance",
        sub_items=[],
        priority=1.0,
        base_priority=1.0,
        created_at=time.time(),
        last_touched_at=time.time(),
    )
    queues.plans_queue.push(plan)


def _load_related_episodes(plan: Plan) -> list[Episode]:
    episodes: list[Episode] = []
    for episode_id in plan.related_episodes:
        episode = episode_store.get(episode_id)
        if episode is not None:
            episodes.append(episode)
    return episodes


def _infer_session_id(plan: Plan) -> str | None:
    if not plan.sub_items:
        return None
    session_id = plan.sub_items[0].payload.get("session_id")
    return str(session_id) if session_id else None


def _actions_satisfy_plan(plan: Plan, actions: list[Action]) -> bool:
    capability_names = [action.capability_name for action in actions]
    if plan.intent == "handle_qq_messages":
        return any(name in QQ_CAPABILITIES for name in capability_names)
    if plan.intent == "write_diary":
        return "im.polaris.diary.write_diary" in capability_names
    return bool(actions)
