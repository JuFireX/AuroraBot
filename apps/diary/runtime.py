from __future__ import annotations
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.platform.contracts import AppEvent
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI

logger = get_logger("DiaryApplication")


class DiaryApplication:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None
        self._diary_file: Path | None = None
        self._records: list[dict[str, Any]] = []

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api
        self._diary_file = api.data_dir / "diaries.json"

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        self._load()
        logger.info("Diary application started")

    async def on_stop(self) -> None:
        self._save()
        logger.info("Diary application stopped")

    async def on_tick(self) -> None:
        return None

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
            "created_at": now_text(),
        }
        self._records.append(record)
        self._save()
        if self._api is not None:
            self._api.emit_event(
                AppEvent(
                    source=self._api.package,
                    type="diary.written",
                    summary=summary.strip(),
                    payload=record,
                )
            )
        return {"saved": True, "record_count": len(self._records)}

    def _load(self) -> None:
        if self._diary_file is None or not self._diary_file.exists():
            return
        try:
            loaded = json.loads(self._diary_file.read_text(encoding="utf-8-sig"))
            self._records = [dict(item) for item in loaded if isinstance(item, dict)]
        except Exception:
            self._records = []

    def _save(self) -> None:
        if self._diary_file is None:
            return
        self._diary_file.parent.mkdir(parents=True, exist_ok=True)
        self._diary_file.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
