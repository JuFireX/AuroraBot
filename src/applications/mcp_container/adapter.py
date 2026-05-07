from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.brain.platform.application_api import PlatformAPI

logger = get_logger("MCPContainer")


class MCPContainer:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None
        self._servers: list[dict[str, Any]] = []

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        self._servers = self._load_server_configs()
        logger.info("MCP container loaded %s server configs", len(self._servers))

    async def on_stop(self) -> None:
        return None

    async def on_tick(self) -> None:
        return None

    def _load_server_configs(self) -> list[dict[str, Any]]:
        api = self._require_api()
        data_file = api.data_dir / "servers.yaml"
        bundled_file = Path(__file__).with_name("servers.yaml")
        if not data_file.exists() and bundled_file.exists():
            data_file.write_text(bundled_file.read_text(encoding="utf-8-sig"), encoding="utf-8")
        if not data_file.exists():
            return []
        try:
            payload = json.loads(data_file.read_text(encoding="utf-8-sig"))
        except Exception:
            return []
        servers = payload.get("servers", [])
        return [item for item in servers if isinstance(item, dict)]

    def _require_api(self) -> "PlatformAPI":
        if self._api is None:
            raise RuntimeError("MCPContainer is not bound to PlatformAPI")
        return self._api
