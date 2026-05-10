from __future__ import annotations
from typing import TYPE_CHECKING

from src.brain.kernel.agent_base import Agent, AgentProposal, AgentResult
from src.brain.kernel.state_store import (
    kernel_file,
    load_json_list,
    next_record_id,
    save_json_list,
)
from src.platform.contracts import AppEvent
from src.utils.Logger import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("PlanAgent")


class PlanAgent(Agent):
    def __init__(
        self,
        host: "ApplicationHost",
        *,
        max_events_per_step: int = 4,
    ) -> None:
        super().__init__(host)
        self._max_events_per_step = max(1, max_events_per_step)
        self._plans_file = kernel_file("plans.json")

    def propose(self) -> AgentProposal | None:
        pending_events = self.host.peek_events()
        if not pending_events:
            return None
        return AgentProposal(
            priority=min(30, len(pending_events)),
            reason=f"待规划事件 {len(pending_events)} 个",
            metadata={"event_count": len(pending_events), "stage": "plan"},
        )

    async def step(self, proposal: AgentProposal) -> AgentResult:
        events = self.host.drain_events(limit=self._max_events_per_step)
        if not events:
            return AgentResult(summary="提案时有事件, 执行时事件队列为空")

        plans = load_json_list(self._plans_file)
        created = [self._build_plan(event) for event in events]
        plans.extend(created)
        save_json_list(self._plans_file, plans)

        logger.info(f"已生成 {len(created)} 个 plan")
        return AgentResult(
            handled=True,
            summary=f"新增 {len(created)} 个 plan",
            events_consumed=len(events),
            metadata={
                "proposal": proposal.metadata,
                "produced_plans": len(created),
            },
        )

    def _build_plan(self, event: AppEvent) -> dict[str, object]:
        timestamp = now_text()
        return {
            "id": next_record_id("plan"),
            "source_event_id": event.id,
            "source_event_type": event.type,
            "source": event.source,
            "session_id": event.session_id,
            "goal": event.summary or f"处理事件 {event.type}",
            "summary": event.summary,
            "payload": event.payload,
            "status": "pending",
            "priority": 50,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
