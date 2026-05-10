from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.platform.contracts import AppEvent
from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI


logger = get_logger("TestApplication")


class TestApplication:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        logger.info("Test application started")

    async def on_stop(self) -> None:
        logger.info("Test application stopped")

    async def on_tick(self) -> None:
        return None

    def test_command_a_plus_b(self, a: int, b: int) -> dict[str, Any]:
        if self._api is not None:
            self._api.emit_event(
                AppEvent(
                    source=self._api.package,
                    type="test.command.a_plus_b",
                    summary="a_plus_b",
                    payload={"a": a, "b": b},
                )
            )
        return {"success": True, "res": a + b}

    def test_command_a_minus_b(self, a: int, b: int) -> dict[str, Any]:
        if self._api is not None:
            self._api.emit_event(
                AppEvent(
                    source=self._api.package,
                    type="test.command.a_minus_b",
                    summary="a_minus_b",
                    payload={"a": a, "b": b},
                )
            )
        return {"success": True, "res": a - b}
