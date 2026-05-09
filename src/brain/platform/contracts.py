from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.utils.time_utils import now_text


@dataclass(slots=True)
class AppEvent:
    source: str
    type: str
    session_id: str = ""
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    expire_at: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=now_text)


@dataclass(slots=True)
class CommandSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    returns_schema: dict[str, Any]
    handler: Callable[..., Any]
