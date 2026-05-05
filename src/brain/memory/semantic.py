from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("SemanticMemory")


class SemanticMemory:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or Config.SEMANTIC_MEMORY_FILE
        self._entries: list[dict[str, object]] = []
        self._load()

    async def add(
        self,
        content: str,
        user_id: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        entry = {
            "content": str(content),
            "user_id": str(user_id),
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self._entries.append(entry)
        self._save()
        try:
            await self._add_remote(entry)
        except Exception as exc:
            logger.warning("[SemanticMemory] Remote add failed, fallback to local only: %s", exc)
        return entry

    async def search(self, query: str, user_id: str) -> list[str]:
        try:
            return await self._search_remote(query=query, user_id=user_id)
        except Exception as exc:
            logger.warning(
                "[SemanticMemory] Remote search failed, fallback to local only: %s",
                exc,
            )
            return self._search_local(query=query, user_id=user_id)

    async def get_all(self, user_id: str) -> list[dict[str, object]]:
        try:
            return await self._get_all_remote(user_id=user_id)
        except Exception as exc:
            logger.warning(
                "[SemanticMemory] Remote get_all failed, fallback to local only: %s",
                exc,
            )
            return self._get_all_local(user_id=user_id)

    async def update_relationship(
        self,
        user_a: str,
        user_b: str,
        relation: str,
    ) -> dict[str, object]:
        relation_text = f"关系更新: {user_a} <-> {user_b} = {relation}"
        return await self.add(
            relation_text,
            user_id="__global__",
            metadata={"kind": "relationship"},
        )

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

    async def _add_remote(self, entry: dict[str, object]) -> dict[str, object]:
        payload = {
            "messages": [{"role": "user", "content": str(entry["content"])}],
            "user_id": str(entry["user_id"]),
            "metadata": entry.get("metadata", {}),
        }
        return await asyncio.to_thread(
            self._request_json,
            "POST",
            "/v3/memories/add/",
            payload,
        )

    async def _search_remote(self, query: str, user_id: str) -> list[str]:
        payload = {
            "query": str(query),
            "user_id": str(user_id),
            "top_k": 5,
        }
        response = await asyncio.to_thread(
            self._request_json,
            "POST",
            "/v1/memories/search/",
            payload,
        )
        results = self._extract_results(response)
        return [
            str(item.get("memory", ""))
            for item in results
            if str(item.get("memory", "")).strip()
        ]

    async def _get_all_remote(self, user_id: str) -> list[dict[str, object]]:
        query = urllib.parse.urlencode({"user_id": str(user_id)})
        response = await asyncio.to_thread(
            self._request_json,
            "GET",
            f"/v1/memories/?{query}",
            None,
        )
        return self._extract_results(response)

    def _search_local(self, query: str, user_id: str) -> list[str]:
        query_terms = [term for term in str(query).lower().split() if term]
        matched: list[str] = []
        for entry in reversed(self._get_all_local(user_id=user_id)):
            content = str(entry.get("content", ""))
            lowered = content.lower()
            if not query_terms or any(term in lowered for term in query_terms):
                matched.append(content)
            if len(matched) >= 5:
                break
        return matched

    def _get_all_local(self, user_id: str) -> list[dict[str, object]]:
        normalized_user_id = str(user_id)
        return [
            entry
            for entry in self._entries
            if normalized_user_id == "__global__"
            or str(entry.get("user_id", "")) == normalized_user_id
            or str(entry.get("user_id", "")) == "__global__"
        ]

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{Config.MEM0_API_BASE_URL.rstrip('/')}{path}"
        data = None
        headers = {
            "Authorization": f"Token {Config.MEM0_API_KEY}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Mem0 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Mem0 network error: {exc}") from exc
        return json.loads(body) if body else {}

    def _extract_results(
        self,
        response: dict[str, Any] | list[dict[str, Any]],
    ) -> list[dict[str, object]]:
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        if isinstance(response, dict):
            results = response.get("results", [])
            if isinstance(results, list):
                return [item for item in results if isinstance(item, dict)]
        return []


semantic_memory = SemanticMemory()
