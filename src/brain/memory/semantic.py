from __future__ import annotations

import json
import time
from pathlib import Path

from src.config import Config


class SemanticMemory:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or Config.SEMANTIC_MEMORY_FILE
        self._entries: list[dict[str, object]] = []
        self._load()

    async def add(self, content: str, user_id: str) -> dict[str, object]:
        entry = {
            "content": str(content),
            "user_id": str(user_id),
            "created_at": time.time(),
        }
        self._entries.append(entry)
        self._save()
        return entry

    async def search(self, query: str, user_id: str) -> list[str]:
        query_terms = [term for term in str(query).lower().split() if term]
        user_id = str(user_id)
        matched: list[str] = []
        for entry in reversed(self._entries):
            if user_id not in {"__global__", str(entry.get("user_id", ""))}:
                continue
            content = str(entry.get("content", ""))
            lowered = content.lower()
            if not query_terms or any(term in lowered for term in query_terms):
                matched.append(content)
            if len(matched) >= 5:
                break
        return matched

    async def update_relationship(
        self,
        user_a: str,
        user_b: str,
        relation: str,
    ) -> dict[str, object]:
        relation_text = f"关系更新: {user_a} <-> {user_b} = {relation}"
        return await self.add(relation_text, user_id="__global__")

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8-sig"))
            self._entries = list(payload.get("entries", []))
        except Exception:
            self._entries = []

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": time.time(),
            "entries": self._entries,
        }
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


semantic_memory = SemanticMemory()
