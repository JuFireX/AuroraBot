from __future__ import annotations

import time
import uuid

import src.brain.core.queues as queues
from src.brain.core.context_builder import context_builder
from src.brain.core.models import Action, Attention, AttentionState, Episode, Plan
from src.brain.core.state import bot_state
from src.brain.core.tool_registry import get_all, get_schemas
from src.brain.memory.episodic import episode_store
from src.brain.model.ModelService import LLMToolCall, llm_call
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Expander")

ENERGY_COST_TABLE = {
    "recall_memory": 2.0,
    "generate_response": 8.0,
    "send_console_message": 2.0,
    "send_session_reply": 2.0,
    "update_memory": 1.0,
    "evaluate_ignore": 1.0,
    "alert_user": 2.0,
    "finalize_alarm": 1.0,
    "run_self_maintenance": 3.0,
    "__default__": Config.DEFAULT_ENERGY_COST,
}


async def run() -> Attention | None:
    if queues.current_attention is not None or not queues.actions_queue.empty():
        return queues.current_attention

    if queues.plans_queue.empty():
        if bot_state.is_idle() and bot_state.heartbeat_count % Config.SELF_MAINTENANCE_INTERVAL == 0:
            _generate_self_maintenance_plan()
        else:
            return None

    plan = (
        queues.plans_queue.pop_lowest()
        if bot_state.is_idle()
        else queues.plans_queue.pop_highest()
    )
    if plan is None:
        return None

    actions = await _expand_plan(plan)
    total_cost = sum(action.energy_cost for action in actions)
    attention = Attention(
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        total_energy_estimate=total_cost,
        action_count=len(actions),
        state=AttentionState.ACTIVE,
        created_at=time.time(),
    )
    queues.set_current_attention(attention)
    queues.actions_queue.push_all(actions)
    return attention


async def _expand_plan(plan: Plan) -> list[Action]:
    if Config.RUN_MODE != "test":
        llm_actions = await _expand_plan_with_llm(plan)
        if llm_actions:
            return llm_actions
    return _expand_plan_deterministic(plan)


async def _expand_plan_with_llm(plan: Plan) -> list[Action]:
    try:
        related_episodes = _load_related_episodes(plan)
        session_id = _infer_session_id(plan)
        system_prompt = await context_builder.build_system(related_episodes, session_id)
        user_message = context_builder.build_user(plan, session_id)
        raw_calls = await llm_call(
            system=system_prompt,
            tools=get_schemas(),
            message=user_message,
        )
        actions = [_tool_call_to_action(call) for call in raw_calls]
        if actions and _actions_satisfy_plan(plan, actions):
            logger.info(
                "[Expander] LLM expanded intent=%s into %s actions",
                plan.intent,
                len(actions),
            )
            return actions
        if actions:
            logger.warning(
                "[Expander] LLM actions incomplete for intent=%s, fallback to deterministic",
                plan.intent,
            )
    except Exception as exc:
        logger.warning("[Expander] LLM expand failed for intent=%s: %s", plan.intent, exc)
    return []


def _expand_plan_deterministic(plan: Plan) -> list[Action]:
    if plan.intent == "handle_qq_messages":
        session_id = str(plan.sub_items[0].payload.get("session_id", "demo-session"))
        messages = [item.payload for item in plan.sub_items]
        latest_text = str(messages[-1].get("text", ""))
        memory_user_id = str(
            messages[-1].get("user_id", messages[-1].get("session_id", "__global__"))
        )
        episode_actions = _make_episode_followup_actions(plan, messages)
        if _has_tool("send_qq_message"):
            return [
                _make_action(
                    "recall_memory",
                    {"query": latest_text, "user_id": memory_user_id},
                ),
                _make_action(
                    "generate_response",
                    {"session_id": session_id, "messages": messages},
                ),
                _make_action(
                    "send_session_reply",
                    {"session_id": session_id},
                ),
                *episode_actions,
                _make_action(
                    "store_memory",
                    {
                        "content": " | ".join(
                            str(message.get("text", "")) for message in messages if message.get("text")
                        ),
                        "user_id": memory_user_id,
                    },
                ),
            ]
        return [
            _make_action("recall_memory", {"query": latest_text, "user_id": memory_user_id}),
            _make_action(
                "generate_response",
                {"session_id": session_id, "messages": messages},
            ),
            _make_action(
                "send_console_message",
                {"session_id": session_id, "messages": messages},
            ),
            *episode_actions,
            _make_action(
                "store_memory",
                {
                    "content": " | ".join(
                        str(message.get("text", "")) for message in messages if message.get("text")
                    ),
                    "user_id": memory_user_id,
                },
            ),
        ]

    if plan.intent == "handle_alarm":
        alarm = plan.sub_items[0].payload
        return [
            _make_action("evaluate_ignore", {"alarm": alarm}),
            _make_action("alert_user", {"alarm": alarm}),
            _make_action("finalize_alarm", {"alarm": alarm}),
        ]

    if plan.intent == "write_diary":
        diary_payload = plan.sub_items[0].payload if plan.sub_items else {}
        summary = str(diary_payload.get("summary", diary_payload.get("message", "记录今天的经历")))
        date = str(diary_payload.get("date", time.strftime("%Y-%m-%d")))
        return [
            _make_action(
                "recall_memory",
                {
                    "query": "人际关系与近期重要事件",
                    "user_id": "__global__",
                },
            ),
            _make_action(
                "write_diary",
                {
                    "date": date,
                    "summary": summary,
                    "interactions": list(diary_payload.get("interactions", [])),
                    "reflections": str(diary_payload.get("reflections", "")),
                },
            ),
        ]

    return [_make_action("run_self_maintenance", {"intent": plan.intent})]


