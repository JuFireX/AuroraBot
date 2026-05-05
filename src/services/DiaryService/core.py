from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.brain.core.tool_registry import Tool, register
from src.brain.memory.snapshot import memory_snapshot
from src.brain.memory.semantic import semantic_memory
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("DiaryService")


class DiaryService:
    def __init__(self) -> None:
        self._registered = False
        self._diary_file = Config.DIARY_DATA_DIR / "diaries.json"
        self._records: list[dict[str, Any]] = []

    async def start(self) -> None:
        self._load()
        if not self._registered:
            register(
                Tool(
                    name="write_diary",
                    description="将当天经历、互动和反思写入结构化日记，并刷新语义记忆快照",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "summary": {"type": "string"},
                            "interactions": {"type": "array", "items": {"type": "string"}},
                            "reflections": {"type": "string"},
                        },
                        "required": ["date", "summary"],
                    },
                    handler=self.write_diary,
                )
            )
            self._registered = True
        logger.info("[DiaryService] Started")

    def stop(self) -> None:
        self._save()
        logger.info("[DiaryService] Stopped")

    async def write_diary(
        self,
        date: str,
        summary: str,
        interactions: list[str] | None = None,
        reflections: str | None = None,
    ) -> dict[str, object]:
        record = {
            "date": date,
            "summary": summary,
            "interactions": list(interactions or []),
            "reflections": reflections or "",
            "created_at": time.time(),
        }
        self._records.append(record)
        self._save()

        diary_text_parts = [f"日期: {date}", f"总结: {summary}"]
        if record["interactions"]:
            diary_text_parts.append("互动: " + " | ".join(record["interactions"]))
        if record["reflections"]:
            diary_text_parts.append("反思: " + str(record["reflections"]))

        await semantic_memory.add(
            content="\n".join(diary_text_parts),
            user_id="__global__",
            metadata={"kind": "diary", "date": date},
        )
        snapshot = await memory_snapshot.refresh()
        return {
            "status": "written",
            "date": date,
            "snapshot_length": len(snapshot),
        }

    def _load(self) -> None:
        if not self._diary_file.exists():
            return
        try:
            self._records = json.loads(self._diary_file.read_text(encoding="utf-8-sig"))
        except Exception:
            self._records = []

    def _save(self) -> None:
        self._diary_file.parent.mkdir(parents=True, exist_ok=True)
        self._diary_file.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


diary_service_instance = DiaryService()
