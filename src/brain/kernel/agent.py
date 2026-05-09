from __future__ import annotations

from abc import ABC, abstractmethod


class Agent(ABC):
    @abstractmethod
    @asyncio.coroutine
    async def tick(self) -> None:
        pass
