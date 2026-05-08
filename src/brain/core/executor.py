# ------------------------------------------------------------
# @author: Churk
# @status: 待完善
# @description: 计划执行器模块, 理想功能是由LLM根据计划执行动作
#
# executor的理想功能是根据actions队列的action, 执行动作. 这个模块其实确实是越简单越好, 但是目前缺乏校验和错误回馈, 补偿机制.
# ------------------------------------------------------------


from __future__ import annotations

import time

import src.brain.core.queues as queues
from src.brain.core import capability_registry
from src.brain.core.models import ActionStatus, AttentionState, PlanStatus
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("Executor")


async def run() -> int:
    executed = 0
    while not queues.actions_queue.empty() and executed < Config.MAX_ACTIONS_PER_BEAT:
        action = queues.actions_queue.peek()
        if action is None:
            break
        queues.actions_queue.pop()
        action.started_at = time.time()
        action.status = ActionStatus.RUNNING
        queues.actions_queue.update(action)
        try:
            _validate_action(action)
            if Config.CAPABILITY_LOG_EXECUTION:
                logger.info(
                    "[Capability Execute] plan=%s action=%s capability=%s params=%s",
                    action.plan_id,
                    action.id,
                    action.capability_name,
                    _clip_log_text(str(action.params)),
                )
            result = await capability_registry.call(
                action.capability_name, action.params
            )
            action.status = ActionStatus.SUCCEEDED
            action.result_summary = _summarize_result(result)
            action.error_message = ""
            if Config.CAPABILITY_LOG_EXECUTION:
                logger.info(
                    "[Capability Result] action=%s capability=%s result=%s",
                    action.id,
                    action.capability_name,
                    _clip_log_text(action.result_summary),
                )
        except Exception as exc:  # noqa: BLE001
            action.status = ActionStatus.FAILED
            action.error_message = str(exc)
            logger.error(f"执行动作 {action.capability_name} 失败: {exc}")
        finally:
            action.finished_at = time.time()
            queues.actions_queue.update(action)
            executed += 1
            _advance_attention(action)
    return executed


def _validate_action(action: object) -> None:
    if not hasattr(action, "capability_name") or not hasattr(action, "params"):
        raise TypeError("无效的 Action 对象")
    if not capability_registry.get(getattr(action, "capability_name")):
        raise KeyError(
            f"Capability '{getattr(action, 'capability_name')}' not registered"
        )


def _summarize_result(result: object) -> str:
    if result is None:
        return "ok"
    if isinstance(result, dict):
        return (
            ", ".join(f"{key}={value}" for key, value in list(result.items())[:3])
            or "ok"
        )
    return str(result)[:120]


def _clip_log_text(text: str) -> str:
    limit = max(120, Config.LLM_LOG_MAX_CHARS // 2)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _advance_attention(action) -> None:
    attention = queues.current_attention
    if attention is None:
        return
    attention.current_index += 1
    attention.last_advanced_at = time.time()
    plan = queues.plans_queue.get(attention.plan_id)
    if action.status == ActionStatus.FAILED:
        attention.state = AttentionState.FAILED
        if plan is not None:
            plan.status = PlanStatus.BLOCKED
            plan.last_error = action.error_message
            plan.last_touched_at = time.time()
            queues.plans_queue.push(plan)
        queues.clear_current_attention()
        return
    if attention.current_index >= len(attention.action_ids):
        attention.state = AttentionState.COMPLETED
        if plan is not None:
            plan.status = PlanStatus.COMPLETED
            plan.last_error = ""
            plan.last_touched_at = time.time()
            queues.plans_queue.push(plan)
        queues.todo_queue.mark_done(attention.source_todo_ids)
        queues.actions_queue.remove_pending_ids(attention.action_ids)
        queues.clear_current_attention()
