from __future__ import annotations
from typing import Any, TYPE_CHECKING

from src.brain.kernel.agent_base import Agent, AgentProposal, AgentResult
from src.brain.kernel.state_store import kernel_file, load_json_list, save_json_list
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("ExecuteAgent")


class ExecuteAgent(Agent):
    def __init__(
        self,
        host: "ApplicationHost",
        *,
        max_actions_per_step: int = 4,
    ) -> None:
        super().__init__(host)
        self._max_actions_per_step = max(1, max_actions_per_step)
        self._plans_file = kernel_file("plans.json")
        self._actions_file = kernel_file("actions.json")

    def propose(self) -> AgentProposal | None:
        actions = load_json_list(self._actions_file)
        pending_count = sum(
            1 for action in actions if action.get("status") == "pending"
        )
        if pending_count == 0:
            return None
        return AgentProposal(
            priority=min(90, pending_count + 40),
            reason=f"待执行 action {pending_count} 个",
            metadata={"action_count": pending_count, "stage": "execute"},
        )

    async def step(self, proposal: AgentProposal) -> AgentResult:
        actions = load_json_list(self._actions_file)
        plans = load_json_list(self._plans_file)
        pending_actions = [
            action for action in actions if action.get("status") == "pending"
        ][: self._max_actions_per_step]
        if not pending_actions:
            return AgentResult(summary="提案时有 action, 执行时已无待执行项")

        attempted = 0
        succeeded = 0
        for action in pending_actions:
            attempted += 1
            action["status"] = "running"
            action["updated_at"] = now_text()
            try:
                result = await self.host.invoke_command(
                    str(action.get("command", "")),
                    **self._normalize_kwargs(action.get("kwargs")),
                )
                action["status"] = "done"
                action["result"] = result
                action["updated_at"] = now_text()
                succeeded += 1
                self._update_plan_status(plans, str(action.get("plan_id", "")), "done")
                logger.info(f"命令执行完成: {action.get('command')} -> {result}")
            except Exception as exc:  # noqa: BLE001
                action["status"] = "failed"
                action["error"] = str(exc)
                action["updated_at"] = now_text()
                self._update_plan_status(
                    plans, str(action.get("plan_id", "")), "failed"
                )
                logger.warning(f"命令执行失败: {action.get('command')}, error={exc}")

        save_json_list(self._actions_file, actions)
        save_json_list(self._plans_file, plans)

        return AgentResult(
            handled=attempted > 0,
            summary=f"执行了 {attempted} 个 action",
            commands_attempted=attempted,
            commands_succeeded=succeeded,
            metadata={
                "proposal": proposal.metadata,
                "actions_failed": attempted - succeeded,
            },
        )

    def _normalize_kwargs(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _update_plan_status(
        self,
        plans: list[dict[str, Any]],
        plan_id: str,
        status: str,
    ) -> None:
        if not plan_id:
            return
        for plan in plans:
            if plan.get("id") != plan_id:
                continue
            plan["status"] = status
            plan["updated_at"] = now_text()
            return
