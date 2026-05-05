from __future__ import annotations

import time
import uuid

import src.brain.core.queues as queues
from src.brain.core.models import Action, Attention, AttentionState, Plan
from src.brain.core.state import bot_state
from src.config import Config

ENERGY_COST_TABLE = {
    "recall_memory": 2.0,
    "generate_response": 8.0,
    "send_console_message": 2.0,
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

    actions = _expand_plan(plan)
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


def _expand_plan(plan: Plan) -> list[Action]:
    if plan.intent == "handle_qq_messages":
        session_id = str(plan.sub_items[0].payload.get("session_id", "demo-session"))
        messages = [item.payload for item in plan.sub_items]
        latest_text = str(messages[-1].get("text", ""))
        memory_user_id = str(
            messages[-1].get("user_id", messages[-1].get("session_id", "__global__"))
        )
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
