from __future__ import annotations

from typing import TYPE_CHECKING

from src.brain.kernel.agent_base import Agent
from src.brain.kernel.agents import *
from src.config import Config
from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("AgentFactory")

DEFAULT_AGENT_KEY = "example"
AGENT_REGISTRY: dict[str, type[Agent]] = {
    "test": TestAgent,
    "example": TestAgent,
    "alpha": TestAgent,
}


def build_host_agent(host: "ApplicationHost") -> Agent:
    configured_name = Config().KERNEL_AGENT.lower().strip()
    agent_key = configured_name or DEFAULT_AGENT_KEY
    agent_class = AGENT_REGISTRY.get(agent_key)

    if agent_class is None:
        fallback_class = AGENT_REGISTRY[DEFAULT_AGENT_KEY]
        logger.warning(f"未知 Agent 配置: {configured_name or '<empty>'}, 默认回退")
        agent_class = fallback_class
        agent_key = DEFAULT_AGENT_KEY

    agent = agent_class(host)

    logger.info(f"已选择 Agent 框架: {agent_class.__name__}")
    return agent
