from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from src.brain.core.models import Episode, EpisodeStatus
from src.config import Config


class EpisodeStore:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or Config.EPISODIC_MEMORY_FILE
        self._episodes: dict[str, Episode] = {}
        self._load()

    def create(self, episode: Episode) -> Episode:
        self._episodes[episode.id] = episode
        self._save()
        return episode

    def close(self, episode_id: str, summary: str | None = None) -> Episode | None:
        episode = self._episodes.get(episode_id)
        if episode is None:
            return None
        if summary:
            episode.summary = summary
        episode.status = EpisodeStatus.CLOSED
        episode.closed_at = time.time()
        self._save()
        return episode

    def get(self, episode_id: str) -> Episode | None:
        return self._episodes.get(episode_id)

    def get_all_pending(self) -> list[Episode]:
        return [
            episode
            for episode in self._episodes.values()
            if episode.status == EpisodeStatus.PENDING
        ]

    def get_all(self) -> list[Episode]:
        return list(self._episodes.values())

    def find_pending_by_participants(self, participants: list[str]) -> list[Episode]:
        participant_set = {str(item) for item in participants if str(item).strip()}
        if not participant_set:
            return []
        return [
            episode
            for episode in self.get_all_pending()
            if participant_set.intersection(set(episode.participants))
        ]

    def find_similar_pending(
        self,
        summary: str,
        participants: list[str],
    ) -> Episode | None:
        summary_key = _normalize_text(summary)
        participant_set = {str(item) for item in participants if str(item).strip()}
        for episode in self.get_all_pending():
            if set(episode.participants) != participant_set:
                continue
            if _normalize_text(episode.summary) == summary_key:
                return episode
        return None

    def clear(self) -> None:
        self._episodes.clear()
        self._save()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8-sig"))
            for item in payload.get("episodes", []):
                episode = Episode(
                    id=str(item.get("id", "")),
                    summary=str(item.get("summary", "")),
                    participants=[str(p) for p in item.get("participants", [])],
                    status=EpisodeStatus(str(item.get("status", EpisodeStatus.PENDING.value))),
                    pending_on=(
                        str(item.get("pending_on"))
                        if item.get("pending_on") is not None
                        else None
                    ),
                    notify=(
                        str(item.get("notify"))
                        if item.get("notify") is not None
                        else None
                    ),
                    created_at=float(item.get("created_at", 0.0)),
                    closed_at=(
                        float(item.get("closed_at"))
                        if item.get("closed_at") is not None
                        else None
                    ),
                )
                self._episodes[episode.id] = episode
        except Exception:
            self._episodes = {}

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": time.time(),
            "episodes": [asdict(episode) for episode in self._episodes.values()],
        }
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


episode_store = EpisodeStore()


def _normalize_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())