def _tool_call_to_action(call: LLMToolCall) -> Action:
    return _make_action(call.name, call.arguments)


def _make_action(tool_name: str, params: dict[str, object]) -> Action:
    return Action(
        id=str(uuid.uuid4()),
        tool_name=tool_name,
        params=params,
        energy_cost=ENERGY_COST_TABLE.get(tool_name, ENERGY_COST_TABLE["__default__"]),
    )


def _generate_self_maintenance_plan() -> None:
    plan = Plan(
        id=str(uuid.uuid4()),
        intent="self_maintenance",
        sub_items=[],
        priority=5.0,
        base_priority=5.0,
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
    payload = plan.sub_items[0].payload
    session_id = payload.get("session_id", payload.get("group_key"))
    return str(session_id) if session_id else None


def _actions_satisfy_plan(plan: Plan, actions: list[Action]) -> bool:
    tool_names = [action.tool_name for action in actions]
    if plan.intent == "handle_qq_messages":
        has_generation = "generate_response" in tool_names
        has_send = any(
            name in tool_names
            for name in {
                "send_console_message",
                "send_session_reply",
                "send_qq_message",
                "send_qq_private_message",
                "at_user_in_group",
            }
        )
        return has_generation and has_send
    if plan.intent == "handle_alarm":
        return "finalize_alarm" in tool_names
    if plan.intent == "write_diary":
        return "write_diary" in tool_names
    return bool(actions)


def _has_tool(name: str) -> bool:
    return any(tool.name == name for tool in get_all())


def _make_episode_followup_actions(
    plan: Plan,
    messages: list[dict[str, object]],
) -> list[Action]:
    latest_text = str(messages[-1].get("text", "")).strip()
    if not latest_text:
        return []

    related_episodes = _load_related_episodes(plan)
    if related_episodes and _looks_like_resolution(latest_text):
        episode = related_episodes[0]
        return [
            _make_action(
                "close_episode",
                {
                    "episode_id": episode.id,
                    "summary": latest_text[:120],
                },
            )
        ]

    if not related_episodes and _looks_like_pending_episode(latest_text):
        participants = _extract_episode_participants(messages)
        if not participants:
            return []
        summary = f"跟进 {participants[0]} 关于: {latest_text[:60]}"
        session_id = str(messages[-1].get("session_id", participants[0]))
        return [
            _make_action(
                "create_episode",
                {
                    "summary": summary,
                    "participants": participants,
                    "pending_on": "等待对方回应或事情结果",
                    "notify": f"session:{session_id}",
                },
            )
        ]
    return []


def _extract_episode_participants(messages: list[dict[str, object]]) -> list[str]:
    participants: list[str] = []
    for message in messages:
        user_id = message.get("user_id")
        if user_id is not None and str(user_id).strip():
            participants.append(str(user_id))
    return list(dict.fromkeys(participants))


def _looks_like_pending_episode(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "?",
        "？",
        "吗",
        "能不能",
        "可以吗",
        "要不要",
        "一起",
        "记得",
        "等你",
        "回头",
        "稍后",
    ]
    return any(marker in lowered for marker in markers)


def _looks_like_resolution(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "好",
        "好的",
        "行",
        "可以",
        "收到",
        "完成",
        "搞定",
        "写完",
        "确认",
        "ok",
        "安排上",
    ]
    return any(marker in lowered for marker in markers)
