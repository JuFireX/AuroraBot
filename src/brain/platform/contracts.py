from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AppEvent:
    source: str
    type: str
    session_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    # TODO: 增加summary, last_time字段


@dataclass(slots=True)
class CommandSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    returns_schema: dict[str, Any]
    handler: Callable[..., Any]
