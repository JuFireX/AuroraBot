from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from src.config import Config


def kernel_file(name: str) -> Path:
    return Config.KERNEL_DATA_DIR / name


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def save_json_list(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_record_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
