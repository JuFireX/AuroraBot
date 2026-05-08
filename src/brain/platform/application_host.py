from __future__ import annotations

import inspect
from typing import Any

from src.brain.core.capability_registry import CapabilitySpec, register as register_capability
from src.brain.core.context_builder import (
    register_app_planning_hint,
    reset_app_planning_hints,
)
from src.brain.platform.application_api import PlatformAPI
from src.brain.platform.application_protocol import ApplicationProtocol
from src.brain.platform.manifest import Manifest, ToolSpec
from src.utils.Logger import get_logger

logger = get_logger("ApplicationHost")


class ApplicationHost:
    def __init__(self) -> None:
        self._apps: dict[str, ApplicationProtocol] = {}

    async def register(self, app: ApplicationProtocol) -> None:
        if not isinstance(app, ApplicationProtocol):
            raise TypeError(f"{app.__class__.__name__} does not satisfy ApplicationProtocol")
        manifest = Manifest.load(app.manifest_path())
        if not manifest.package:
            raise ValueError(f"Manifest package is required: {app.manifest_path()}")
        if manifest.package in self._apps:
            return
        for tool_spec in manifest.tools:
            handler = getattr(app, tool_spec.name, None)
            if handler is None:
                raise AttributeError(
                    f"{app.__class__.__name__} is missing method declared in manifest: {tool_spec.name}"
                )
            register_capability(
                CapabilitySpec(
                    name=f"{manifest.package}.{tool_spec.name}",
                    description=_build_llm_description(tool_spec),
                    parameters_schema=tool_spec.to_parameters_schema(),
                    returns_schema=tool_spec.to_returns_schema(),
                    side_effects=tool_spec.side_effects,
                    handler=handler,
                )
            )
        if manifest.planning_hint:
            register_app_planning_hint(manifest.package, manifest.planning_hint)
        bind = getattr(app, "_bind", None)
        if callable(bind):
            result = bind(PlatformAPI(manifest, self))
            if inspect.isawaitable(result):
                await result
        await _maybe_await(app.on_start())
        self._apps[manifest.package] = app
        logger.info("Application registered: %s (%s)", manifest.name, manifest.package)

    async def tick(self) -> None:
        for package, app in self._apps.items():
            try:
                await _maybe_await(app.on_tick())
            except Exception as exc:  # noqa: BLE001
                logger.error("Application tick failed [%s]: %s", package, exc)

    async def stop_all(self) -> None:
        for package, app in reversed(list(self._apps.items())):
            try:
                await _maybe_await(app.on_stop())
            except Exception as exc:  # noqa: BLE001
                logger.error("Application stop failed [%s]: %s", package, exc)
        self._apps.clear()
        reset_app_planning_hints()


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


def _build_llm_description(tool_spec: ToolSpec) -> str:
    lines = [tool_spec.description.strip()]
    if tool_spec.side_effects:
        lines.append("Side effects:")
        lines.extend(f"- {item}" for item in tool_spec.side_effects)
    return "\n".join(line for line in lines if line).strip()


app_host = ApplicationHost()
