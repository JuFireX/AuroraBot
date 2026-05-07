from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ApplicationProtocol(Protocol):
    def manifest_path(self) -> Path: ...

    async def on_start(self) -> None: ...

    async def on_stop(self) -> None: ...

    async def on_tick(self) -> None: ...
