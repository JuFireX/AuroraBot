from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.brain.kernel.base import (
    Agent,
    FileDescriptor,
    FilePattern,
    FileUpdate,
    NodeState,
)
from src.config import Config
from src.utils.log_utils import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("ExampleNode")

_DATA_DIR = Config.KERNEL_DATA_DIR

_SYSTEM_PROMPT = """你是小光，一个活泼可爱的 QQ 聊天机器人。请用自然的中文回复以下消息。
要求：
- 回复简洁自然，像朋友聊天一样
- 字数控制在 50 字以内
- 用口语化的短句
- 不要使用颜文字和 emoji
- 不说客套话
"""


class ExampleNode(Agent):
    """测试用节点 — 消费所有 AppEvent，调用 LLM 回复，通过 QQ 发回。

    - ``guards``: ``inbox/event_*.json``
    - 读取 inbox 事件 → 调用 LLM → 调用 ``im.polaris.qq.send_qq_message`` 回复
    - 处理完后删除 inbox 文件

    注意
    ----
    这是测试节点，不区分事件类型、不加频率限制，收到什么都回。
    """

    def __init__(self, node_id: str, host: ApplicationHost) -> None:  # noqa: F821
        super().__init__(node_id, host, system_prompt=_SYSTEM_PROMPT)
        self._inbox_dir = _DATA_DIR / "inbox"

    @property
    def type(self) -> str:
        return "agent"

    @property
    def guards(self) -> list[FilePattern]:
        return [FilePattern("inbox/event_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        return []

    async def execute(self) -> list[FileUpdate]:
        if not self._inbox_dir.exists():
            return []

        event_files = sorted(self._inbox_dir.glob("event_*.json"))
        if not event_files:
            return []

        for event_file in event_files:
            try:
                event_data = self._read_event(event_file)
                if event_data is None:
                    self._safe_unlink(event_file)
                    continue

                ok = await self._handle_event(event_data)
                if ok:
                    self._safe_unlink(event_file)

            except Exception:  # noqa: BLE001
                logger.exception(f"ExampleNode 处理事件文件失败: {event_file.name}")

        return []

    def _read_event(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"读取事件文件失败 {path}: {exc}")
            return None

    async def _handle_event(self, event_data: dict[str, Any]) -> bool:
        event_type = str(event_data.get("type", ""))
        session_id = str(event_data.get("session_id", ""))
        payload = event_data.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        text = str(payload.get("text", ""))
        source = str(event_data.get("source", ""))

        logger.info(
            f"处理事件: type={event_type}, session={session_id}, "
            f"source={source}, text={text!r}"
        )

        if not text.strip():
            logger.info("事件无文本内容，跳过")
            return True

        # 调用 LLM
        user_msg = f"收到的消息: {text}\n请回复这条消息。"
        messages = [{"role": "user", "content": user_msg}]
        try:
            reply = await self.think(messages, max_tokens=256)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"LLM 调用失败: {exc}")
            return False

        reply = (reply or "").strip()
        if not reply:
            logger.info("LLM 返回空回复，跳过")
            return True

        logger.info(f"LLM 回复: {reply!r}")

        # 通过 QQ 发回
        if session_id:
            try:
                result = await self.host.invoke_command(
                    "im.polaris.qq.send_qq_message",
                    session_id=session_id,
                    text=reply,
                )
                logger.info(f"QQ 发送结果: {result}")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"QQ 发送失败: {exc}")
                return False
        else:
            logger.warning("事件无 session_id，无法回复")
            return True

        return True

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"删除文件失败 {path}: {exc}")

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
