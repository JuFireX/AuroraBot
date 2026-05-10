from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

from src.platform.manifest import Manifest
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("AppDiscovery")


@dataclass(frozen=True, slots=True)
class DiscoveredApp:
    key: str
    package: str
    name: str
    directory: Path


def apps_root() -> Path:
    return Config.PROJECT_ROOT / "apps"


# 发现所有应用(软件包要求一个 manifest.yaml 文件和一个 __init__.py 文件)
def discover_apps(root: Path | None = None) -> dict[str, DiscoveredApp]:
    search_root = root or apps_root()
    discovered: dict[str, DiscoveredApp] = {}
    if not search_root.exists():
        return discovered
    for child in sorted(search_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.name.startswith("__"):
            continue
        manifest_path = child / "manifest.yaml"
        init_path = child / "__init__.py"
        if not manifest_path.exists() or not init_path.exists():
            continue
        try:
            manifest = Manifest.load(manifest_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"跳过应用目录 {child.name}, manifest 读取失败: {exc}")
            continue
        if not manifest.package:
            logger.warning(f"跳过应用目录 {child.name}, manifest.package 为空")
            continue
        discovered[child.name] = DiscoveredApp(
            key=child.name,
            package=manifest.package,
            name=manifest.name or child.name,
            directory=child,
        )
    return discovered


# 实例化应用
def instantiate_app(app_name: str, startup: dict[str, Any] | None = None) -> Any:
    module = importlib.import_module(f"apps.{app_name}")
    app_class = _resolve_application_class(module)
    kwargs = _filter_startup_kwargs(app_class, startup or {})
    return app_class(**kwargs)


# 获取应用启动参数默认值
def startup_defaults(app_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(f"apps.{app_name}")
        app_class = _resolve_application_class(module)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"读取应用 {app_name} 启动参数默认值失败: {exc}")
        return {}
    signature = inspect.signature(app_class)
    defaults: dict[str, Any] = {}
    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Signature.empty:
            continue
        defaults[parameter.name] = parameter.default
    return defaults


def _resolve_application_class(module: ModuleType) -> type[Any]:
    exports = getattr(module, "__all__", [])
    for name in exports:
        candidate = getattr(module, str(name), None)
        if inspect.isclass(candidate):
            return candidate
    for _, candidate in inspect.getmembers(module, inspect.isclass):
        if candidate.__module__.startswith(
            module.__name__
        ) and candidate.__name__.endswith("Application"):
            return candidate
    raise LookupError(f"在模块 {module.__name__} 中未找到 Application 类")


def _filter_startup_kwargs(
    app_class: type[Any],
    startup: dict[str, Any],
) -> dict[str, Any]:
    signature = inspect.signature(app_class)
    parameters = signature.parameters
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return dict(startup)
    allowed = {
        name
        for name, parameter in parameters.items()
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    unknown = sorted(set(startup) - allowed)
    if unknown:
        logger.warning(
            f"应用 {app_class.__name__} 忽略未知启动参数: {', '.join(unknown)}"
        )
    return {key: value for key, value in startup.items() if key in allowed}
