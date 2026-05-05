from __future__ import annotations


class ReplyStore:
    def __init__(self) -> None:
        self._replies: dict[str, str] = {}

    def set(self, session_id: str, reply: str) -> None:
        self._replies[str(session_id)] = str(reply)

    def get(self, session_id: str) -> str | None:
        return self._replies.get(str(session_id))

    def pop(self, session_id: str) -> str | None:
        return self._replies.pop(str(session_id), None)

    def clear(self) -> None:
        self._replies.clear()


reply_store = ReplyStore()
