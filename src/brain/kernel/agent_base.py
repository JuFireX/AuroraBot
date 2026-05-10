from __future__ import annotations

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost


@dataclass(slots=True)
class AgentProposal:
    priority: int = 0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    handled: bool = False
    summary: str = ""
    events_consumed: int = 0
    commands_attempted: int = 0
    commands_succeeded: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    def __init__(self, host: "ApplicationHost") -> None:
        self._host = host

    @property
    def host(self) -> "ApplicationHost":
        return self._host

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def propose(self) -> AgentProposal | None:
        raise NotImplementedError

    @abstractmethod
    async def step(self, proposal: AgentProposal) -> AgentResult:
        raise NotImplementedError
