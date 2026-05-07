from __future__ import annotations

import json
from pathlib import Path

from src.brain.core.capability_registry import get_all_schemas
from src.brain.core.models import Episode, Plan
from src.brain.core.session import Message, session_buffer
from src.brain.core.state import bot_state
from src.brain.memory.snapshot import memory_snapshot
from src.config import Config

_APP_HINTS: dict[str, str] = {}


def register_app_hint(package: str, hint: str) -> None:
    _APP_HINTS[package] = hint


def reset_app_hints() -> None:
    _APP_HINTS.clear()


class ContextBuilder:
    def __init__(self) -> None:
        self._prompt_cache: dict[Path, str] = {}

    async def build_system(self, related_episodes: list[Episode]) -> str:
        if memory_snapshot.should_refresh():
            await memory_snapshot.refresh()
        parts = [
            self._prompt("PLAN.md"),
            self._prompt("SOUL.md"),
            self._capability_block(),
            self._app_hints_block(),
            self._semantic_snapshot(),
            self._episodes_block(related_episodes),
            self._bot_state_block(),
        ]
        return "\n\n---\n\n".join(part for part in parts if part.strip())

    def build_user(self, plan: Plan, session_id: str | None = None) -> str:
        parts = [
            f"Current intent: {plan.intent}",
            f"Priority: {plan.priority:.1f}",
        ]
        if plan.sub_items:
            items_payload = [item.payload for item in plan.sub_items]
            parts.append("Items:")
            parts.append(json.dumps(items_payload, ensure_ascii=False, indent=2))
        if plan.related_episodes:
            parts.append("Related episode ids: " + ", ".join(plan.related_episodes))
        if session_id:
            context = session_buffer.get_context(session_id)
            if context:
                parts.append("Recent conversation:")
                parts.append(self._format_messages(context))
        return "\n".join(parts)

    def _prompt(self, filename: str) -> str:
        path = Config.PROMPTS_DIR / filename
        if path not in self._prompt_cache:
            self._prompt_cache[path] = (
                path.read_text(encoding="utf-8-sig").strip() if path.exists() else ""
            )
        return self._prompt_cache[path]

    def _capability_block(self) -> str:
        schemas = get_all_schemas()
        if not schemas:
            return ""
        lines = ["## Available capabilities"]
        for schema in schemas:
            lines.append(
                "- "
                + str(schema["name"])
                + ": "
                + str(schema.get("description", "")).strip()
                + " | parameters="
                + json.dumps(schema.get("parameters", {}), ensure_ascii=False)
            )
        return "\n".join(lines)

    def _app_hints_block(self) -> str:
        if not _APP_HINTS:
            return ""
        lines = ["## Application hints"]
        for package, hint in _APP_HINTS.items():
            lines.append(f"### {package}")
            lines.append(hint)
        return "\n".join(lines)

    def _semantic_snapshot(self) -> str:
        return memory_snapshot.get().strip()

    def _episodes_block(self, episodes: list[Episode]) -> str:
        if not episodes:
            return ""
        lines = ["## Pending episodes"]
        for episode in episodes:
            summary = f"- [{episode.id}] {episode.summary}"
            if episode.pending_on:
                summary += f" (waiting on: {episode.pending_on})"
            lines.append(summary)
        return "\n".join(lines)

    def _bot_state_block(self) -> str:
        feeling = _describe_feeling()
        return f"## Current feeling\n{feeling}" if feeling else ""

    def _format_messages(self, messages: list[Message]) -> str:
        return "\n".join(
            f"- [{message.role}] {message.content}" for message in messages[-12:]
        )


def _describe_feeling() -> str:
    if bot_state.is_stressed():
        return "Things have been relentless for a while, so it feels hard to breathe."
    if bot_state.is_in_flow():
        return "The rhythm feels good right now: busy enough to stay engaged, not overwhelming."
    rate = bot_state.activity_rate
    variability = bot_state.activity_variability
    if rate < 0.2 and variability < 0.3:
        return "It is genuinely calm right now, which makes it a good time for personal upkeep."
    if rate < 0.2 and variability > 0.5:
        return "The day has been mostly quiet with occasional interruptions."
    return ""


context_builder = ContextBuilder()
