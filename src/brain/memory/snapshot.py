from __future__ import annotations

import time

from src.brain.memory.semantic import semantic_memory
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("SemanticSnapshot")


class SemanticSnapshot:
    def __init__(self) -> None:
        self._cache = ""
        self._updated_at = 0.0
        self._last_refresh_started_at = 0.0
        self._load()

    def get(self) -> str:
        return self._cache

    def should_refresh(self) -> bool:
        if self._updated_at <= 0:
            return True
        return (time.time() - self._updated_at) >= Config.SNAPSHOT_REFRESH_INTERVAL

    async def refresh(self, force: bool = False) -> str:
        now = time.time()
        if (
            not force
            and self._last_refresh_started_at > 0
            and (now - self._last_refresh_started_at) < Config.SNAPSHOT_REFRESH_DEBOUNCE_SECONDS
        ):
            return self._cache

        self._last_refresh_started_at = now
        memories = await semantic_memory.get_all(user_id="__global__")
        lines = ["## Semantic snapshot"]
        for item in memories[:20]:
            memory = str(item.get("memory", item.get("content", ""))).strip()
            if memory:
                lines.append(f"- {memory}")
        self._cache = "\n".join(lines) if len(lines) > 1 else "## Semantic snapshot\n- empty"
        self._updated_at = time.time()
        Config.SEMANTIC_SNAPSHOT_FILE.write_text(self._cache, encoding="utf-8")
        logger.info("Snapshot refreshed with %s entries", len(memories))
        return self._cache

    def _load(self) -> None:
        if not Config.SEMANTIC_SNAPSHOT_FILE.exists():
            return
        try:
            self._cache = Config.SEMANTIC_SNAPSHOT_FILE.read_text(encoding="utf-8-sig")
            self._updated_at = Config.SEMANTIC_SNAPSHOT_FILE.stat().st_mtime
        except Exception:
            self._cache = ""
            self._updated_at = 0.0


memory_snapshot = SemanticSnapshot()
