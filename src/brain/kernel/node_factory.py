from __future__ import annotations

from typing import TYPE_CHECKING

from src.brain.kernel.circuit import Circuit
from src.brain.nodes.agents import ExecuteNode, ExpandNode, PlanNode

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost


def build_circuit(host: ApplicationHost) -> Circuit:  # noqa: F821
    """构造认知拓扑电路并返回已装配的 Circuit 实例。

    当前装配三个节点：
    - ``planner``：PlanNode — 事件 → plan
    - ``expander``：ExpandNode — plan → action
    - ``executor``：ExecuteNode — action → 命令执行

    后续可添加 Router 节点（SwitchRouter、WaitRouter 等）以支持
    条件分支、多路汇集等控制流。

    Parameters
    ----------
    host : ApplicationHost
        应用宿主，注入给需要访问命令/事件的节点。

    Returns
    -------
    Circuit
        已装配但未启动的电路实例，调用方需 await ``circuit.start()``。
    """
    nodes = [
        PlanNode("planner"),
        ExpandNode("expander", host),
        ExecuteNode("executor", host),
    ]
    return Circuit(nodes)
