from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.platform.app_discovery import (
    DiscoveredApp,
    discover_apps,
    startup_defaults,
)
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("AppConfig")


def app_config_path() -> Path:
    return Config.PROJECT_ROOT / "apps" / "config.yaml"


# 加载应用配置
def load_apps_config(path: Path | None = None) -> dict[str, dict[str, Any]]:
    config_path = path or app_config_path()
    discovered = discover_apps()

    # 当配置文件不存在时, 根据发现的应用生成初始化配置并返回
    if not config_path.exists():
        _write_initial_config(config_path, discovered)
        logger.warning(
            "未找到 apps/config.yaml, 已根据扫描结果生成初始化配置; 本次不加载任何应用"
        )
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取 apps/config.yaml 失败, 本次不加载任何应用: %s", exc)
        return {}
    payload = loaded if isinstance(loaded, dict) else {}
    raw_apps = payload.get("apps", {})
    if not isinstance(raw_apps, dict):
        logger.warning("apps/config.yaml 的 apps 字段不是映射, 本次不加载任何应用")
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for name in sorted(discovered):
        raw = raw_apps.get(name)
        if raw is None:
            logger.warning("应用 %s 未在 apps/config.yaml 中声明, 跳过加载", name)
            continue
        if not isinstance(raw, dict):
            logger.warning("应用 %s 的配置不是对象, 跳过加载", name)
            continue
        startup = raw.get("startup", {})
        if not isinstance(startup, dict):
            logger.warning("应用 %s 的 startup 字段不是对象, 已重置为空", name)
            startup = {}
        normalized[name] = {
            "enabled": bool(raw.get("enabled", False)),
            "startup": {str(key): value for key, value in startup.items()},
        }

    for name in sorted(set(raw_apps) - set(discovered)):
        logger.warning("apps/config.yaml 中声明了未知应用 %s, 已忽略", name)
    return normalized


# 获取已启用的应用名称
def enabled_app_names(apps_config: dict[str, dict[str, Any]]) -> list[str]:
    return [
        name for name, spec in apps_config.items() if bool(spec.get("enabled", False))
    ]


def app_startup(
    apps_config: dict[str, dict[str, Any]], app_name: str
) -> dict[str, Any]:
    startup = apps_config.get(app_name, {}).get("startup", {})
    return startup if isinstance(startup, dict) else {}


def build_initial_apps_config() -> dict[str, Any]:
    return _build_initial_apps_config_from_discovered(discover_apps())


# 写入初始应用配置
def _write_initial_config(
    config_path: Path, discovered: dict[str, DiscoveredApp]
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            _build_initial_apps_config_from_discovered(discovered),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _build_initial_apps_config_from_discovered(
    discovered: dict[str, DiscoveredApp],
) -> dict[str, Any]:
    return {
        "apps": {
            name: {
                "enabled": True,
                "startup": startup_defaults(name),
            }
            for name in sorted(discovered)
        }
    }
