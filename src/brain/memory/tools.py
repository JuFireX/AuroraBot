from __future__ import annotations

import time
import uuid

from src.brain.core.models import Episode
from src.brain.core.tool_registry import Tool, register
from src.brain.memory.episodic import episode_store
from src.brain.memory.semantic import semantic_memory


def register_memory_tools() -> None:
    register(
        Tool(
            name="recall_memory",
            description="从长期记忆中检索与当前人物或话题相关的信息",
            parameters_schema=_object_schema("query", "user_id"),
            handler=_recall_memory,
        )
    )
    register(
        Tool(
            name="store_memory",
            description="将本次交互中值得记住的信息写入长期记忆",
            parameters_schema=_object_schema("content", "user_id"),
            handler=_store_memory,
        )
    )
    register(
        Tool(
            name="update_relationship",
            description="更新两个人之间的关系状态",
            parameters_schema=_object_schema("user_a", "user_b", "relation"),
            handler=_update_relationship,
        )
    )
    register(
        Tool(
            name="create_episode",
            description="创建一个新的挂起情节，追踪尚未有结果的事件",
            parameters_schema=_episode_create_schema(),
            handler=_create_episode,
        )
    )
    register(
        Tool(
            name="close_episode",
            description="关闭一个已有结果的挂起情节",
            parameters_schema=_object_schema("episode_id", "summary"),
            handler=_close_episode,
        )
    )


async def _recall_memory(query: str, user_id: str) -> list[str]:
    return await semantic_memory.search(query=query, user_id=user_id)


async def _store_memory(content: str, user_id: str) -> dict[str, object]:
    return await semantic_memory.add(content=content, user_id=user_id)


async def _update_relationship(
    user_a: str,
    user_b: str,
    relation: str,
) -> dict[str, object]:
    return await semantic_memory.update_relationship(
        user_a=user_a,
        user_b=user_b,
        relation=relation,
    )


def _create_episode(
    summary: str,
    participants: list[str],
    pending_on: str | None = None,
    notify: str | None = None,
) -> dict[str, object]:
    episode = Episode(
        id=str(uuid.uuid4()),
        summary=summary,
        participants=[str(item) for item in participants],
        pending_on=pending_on,
        notify=notify,
        created_at=time.time(),
    )
    episode_store.create(episode)
    return {"episode_id": episode.id, "status": "created"}


def _close_episode(episode_id: str, summary: str) -> dict[str, object]:
    episode = episode_store.close(episode_id=episode_id, summary=summary)
    return {"episode_id": episode_id, "status": "closed" if episode else "missing"}


def _object_schema(*required_fields: str) -> dict[str, object]:
    properties = {field: {"type": "string"} for field in required_fields}
    return {
        "type": "object",
        "properties": properties,
        "required": list(required_fields),
    }


def _episode_create_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "participants": {"type": "array", "items": {"type": "string"}},
            "pending_on": {"type": "string"},
            "notify": {"type": "string"},
        },
        "required": ["summary", "participants"],
    }
