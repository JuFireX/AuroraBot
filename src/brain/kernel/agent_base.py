from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("KernelAgent")


class Agent(ABC):
    def __init__(self, host: "ApplicationHost") -> None:
        self._host = host

    @property
    def host(self) -> "ApplicationHost":
        return self._host

    @abstractmethod
    async def tick(self) -> None:
        raise NotImplementedError
