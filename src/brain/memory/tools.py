from __future__ import annotations

import time
import uuid

from src.brain.core.capability_registry import CapabilitySpec, register
from src.brain.core.models import Episode
from src.brain.memory.episodic import episode_store
from src.brain.memory.semantic import semantic_memory


def register_memory_capabilities() -> None:
    register(
        CapabilitySpec(
            name="memory.recall",
            description="Recall relevant long-term memory for the current topic or person.",
            parameters_schema=_object_schema("query", "user_id"),
            returns_schema={"type": "array", "items": {"type": "string"}},
            side_effects=[],
            handler=_recall_memory,
        )
    )
    register(
        CapabilitySpec(
            name="memory.store",
            description="Store something worth remembering into long-term memory.",
            parameters_schema=_object_schema("content", "user_id"),
            returns_schema={"type": "object", "properties": {"content": {"type": "string"}}},
            side_effects=["Writes to semantic memory storage"],
            handler=_store_memory,
        )
    )
    register(
        CapabilitySpec(
            name="memory.update_relationship",
            description="Update a relationship memory between two people.",
            parameters_schema=_object_schema("user_a", "user_b", "relation"),
            returns_schema={"type": "object", "properties": {"content": {"type": "string"}}},
            side_effects=["Writes relationship state to semantic memory"],
            handler=_update_relationship,
        )
    )
    register(
        CapabilitySpec(
            name="episode.create",
            description="Create a new pending episode that should be tracked later.",
            parameters_schema=_episode_create_schema(),
            returns_schema={"type": "object", "properties": {"episode_id": {"type": "string"}}},
            side_effects=["Writes episode state to local storage"],
            handler=_create_episode,
        )
    )
    register(
        CapabilitySpec(
            name="episode.close",
            description="Close an existing pending episode once there is an outcome.",
            parameters_schema=_object_schema("episode_id", "summary"),
            returns_schema={"type": "object", "properties": {"episode_id": {"type": "string"}}},
            side_effects=["Updates episode state to closed"],
            handler=_close_episode,
        )
    )


async def _recall_memory(query: str, user_id: str) -> list[str]:
    return await semantic_memory.search(query=query, user_id=user_id)


async def _store_memory(content: str, user_id: str) -> dict[str, object]:
    return await semantic_memory.add(content=content, user_id=user_id)


async def _update_relationship(user_a: str, user_b: str, relation: str) -> dict[str, object]:
    return await semantic_memory.update_relationship(
        user_a=user_a,
        user_b=user_b,
        relation=relation,
    )


def _create_episode(summary: str, participants: list[str], pending_on: str | None = None) -> dict[str, object]:
    normalized_participants = [str(item) for item in participants if str(item).strip()]
    existing = episode_store.find_similar_pending(summary=summary, participants=normalized_participants)
    if existing is not None:
        return {"episode_id": existing.id, "status": "existing"}
    episode = Episode(
        id=str(uuid.uuid4()),
        summary=summary,
        participants=normalized_participants,
        pending_on=pending_on,
        created_at=time.time(),
    )
    episode_store.create(episode)
    return {"episode_id": episode.id, "status": "created"}


def _close_episode(episode_id: str, summary: str) -> dict[str, object]:
    episode = episode_store.close(episode_id=episode_id, summary=summary)
    return {"episode_id": episode_id, "status": "closed" if episode else "missing"}


def _object_schema(*required_fields: str) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {field: {"type": "string"} for field in required_fields},
        "required": list(required_fields),
    }


def _episode_create_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "participants": {"type": "array", "items": {"type": "string"}},
            "pending_on": {"type": "string"},
        },
        "required": ["summary", "participants"],
    }
