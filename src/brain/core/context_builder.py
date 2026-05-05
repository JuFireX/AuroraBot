from __future__ import annotations

import json
from pathlib import Path

from src.brain.core.models import Episode, Plan
from src.brain.core.session import Message, session_buffer
from src.brain.core.state import bot_state
from src.brain.core.tool_registry import get_all
from src.brain.memory.snapshot import memory_snapshot
from src.config import Config


class ContextBuilder:
    def __init__(self) -> None:
        self._prompt_cache: dict[Path, str] = {}

    async def build_system(
        self,
        related_episodes: list[Episode],
        session_id: str | None = None,
    ) -> str:
        if memory_snapshot.should_refresh():
            await memory_snapshot.refresh()

        parts = [
            self._prompt("SOUL.md"),
            self._prompt("PLAN.md"),
            self._tool_hints(),
            self._semantic_snapshot(),
            self._episodes(related_episodes),
            self._bot_state(),
        ]
        if session_id:
            parts.append(f"当前 session_id: {session_id}")
        return "\n\n---\n\n".join(part for part in parts if part.strip())

    def build_user(self, plan: Plan, session_id: str | None = None) -> str:
        items_payload = [item.payload for item in plan.sub_items]
        parts = [
            f"当前计划 intent: {plan.intent}",
            f"计划优先级: {plan.priority:.1f}",
            "涉及事项(JSON):",
            json.dumps(items_payload, ensure_ascii=False, indent=2),
        ]
        if plan.related_episodes:
            parts.append("候选情节ID: " + ", ".join(plan.related_episodes))
        if session_id:
            context = session_buffer.get_context(session_id)
            if context:
                parts.append("近期对话上下文:")
                parts.append(self._format_messages(context))
        return "\n".join(parts)

    def _prompt(self, filename: str) -> str:
        path = Config.PROMPTS_DIR / filename
        if path not in self._prompt_cache:
            self._prompt_cache[path] = (
                path.read_text(encoding="utf-8-sig").strip() if path.exists() else ""
            )
        return self._prompt_cache[path]

    def _tool_hints(self) -> str:
        tools = get_all()
        if not tools:
            return "当前没有可用工具。"
        tool_lines = ["当前可用工具（按需选择，不要臆造不存在的工具）:"]
        for tool in tools:
            tool_lines.append(
                f"- {tool.name}: {tool.description}; 参数模式={json.dumps(tool.parameters_schema, ensure_ascii=False)}"
            )
        return "\n".join(tool_lines)

    def _semantic_snapshot(self) -> str:
        return memory_snapshot.get().strip()

    def _episodes(self, episodes: list[Episode]) -> str:
        if not episodes:
            return ""
        lines = ["当前挂起情节候选（需要你判断是否相关）:"]
        for episode in episodes:
            pending_on = episode.pending_on or "未指定"
            notify = episode.notify or "无"
            lines.append(
                f"- [{episode.id}] {episode.summary}（等待: {pending_on}; 完成后: {notify}）"
            )
        return "\n".join(lines)

    def _bot_state(self) -> str:
        return (
            "当前状态: "
            f"精力 {bot_state.energy_current:.1f}/{bot_state.energy_max:.1f}, "
            f"认知负载 {bot_state.cognitive_load:.2f}, "
            f"plan_interval {bot_state.plan_interval}, "
            f"idle_counter {bot_state.idle_counter}"
        )

    def _format_messages(self, messages: list[Message]) -> str:
        return "\n".join(
            f"- [{message.role}] {message.content}" for message in messages[-12:]
        )


context_builder = ContextBuilder()
