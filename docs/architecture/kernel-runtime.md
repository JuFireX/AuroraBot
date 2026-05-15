---
title: 内核运行时
description: Kernel 的调度机制——从旧 loop.py 线性轮询到事件总线驱动的过渡。
order: 6
---

# 内核运行时

Kernel 是 AuroraBot 的调度心脏。**当前代码处于过渡期**：旧调度器 `loop.py` 仍在运行，新的事件总线 + Node 调度模型已在 `base.py` 中就位，等待 `node_factory.py` 完成填充后切换。

## 当前运行态：loop.py 线性调度

旧调度器位于 `src/brain/kernel/loop.py`，采用轮询 + 优先级模型：

```
每个周期：
  1. 遍历所有 Agent，调用 propose() 收集提案
  2. 按优先级排序，选择得分最高的 Agent
  3. 调用该 Agent 的 step()，执行一步
  4. 如果该步是"空闲"结果，结束本轮
  5. 否则回到 2，最多执行 MAX_AGENT_STEPS_PER_TICK 步
```

### 当前注册的 Agent

```python
DEFAULT_AGENT_KEYS = ("plan", "expand", "execute")
```

这三个 Agent 对应旧流水线的三个阶段。注册表在 `agent_factory.py` 中：

| Key       | 类             | 职责                         |
| --------- | -------------- | ---------------------------- |
| `plan`    | `PlanAgent`    | 从事件队列识别意图，生成计划 |
| `expand`  | `ExpandAgent`  | 将计划展开为原子动作         |
| `execute` | `ExecuteAgent` | 调用 App 命令执行            |

## 目标态：事件总线 + Node 调度

迁移完成后，Kernel 的调度将转向事件驱动模型：

```
事件循环：
  1. 文件变更 → 事件总线广播 FileEvent
  2. 所有 Node 的 on_event() 被调用
  3. 匹配的 Node 进入 READY 状态
  4. 调度器按优先级从 READY 队列中选择 Node
  5. 调用 execute()，产出 FileUpdate
  6. 文件写入触发新一轮 FileEvent → 回到 1
```

关键变化：

| 维度     | 旧调度                  | 新调度                               |
| -------- | ----------------------- | ------------------------------------ |
| 触发方式 | 定时轮询（interval）    | 事件驱动（文件变更）                 |
| 调度对象 | Agent（propose / step） | Node（on_event / execute）           |
| 激活判断 | Agent 内部逻辑          | 声明式 `guards` + `FileEvent`        |
| 产出     | 命令调用                | `FileUpdate` + 命令调用              |
| 流程控制 | 无（硬编码顺序）        | Router 节点（Switch / Loop / Merge） |

## HeartbeatRouter — 自主意识脉冲

新架构的核心创新之一：系统不再等待外部输入。`HeartbeatRouter` 定时产生脉冲事件（`heartbeat.tick`），驱动 `GoalGeneratorAgent` 在沉默过久时主动生成意图。

这使 AuroraBot 从"回应用户的镜子"变成"会自己呼吸的生命体"——她不是因为有人说话才醒来，而是内部的钟摆从不停止。

## 当前过渡状态

```
src/brain/
  kernel/
    base.py           ← ✅ Node/Agent/Router 基类就位
    agent_base.py     ← 🔄 旧 Agent 体系（运行中）
    agent_factory.py  ← 🔄 旧 Agent 注册表（运行中）
    node_factory.py   ← ⏳ 空文件，待实现
    loop.py           ← 🔄 旧调度器（运行中）
  agents/
    plan_agent.py     ← 🔄 旧 Agent（待重写为 Node）
    expand_agent.py   ← 🔄 旧 Agent（待重写为 Node）
    execute_agent.py  ← 🔄 旧 Agent（待重写为 Node）
  nodes/
    agents/           ← ⏳ 空目录，待填充
    routers/          ← ⏳ 空目录，待填充
```

## 下一步阅读

- 想理解 Node 基类细节：读 [节点系统](./node-system.html)
- 想理解认知全貌：读 [认知架构](./brain-architecture.html)
- 想看目标态认知拓扑：设计白皮书 `CortexForge 0.7`
