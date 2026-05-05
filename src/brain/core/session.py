from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from src.config import Config


@dataclass
class Message:
    role: str
    content: str
    timestamp: float


class SessionBuffer:
    def __init__(self, max_tokens: int = Config.SESSION_MAX_TOKENS) -> None:
        self._sessions: dict[str, deque[Message]] = {}
        self.max_tokens = max_tokens

    def append(self, session_id: str, message: Message) -> None:
        sid = str(session_id)
        if sid not in self._sessions:
            self._sessions[sid] = deque()
        self._sessions[sid].append(message)
        self._trim(sid)

    def append_text(self, session_id: str, role: str, content: str) -> None:
        self.append(
            session_id=session_id,
            message=Message(role=role, content=content, timestamp=time.time()),
        )

    def get_context(self, session_id: str) -> list[Message]:
        return list(self._sessions.get(str(session_id), deque()))

    def clear(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._sessions.clear()
            return
        self._sessions.pop(str(session_id), None)

    def _trim(self, session_id: str) -> None:
        msgs = self._sessions.get(session_id)
        if msgs is None:
            return
        while _estimate_messages_tokens(msgs) > self.max_tokens and msgs:
            msgs.popleft()


def _estimate_messages_tokens(messages: deque[Message]) -> int:
    # M2 阶段采用轻量估算，后续可替换为 tokenizer。
    return sum(max(1, len(msg.content) // 4) for msg in messages)


session_buffer = SessionBuffer()
