from __future__ import annotations

from typing import TYPE_CHECKING

from src.brain.kernel.agent_base import Agent
from src.brain.agents import *

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

AGENT_REGISTRY: dict[str, type[Agent]] = {
    "test": TestAgent,
    "example": TestAgent,
    "alpha": TestAgent,
}


# 构造指定智能体实例
def build_agent(agent_key: str, host: "ApplicationHost") -> Agent:
    return AGENT_REGISTRY[agent_key](host)
