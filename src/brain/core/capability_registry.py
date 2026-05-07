from __future__ import annotations

import inspect
import re
from hashlib import sha1
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
_alias_to_name: dict[str, str] = {}
_name_to_alias: dict[str, str] = {}


def register(spec: CapabilitySpec) -> None:
    _registry[spec.name] = spec
    alias = _build_unique_alias(spec.name)
    _alias_to_name[alias] = spec.name
    _name_to_alias[spec.name] = alias


def clear() -> None:
    _registry.clear()
    _alias_to_name.clear()
    _name_to_alias.clear()


def get(name: str) -> CapabilitySpec | None:
    resolved_name = resolve_name(name)
    return _registry.get(resolved_name)


def get_all() -> list[CapabilitySpec]:
    return list(_registry.values())


def get_all_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": _name_to_alias[spec.name],
            "description": spec.description,
            "parameters": spec.parameters_schema,
            "returns": spec.returns_schema,
            "side_effects": spec.side_effects,
        }
        for spec in _registry.values()
    ]


async def call(name: str, params: dict[str, Any]) -> Any:
    spec = _registry.get(resolve_name(name))
    if spec is None or spec.handler is None:
        raise KeyError(f"Capability '{name}' not registered")

    handler = spec.handler
    if inspect.iscoroutinefunction(handler):
        return await handler(**params)

    result = handler(**params)
    if inspect.isawaitable(result):
        return await result
    return result


def resolve_name(name: str) -> str:
    return _alias_to_name.get(name, name)


def get_public_name(name: str) -> str:
    resolved_name = resolve_name(name)
    return _name_to_alias.get(resolved_name, resolved_name)


def _build_unique_alias(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    base_alias = sanitized or "tool"
    current = _alias_to_name.get(base_alias)
    if current is None or current == name:
        return base_alias
    suffix = sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{base_alias}_{suffix}"
