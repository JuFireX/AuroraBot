from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: ToolHandler


_registry: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    _registry[tool.name] = tool


def get_all() -> list[Tool]:
    return list(_registry.values())


def get_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        }
        for tool in _registry.values()
    ]


def clear() -> None:
    _registry.clear()


async def call(name: str, params: dict[str, Any]) -> Any:
    tool = _registry.get(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not registered")

    result = tool.handler(**params)
    if isawaitable(result):
        return await result
    return result
