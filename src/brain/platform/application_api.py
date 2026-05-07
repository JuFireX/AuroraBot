from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.brain.core.capability_registry import CapabilitySpec, register
from src.brain.core.queues import todo_queue
from src.config import Config
from src.utils.Logger import get_logger

if TYPE_CHECKING:
    from src.brain.core.models import TodoItem
    from src.brain.platform.application_host import ApplicationHost
    from src.brain.platform.manifest import Manifest


class PlatformAPI:
    def __init__(self, manifest: "Manifest", host: "ApplicationHost") -> None:
        self._manifest = manifest
        self._host = host
        self._logger = get_logger(f"AppAPI:{manifest.package}")

    def post_intention(self, item: "TodoItem") -> None:
        todo_queue.push(item)

    def register_capability(self, spec: CapabilitySpec) -> None:
        register(spec)

    def get_persona(self) -> str:
        soul_path = Config.PROMPTS_DIR / "SOUL.md"
        return soul_path.read_text(encoding="utf-8-sig").strip() if soul_path.exists() else ""

    def log(self, level: str, message: str) -> None:
        log_method = getattr(self._logger, level, self._logger.info)
        log_method(message)

    @property
    def data_dir(self) -> Path:
        path = Config.APP_DATA_DIR / self._manifest.package.replace(".", "_")
        path.mkdir(parents=True, exist_ok=True)
        return path
