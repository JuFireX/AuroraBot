from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.platform.contracts import AppEvent, CommandSpec
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI


class ExampleApplication:
    def __init__(
        self,
        greeting: str = "hello from example",
        emit_startup_event: bool = True,
    ) -> None:
        self._api: PlatformAPI | None = None
        self._greeting = greeting
        self._emit_startup_event = emit_startup_event
        self._notes_file: Path | None = None
        self._state_file: Path | None = None
        self._notes: list[dict[str, Any]] = []
        self._tick_count = 0

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api
        self._notes_file = api.data_dir / "notes.json"
        self._state_file = api.data_dir / "state.json"
        api.log("info", f"绑定示例应用: package={api.package}, data_dir={api.data_dir}")
        api.register_command(
            CommandSpec(
                name=f"{api.package}.dynamic_ping",
                description="动态注册的 ping 命令，演示 register_command 的用法。",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "ping 主题",
                        }
                    },
                    "required": [],
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "message": {"type": "string"},
                    },
                },
                handler=self.dynamic_ping,
            )
        )

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        self._load_notes()
        self._save_state(last_status="started")
        api = self._require_api()
        api.log("info", "Example application started")
        if self._emit_startup_event:
            api.post_intention(
                AppEvent(
                    source=api.package,
                    type="example.started",
                    summary=self._greeting,
                    payload={
                        "greeting": self._greeting,
                        "data_dir": str(api.data_dir),
                    },
                )
            )

    async def on_stop(self) -> None:
        self._save_notes()
        self._save_state(last_status="stopped")
        self._require_api().log("info", "Example application stopped")

    async def on_tick(self) -> None:
        self._tick_count += 1
        if self._tick_count % 30 == 0:
            self._save_state(last_status="running")

    def echo_message(
        self,
        text: str,
        session_id: str = "",
        use_post_intention: bool = False,
    ) -> dict[str, object]:
        api = self._require_api()
        event = AppEvent(
            source=api.package,
            type="example.echoed",
            session_id=session_id,
            summary=text.strip(),
            payload={
                "text": text,
                "session_id": session_id,
                "used_post_intention": bool(use_post_intention),
            },
        )
        if use_post_intention:
            api.post_intention(event)
        else:
            api.emit_event(event)
        api.log("info", f"echo_message called: {text}")
        return {"ok": True, "echoed_text": text, "package": api.package}

    def save_note(
        self,
        title: str,
        content: str,
        emit_event: bool = True,
    ) -> dict[str, object]:
        api = self._require_api()
        note = {
            "title": title,
            "content": content,
            "created_at": now_text(),
        }
        self._notes.append(note)
        self._save_notes()
        self._save_state(last_status="note_saved")
        api.log("info", f"save_note called: {title}")
        if emit_event:
            api.emit_event(
                AppEvent(
                    source=api.package,
                    type="example.note_saved",
                    summary=title.strip(),
                    payload=note,
                )
            )
        return {"ok": True, "note_count": len(self._notes)}

    def publish_demo_event(
        self,
        event_type: str = "example.custom",
        summary: str = "manual demo event",
        session_id: str = "",
    ) -> dict[str, object]:
        api = self._require_api()
        api.emit_event(
            AppEvent(
                source=api.package,
                type=event_type.strip() or "example.custom",
                session_id=session_id,
                summary=summary.strip() or "manual demo event",
                payload={"session_id": session_id},
            )
        )
        api.log("info", f"publish_demo_event called: {event_type}")
        return {"ok": True, "emitted_type": event_type.strip() or "example.custom"}

    def dynamic_ping(self, topic: str = "platform") -> dict[str, object]:
        api = self._require_api()
        message = f"pong from {api.package}: {topic}"
        api.log("info", f"dynamic_ping called: {topic}")
        return {"ok": True, "message": message}

    def _load_notes(self) -> None:
        loaded = self._read_json(self._notes_file, [])
        self._notes = [dict(item) for item in loaded if isinstance(item, dict)]

    def _save_notes(self) -> None:
        self._write_json(self._notes_file, self._notes)

    def _save_state(self, last_status: str) -> None:
        api = self._require_api()
        self._write_json(
            self._state_file,
            {
                "package": api.package,
                "tick_count": self._tick_count,
                "notes_count": len(self._notes),
                "last_status": last_status,
                "updated_at": now_text(),
            },
        )

    def _read_json(self, file_path: Path | None, default: Any) -> Any:
        if file_path is None or not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return default

    def _write_json(self, file_path: Path | None, data: Any) -> None:
        if file_path is None:
            return
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _require_api(self) -> "PlatformAPI":
        if self._api is None:
            raise RuntimeError("ExampleApplication is not bound to PlatformAPI")
        return self._api
