from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    returns: dict[str, dict[str, Any]] = field(default_factory=dict)
    side_effects: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolSpec":
        return cls(
            name=str(payload.get("name", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            parameters=_normalize_mapping(payload.get("parameters")),
            returns=_normalize_mapping(payload.get("returns")),
            side_effects=[
                str(item)
                for item in payload.get("side_effects", [])
                if str(item).strip()
            ],
        )

    def to_parameters_schema(self) -> dict[str, Any]:
        properties = {
            name: _schema_from_field(spec) for name, spec in self.parameters.items()
        }
        required = [
            name
            for name, spec in self.parameters.items()
            if bool(spec.get("required", True))
        ]
        return {"type": "object", "properties": properties, "required": required}

    def to_returns_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                name: _schema_from_field(spec) for name, spec in self.returns.items()
            },
        }


@dataclass(slots=True)
class Manifest:
    package: str
    name: str
    version: str
    brain_version: str
    persona_hint: str = ""
    planning_hint: str = ""
    capabilities: list[str] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)
    type: str = "application"

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        raw_payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        tools = [
            ToolSpec.from_dict(item)
            for item in payload.get("tools", [])
            if isinstance(item, dict)
        ]
        return cls(
            package=str(payload.get("package", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            version=str(payload.get("version", "0.0.0")).strip(),
            brain_version=str(payload.get("brain_version", "")).strip(),
            persona_hint=str(payload.get("persona_hint", "")).strip(),
            planning_hint=str(payload.get("planning_hint", "")).strip(),
            capabilities=[
                str(item)
                for item in payload.get("capabilities", [])
                if str(item).strip()
            ],
            tools=tools,
            type=str(payload.get("type", "application")).strip() or "application",
        )


def _normalize_mapping(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            normalized[str(key)] = {
                str(item_key): item_value for item_key, item_value in value.items()
            }
    return normalized


def _schema_from_field(spec: dict[str, Any]) -> dict[str, Any]:
    schema = {"type": str(spec.get("type", "string"))}
    description = str(spec.get("description", "")).strip()
    if description:
        schema["description"] = description
    items = spec.get("items")
    if isinstance(items, dict):
        schema["items"] = _schema_from_field(
            {str(key): value for key, value in items.items()}
        )
    return schema
