from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class CapabilitySpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    returns_schema: dict[str, Any] = field(default_factory=dict)
    side_effects: list[str] = field(default_factory=list)
    handler: Callable[..., Any] | Callable[..., Awaitable[Any]] | None = None


_registry: dict[str, CapabilitySpec] = {}


def register(spec: CapabilitySpec) -> None:
    _registry[spec.name] = spec


def clear() -> None:
    _registry.clear()


def get(name: str) -> CapabilitySpec | None:
    return _registry.get(name)


def get_all() -> list[CapabilitySpec]:
    return list(_registry.values())


def get_all_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters_schema,
            "returns": spec.returns_schema,
            "side_effects": spec.side_effects,
        }
        for spec in _registry.values()
    ]


async def call(name: str, params: dict[str, Any]) -> Any:
    spec = _registry.get(name)
    if spec is None or spec.handler is None:
        raise KeyError(f"Capability '{name}' not registered")

    handler = spec.handler
    if inspect.iscoroutinefunction(handler):
        return await handler(**params)

    result = handler(**params)
    if inspect.isawaitable(result):
        return await result
    return result
