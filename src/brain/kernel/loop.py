from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

from src.brain.kernel.agent_base import Agent, AgentProposal, AgentResult
from src.brain.kernel.agent_factory import build_agent
from src.utils.log_utils import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("AgentLoop")
MAX_AGENT_STEPS_PER_TICK = 8
DEFAULT_AGENT_KEYS = ("plan", "expand", "execute")


async def run_agent_loop(
    host: "ApplicationHost",
    stop_event: asyncio.Event,
    interval: float,
) -> None:
    logger.info("内核循环已启动")
    agents = [build_agent(agent_key, host) for agent_key in DEFAULT_AGENT_KEYS]
    logger.info(
        f"内核已装配 Agents: {', '.join(agent.name for agent in agents) or '<none>'}"
    )

    while not stop_event.is_set():
        try:
            await _run_kernel_tick(agents)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"内核调度错误: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.05, interval))
        except asyncio.TimeoutError:
            continue


async def _run_kernel_tick(agents: list[Agent]) -> None:
    for _ in range(MAX_AGENT_STEPS_PER_TICK):
        selected = _select_next_agent(agents)
        if selected is None:
            return

        agent, proposal = selected
        logger.info(
            f"内核选择 Agent {agent.name}: priority={proposal.priority}, "
            f"reason={proposal.reason or '-'}"
        )

        result = await agent.step(proposal)
        logger.info(
            f"Agent执行完成: {agent.name}, handled={result.handled}, "
            f"events={result.events_consumed}, "
            f"commands={result.commands_succeeded}/{result.commands_attempted}, "
            f"summary={result.summary or '-'}"
        )

        if _is_idle_result(result):
            return


def _select_next_agent(agents: list[Agent]) -> tuple[Agent, AgentProposal] | None:
    proposals: list[tuple[Agent, AgentProposal]] = []

    for agent in agents:
        try:
            proposal = agent.propose()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Agent提案失败: {agent.name}, error={exc}")
            continue
        if proposal is None:
            continue
        proposals.append((agent, proposal))

    if not proposals:
        return None

    proposals.sort(key=lambda item: item[1].priority, reverse=True)
    return proposals[0]


def _is_idle_result(result: AgentResult) -> bool:
    return (
        not result.handled
        and result.events_consumed == 0
        and result.commands_attempted == 0
    )
