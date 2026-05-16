from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from src.brain.kernel.circuit import Circuit
from src.brain.kernel.base import Node
from src.brain.nodes.agents import ExampleNode, ExecuteNode, ExpandNode, PlanNode
from src.brain.nodes.routers import MergeRouter, SwitchRouter, WaitRouter
from src.config import Config
from src.utils.log_utils import get_logger

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("NodeFactory")

# 节点注册表 —— 新节点加在这里
NODE_REGISTRY: dict[str, type[Node]] = {
    "planner": PlanNode,
    "expander": ExpandNode,
    "executor": ExecuteNode,
    "example": ExampleNode,
    "switch": SwitchRouter,
    "merge": MergeRouter,
    "wait": WaitRouter,
}

# 部分节点构造时需要 host 引用
NODE_NEEDS_HOST: frozenset[str] = frozenset({"expander", "executor", "example"})

# 部分节点通过 topology.yaml 的 config 块传入参数
NODE_ACCEPTS_CONFIG: frozenset[str] = frozenset({"switch", "merge", "wait"})


def _load_topology_config() -> dict[str, Any]:
    """读取 ``topology.yaml``，返回节点头部配置。"""
    path = Config.TOPOLOGY_CONFIG
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"拓扑配置不存在: {path}，使用全量默认配置")
        return _default_topology()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"读取拓扑配置失败: {exc}，使用全量默认配置")
        return _default_topology()

    if not isinstance(payload, dict):
        logger.warning("拓扑配置格式错误，使用全量默认配置")
        return _default_topology()

    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, dict):
        logger.warning("拓扑配置缺少 nodes 字段，使用全量默认配置")
        return _default_topology()

    return _normalize(raw_nodes)


def _default_topology() -> dict[str, Any]:
    """全量启用所有注册节点。"""
    return {name: {"enabled": True} for name in NODE_REGISTRY}


def _normalize(raw_nodes: dict[str, Any]) -> dict[str, Any]:
    """将 ``{name: {enabled: true, config: {...}}}`` 归一化，未知节点名直接丢弃。"""
    normalized: dict[str, Any] = {}
    for name, spec in raw_nodes.items():
        if name not in NODE_REGISTRY:
            logger.warning(f"拓扑配置包含未知节点: {name}，已忽略")
            continue
        if not isinstance(spec, dict):
            spec = {}
        normalized[name] = {
            "enabled": bool(spec.get("enabled", True)),
            "config": spec.get("config", {}) if isinstance(spec.get("config"), dict) else {},
        }
    return normalized


def build_circuit(host: ApplicationHost) -> Circuit:  # noqa: F821
    """从 ``topology.yaml`` 读取配置，构造认知拓扑电路。

    遍历 ``NODE_REGISTRY``，按配置启用/禁用。已启用的节点逐
    个实例化并注入 ``Circuit``。

    Parameters
    ----------
    host : ApplicationHost
        应用宿主，注入给需要访问命令/事件的节点。

    Returns
    -------
    Circuit
        已装配但**未启动**的电路实例，调用方需 await ``circuit.start()``。
    """
    topology = _load_topology_config()
    instances: list[Node] = []

    for name in sorted(NODE_REGISTRY):
        entry = topology.get(name)
        if entry is None or not entry.get("enabled", False):
            logger.info(f"节点已禁用: {name}")
            continue

        node_cls = NODE_REGISTRY[name]
        node_config = entry.get("config", {})

        if name in NODE_ACCEPTS_CONFIG:
            node = node_cls(name, **node_config)
        elif name in NODE_NEEDS_HOST:
            node = node_cls(name, host)
        else:
            node = node_cls(name)

        instances.append(node)
        logger.info(f"节点已装配: {name} ({node_cls.__name__})")

    if not instances:
        logger.warning("电路没有装配任何节点 — 空转")

    return Circuit(instances)
