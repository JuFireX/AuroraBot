# Polaris Bot 自循环体系（PAA 循环）架构设计文档

## 版本记录

| 版本  | 日期         | 作者   | 变更说明                                      |
| --- | ---------- | ---- | ----------------------------------------- |
| 1.0 | 2026-04-27 | 设计团队 | 初始详尽版，基于 Plan-Attention-Action 循环架构       |
| 2.0 | 2026-05-04 | 设计团队 | 重构 brain/services 边界；引入动态工具注册表；重新划定核心模块职责 |

***

## 1. 引言

本文档定义了 **PAA（Plan-Attention-Action）** Bot 自循环体系。该体系模拟人类处理任务的方式：**收集待办 → 合并为计划 → 专注于一项计划 → 将其分解为原子动作逐个执行**，并引入 **精力值** 作为全局限制资源，使 Bot 呈现出自主节奏与"人味"。

> 外部事件 → 收件箱（ToDo）→ 整理为意图（Plans）→ 专注一件事（Attention）→ 拆解执行（Actions）→ 精力耗尽就休息
>
> Claude: 整体架构一句话总结

### 1.1 核心设计理念

- **自上而下的分层调度**：ToDo（事件）→ Plans（意图）→ Attention（焦点）→ Actions（原子执行）
- **精力作为硬通货**：所有行动消耗精力，精力不足时暂停，恢复后继续。
- **自然节律驱动**：无老化机制，任务不会被强制过期。Bot 在群聊活跃时快速响应，在安静时自发消化积压的低优先级计划，形成类似人类的作息感。
- **拟人化自动任务**：闹钟、定时提醒等自动任务以"柔性意图"存在，Bot 可以因忙碌而暂时忽略，不会被强迫立即执行。
- **原子动作保证**：每一步均可中断、可恢复，系统可随时安全暂停。
- **AI 驱动的动态工具选择**：Brain 的动作展开由 LLM function call 驱动，工具能力由外围 Services 在启动时动态注册，Brain 不硬编码任何工具细节。

***

## 2. 系统架构总览

### 2.1 宏观分层

系统分为两个顶层模块：

```
┌─────────────────────────────────────────────┐
│                  brain/                     │
│   认知系统：感知、规划、决策、执行的闭环          │
│   不依赖任何具体外围服务                        │
└────────────────────┬────────────────────────┘
                     │  单向依赖
┌────────────────────▼────────────────────────┐
│                 services/                   │
│   外部适配器：感知输入、执行输出                 │
│   启动时向 brain 注册自己的能力                 │
└─────────────────────────────────────────────┘
```

**关键原则**：

- Services 依赖 brain（注入 TodoItem、注册工具）
- Brain **完全不 import** 任何 service 模块
- 新增 Service 只需注册，brain 无需改动

### 2.2 Brain 内部数据流

```
Services ──push──▶ ToDo 队列
                       │
                       ▼  [planner.py：Plan 阶段]
                   Plans 队列（优先级堆）
                       │
                       ▼  [expander.py：Attention 阶段]
                 Attention 上下文（当前焦点计划）
                       │
                       ▼  [expander.py：LLM function call 展开]
                   Actions 队列（原子动作序列）
                       │
                       ▼  [executor.py：Action 阶段]
               tool_registry.call(action.name, action.params)
                       │
                       ▼
                  外围 Services（发消息、写文件、触发闹钟……）
```

### 2.3 心跳循环（engine.py）

每次心跳顺序执行：**精力恢复 → Plan 阶段 → Attention 阶段 → Action 阶段**

```
engine.tick()
    ├── state.regenerate_energy()
    ├── [条件] planner.run()        # 每 N 个心跳执行一次
    ├── [条件] expander.run()       # 仅当 Actions 空且无 Attention
    └── executor.run()              # 循环执行，直到精力不足或队列空
```

***

## 3. 项目文件结构

```
project/
│   main.py              ← 程序入口，启动 NoneBot、注册 Services
│   config.py            ← 全局配置常量
│
├───brain/
│   ├───core/
│   │       models.py        ← 纯数据类（无业务逻辑）
│   │       state.py         ← BotState 单例（精力、认知负载）
│   │       queues.py        ← 三个队列的单例（ToDo、Plans、Actions）
│   │       tool_registry.py ← 动态工具注册表单例
│   │       planner.py       ← Plan 阶段：ToDo → Plans
│   │       expander.py      ← Attention 阶段：Plan → Actions（LLM 驱动）
│   │       executor.py      ← Action 阶段：逐个调用工具
│   │       engine.py        ← 心跳主循环，纯编排
│   │
│   ├───model/
│   │       ModelService.py  ← LLM 调用封装
│   │
│   └───prompts/
│           PLAN.md          ← Plan 阶段系统提示词
│           SOUL.md          ← Bot 人格设定提示词
│
└───services/
    ├───QQService/
    │       core.py          ← OneBot 适配器，注册 QQ 相关工具
    ├───AlarmService/
    │       core.py          ← 定时任务，注册闹钟相关工具
    └───TestService/
            core.py          ← 测试用 Mock，注册假工具
```

***

## 4. 核心组件详细设计

### 4.1 models.py — 纯数据类

所有模块共用的数据结构，**不含任何业务逻辑**。

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Urgency(str, Enum):
    GENTLE = "gentle"
    NORMAL = "normal"
    URGENT = "urgent"

class AttentionState(str, Enum):
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"

@dataclass
class TodoItem:
    id: str
    type: str                        # 用于 Plan 阶段分组合并
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    created_at: float = 0.0          # unix timestamp
    suggested_window: dict | None = None  # 柔性提醒时间窗口

@dataclass
class Plan:
    id: str
    intent: str                      # 决定 Attention 阶段如何展开
    sub_items: list[TodoItem]
    priority: float
    base_priority: float
    weight: float = 1.0
    created_at: float = 0.0
    last_touched_at: float = 0.0

@dataclass
class Action:
    id: str
    tool_name: str                   # 对应 tool_registry 中的注册名
    params: dict[str, Any]
    energy_cost: float = 1.0
    preconditions: list = field(default_factory=list)

@dataclass
class Attention:
    plan_id: str
    intent: str
    priority: float
    total_energy_estimate: float
    action_count: int                # 展开时的动作总数
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = 0.0
```

### 4.2 state.py — BotState 单例

```python
from dataclasses import dataclass

@dataclass
class BotState:
    energy_current: float = 100.0
    energy_max: float = 100.0
    energy_regen_per_beat: float = 5.0
    cognitive_load: float = 0.5       # 0~1，影响 plan_interval 动态调整
    plan_interval: int = 3            # 每隔几个心跳执行一次 Plan 阶段
    base_plan_interval: int = 3
    idle_counter: int = 0             # 连续空闲心跳数
    heartbeat_count: int = 0

    def regenerate_energy(self):
        self.energy_current = min(
            self.energy_max,
            self.energy_current + self.energy_regen_per_beat
        )

    def has_energy(self, cost: float) -> bool:
        return self.energy_current >= cost

    def consume_energy(self, cost: float):
        self.energy_current = max(0.0, self.energy_current - cost)

    def is_idle(self, threshold: int = 10) -> bool:
        return self.idle_counter >= threshold and self.cognitive_load < 0.2

# 全局单例
bot_state = BotState()
```

### 4.3 queues.py — 队列单例

```python
from collections import deque
from queue import PriorityQueue as _PQ
from brain.core.models import TodoItem, Plan, Action, Attention

class TodoQueue:
    def __init__(self):
        self._q: deque[TodoItem] = deque()

    def push(self, item: TodoItem):
        self._q.append(item)

    def drain(self) -> list[TodoItem]:
        items = list(self._q)
        self._q.clear()
        return items

    def empty(self) -> bool:
        return len(self._q) == 0

class PlansQueue:
    """按 priority 排序的计划列表，最大堆语义"""
    def __init__(self):
        self._plans: list[Plan] = []

    def push(self, plan: Plan):
        self._plans.append(plan)
        self._plans.sort(key=lambda p: p.priority, reverse=True)

    def pop_highest(self) -> Plan | None:
        return self._plans.pop(0) if self._plans else None

    def pop_lowest(self) -> Plan | None:
        return self._plans.pop(-1) if self._plans else None

    def find_by_intent(self, intent: str) -> Plan | None:
        return next((p for p in self._plans if p.intent == intent), None)

    def remove(self, plan_id: str):
        self._plans = [p for p in self._plans if p.id != plan_id]

    def empty(self) -> bool:
        return len(self._plans) == 0

class ActionsQueue:
    def __init__(self):
        self._q: deque[Action] = deque()

    def push_all(self, actions: list[Action]):
        self._q.extend(actions)

    def peek(self) -> Action | None:
        return self._q[0] if self._q else None

    def pop(self) -> Action | None:
        return self._q.popleft() if self._q else None

    def clear(self):
        self._q.clear()

    def empty(self) -> bool:
        return len(self._q) == 0

# 全局单例
todo_queue   = TodoQueue()
plans_queue  = PlansQueue()
actions_queue = ActionsQueue()

# Attention 也作为单例管理（同时只有一个焦点）
current_attention: Attention | None = None
```

### 4.4 tool\_registry.py — 动态工具注册表

这是 v2 最重要的架构变化。Brain 不预定义任何工具接口，Services 在启动时**自报家门**，LLM 在展开动作时从注册表中自主选择工具。

```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class Tool:
    name: str
    description: str           # 给 LLM 看的自然语言描述
    parameters_schema: dict    # JSON Schema，定义入参格式
    handler: Callable          # 实际执行函数（可以是 async）

_registry: dict[str, Tool] = {}

def register(tool: Tool):
    """Service 启动时调用，向 brain 注册一个工具能力"""
    _registry[tool.name] = tool

def get_all() -> list[Tool]:
    """Expander 调用，获取全部可用工具的描述列表"""
    return list(_registry.values())

def get_schemas() -> list[dict]:
    """返回适合直接传给 LLM function call 的 schema 列表"""
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters_schema
        }
        for t in _registry.values()
    ]

async def call(name: str, params: dict) -> Any:
    """Executor 调用，按名字执行工具"""
    if name not in _registry:
        raise KeyError(f"Tool '{name}' not registered")
    handler = _registry[name].handler
    import asyncio
    if asyncio.iscoroutinefunction(handler):
        return await handler(**params)
    return handler(**params)
```

**Service 侧注册示例**（Services 对 brain 的唯一依赖）：

```python
# services/QQService/core.py
from brain.core.tool_registry import register, Tool
from brain.core.queues import todo_queue
from brain.core.models import TodoItem, Urgency

# ── 工具注册 ──────────────────────────────────

async def _send_qq_message(session_id: str, text: str):
    await bot.send_group_msg(group_id=int(session_id), message=text)

register(Tool(
    name="send_qq_message",
    description="向指定 QQ 群或用户发送一条文本消息",
    parameters_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "群号或QQ号"},
            "text":       {"type": "string", "description": "消息内容"}
        },
        "required": ["session_id", "text"]
    },
    handler=_send_qq_message
))

# ── 事件监听，注入 ToDo ────────────────────────

async def on_message(event):
    todo_queue.push(TodoItem(
        id=str(uuid.uuid4()),
        type="qq_msg",
        payload={
            "session_id": str(event.group_id or event.user_id),
            "text": event.get_plaintext()
        },
        urgency=Urgency.NORMAL
    ))
```

***

### 4.5 planner.py — Plan 阶段

**职责**：将 ToDo 队列中的原始事件合并为意图级计划，更新 Plans 队列。

**触发条件**：由 engine.py 根据 `state.plan_interval` 决定是否在本轮执行。

```python
import uuid, time
from brain.core.queues import todo_queue, plans_queue
from brain.core.state import bot_state
from brain.core.models import Plan, Urgency

URGENCY_BONUS = {
    Urgency.GENTLE: 0.0,
    Urgency.NORMAL: 10.0,
    Urgency.URGENT: 50.0,
}

async def run():
    items = todo_queue.drain()
    if not items:
        bot_state.idle_counter += 1
        _adjust_plan_interval(idle=True)
        return

    bot_state.idle_counter = 0
    _adjust_plan_interval(idle=False)

    # 按 (type, group_key) 分组，group_key 默认取 payload.session_id
    groups: dict[tuple, list] = {}
    for item in items:
        group_key = item.payload.get("session_id", "__default__")
        key = (item.type, group_key)
        groups.setdefault(key, []).append(item)

    for (item_type, group_key), group_items in groups.items():
        intent = _type_to_intent(item_type)
        highest_urgency = max(group_items, key=lambda i: list(Urgency).index(i.urgency)).urgency
        bonus = URGENCY_BONUS[highest_urgency]

        # 尝试合并进已有 Plan（未被 Attention 占用的同 intent 计划）
        existing = plans_queue.find_by_intent(intent)
        if existing:
            existing.sub_items.extend(group_items)
            existing.priority = max(existing.priority, existing.base_priority + bonus)
            existing.last_touched_at = time.time()
        else:
            base = 20.0
            plans_queue.push(Plan(
                id=str(uuid.uuid4()),
                intent=intent,
                sub_items=group_items,
                priority=base + bonus,
                base_priority=base,
                created_at=time.time(),
                last_touched_at=time.time()
            ))

    # 更新认知负载（积压量越大负载越高）
    total_pending = sum(1 for _ in range(len(items)))
    bot_state.cognitive_load = min(1.0, total_pending / 20.0)

def _type_to_intent(item_type: str) -> str:
    mapping = {
        "qq_msg":        "handle_qq_messages",
        "alarm_reminder": "handle_alarm",
        "system_task":   "self_maintenance",
    }
    return mapping.get(item_type, item_type)

def _adjust_plan_interval(idle: bool):
    if idle:
        bot_state.plan_interval = min(
            bot_state.base_plan_interval * 3,
            bot_state.plan_interval + 1
        )
    else:
        bot_state.plan_interval = 1 if bot_state.cognitive_load > 0.5 \
                                    else bot_state.base_plan_interval
```

***

### 4.6 expander.py — Attention 阶段

**职责**：从 Plans 队列选出一个计划，调用 LLM（携带当前可用工具列表）展开为原子 Actions。

**触发条件**：仅当 Actions 队列为空且无活跃 Attention 时执行。

**关键设计**：LLM 拿到工具注册表的 schema 列表，自主决定用哪些工具、以什么顺序、传什么参数，不由代码硬编码。

```python
import uuid, time
import brain.core.queues as queues
from brain.core.state import bot_state
from brain.core.models import Action, Attention, AttentionState
from brain.core import tool_registry
from brain.model.ModelService import llm_call  # LLM 调用封装

ENERGY_COST_TABLE = {
    "recall_memory":     5.0,
    "generate_response": 15.0,
    "send_qq_message":   2.0,
    "update_memory":     3.0,
    "evaluate_ignore":   1.0,
    # 未知工具的默认值
    "__default__":       5.0,
}

async def run():
    if queues.plans_queue.empty():
        if bot_state.is_idle():
            _maybe_generate_maintenance_plan()
        return

    # 闲时拾取：安静时消化积压的低优先级计划
    if bot_state.is_idle():
        plan = queues.plans_queue.pop_lowest()
    else:
        plan = queues.plans_queue.pop_highest()

    if not plan:
        return

    # 调用 LLM，让它从当前工具列表中规划动作序列
    tool_schemas = tool_registry.get_schemas()
    raw_calls = await llm_call(
        system=_build_system_prompt(),
        tools=tool_schemas,
        message=_build_user_message(plan)
    )

    # LLM 返回的 function call 序列 → Action 对象列表
    actions: list[Action] = []
    for call in raw_calls:
        cost = ENERGY_COST_TABLE.get(call.name, ENERGY_COST_TABLE["__default__"])
        actions.append(Action(
            id=str(uuid.uuid4()),
            tool_name=call.name,
            params=call.arguments,
            energy_cost=cost
        ))

    total_cost = sum(a.energy_cost for a in actions)

    queues.current_attention = Attention(
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        total_energy_estimate=total_cost,
        action_count=len(actions),
        state=AttentionState.ACTIVE,
        created_at=time.time()
    )
    queues.actions_queue.push_all(actions)

def _build_system_prompt() -> str:
    # 可读取 brain/prompts/PLAN.md 和 SOUL.md 拼装
    return "你是一个任务规划器，根据当前计划意图和上下文，选择合适的工具组合成最优动作序列。"

def _build_user_message(plan) -> str:
    return (
        f"当前计划意图：{plan.intent}\n"
        f"涉及事项：{[item.payload for item in plan.sub_items]}\n"
        f"请规划执行该计划所需的动作序列。"
    )

def _maybe_generate_maintenance_plan():
    from brain.core.models import Plan, TodoItem
    # 定期自动生成自维护计划（整理记忆等）
    queues.plans_queue.push(Plan(
        id=str(uuid.uuid4()),
        intent="self_maintenance",
        sub_items=[],
        priority=1.0,
        base_priority=1.0,
        created_at=time.time(),
        last_touched_at=time.time()
    ))
```

***

### 4.7 executor.py — Action 阶段

**职责**：逐个弹出 Action，检查精力，调用 tool\_registry 执行，更新 Attention 进度。

```python
import brain.core.queues as queues
from brain.core.state import bot_state
from brain.core.models import AttentionState
from brain.core import tool_registry
from utils.Logger import logger

MAX_ACTIONS_PER_BEAT = 10

async def run():
    executed = 0

    while not queues.actions_queue.empty() and executed < MAX_ACTIONS_PER_BEAT:
        action = queues.actions_queue.peek()

        # 精力不足：暂停 Attention，等待下一心跳恢复
        if not bot_state.has_energy(action.energy_cost):
            if queues.current_attention:
                queues.current_attention.state = AttentionState.PAUSED
            break

        queues.actions_queue.pop()

        try:
            await tool_registry.call(action.tool_name, action.params)
        except Exception as e:
            logger.error(f"Action {action.tool_name} failed: {e}")
            # 根据策略决定跳过或中断，当前策略：跳过，继续执行后续动作
            executed += 1
            continue

        bot_state.consume_energy(action.energy_cost)
        executed += 1

        if queues.current_attention:
            queues.current_attention.current_index += 1
            # 检查是否完成
            if queues.current_attention.current_index >= queues.current_attention.action_count:
                _complete_attention()
                break  # 本心跳结束，下个心跳再选新 Attention

def _complete_attention():
    if queues.current_attention:
        queues.current_attention.state = AttentionState.COMPLETED
        queues.current_attention = None
```

***

### 4.8 engine.py — 心跳主循环

**职责**：纯编排，调用 planner/expander/executor，不含任何业务逻辑。

```python
import asyncio
from nonebot import get_driver
from brain.core.state import bot_state
from brain.core import queues, planner, expander, executor
from utils.Logger import logger

HEARTBEAT_INTERVAL = 1.0  # 秒

driver = get_driver()

async def _heartbeat_loop():
    while True:
        try:
            await tick()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)

@driver.on_startup
async def start_engine():
    asyncio.create_task(_heartbeat_loop())

async def tick():
    bot_state.heartbeat_count += 1

    # 1. 精力恢复
    bot_state.regenerate_energy()

    # 2. Plan 阶段（按间隔触发）
    if bot_state.heartbeat_count % bot_state.plan_interval == 0:
        await planner.run()

    # 3. Attention 阶段（仅当手上无事）
    if queues.actions_queue.empty() and queues.current_attention is None:
        await expander.run()

    # 4. Action 阶段（暂停状态的 Attention 也应尝试续接）
    if queues.current_attention is not None or not queues.actions_queue.empty():
        await executor.run()
```

***

## 5. 完整依赖关系图

```
main.py
  │  import & register
  ├──▶ services/QQService    ──register tools──▶  brain/core/tool_registry
  ├──▶ services/AlarmService ──register tools──▶  brain/core/tool_registry
  └──▶ brain/core/engine     ──starts heartbeat──▶ ...

brain/core/engine
  ├──▶ planner.py    ──uses──▶  queues / state / models
  ├──▶ expander.py   ──uses──▶  queues / state / tool_registry / ModelService
  └──▶ executor.py   ──uses──▶  queues / state / tool_registry

services/*
  ├──▶ brain/core/tool_registry  (注册工具)
  └──▶ brain/core/queues         (注入 TodoItem)
```

Brain 模块之间的横向依赖：planner / expander / executor 互不直接依赖，全部通过 queues 和 state 这两个单例通信。

***

## 6. 关键算法与策略

### 6.1 Plan 阶段合并规则

使用 `(type, group_key)` 作为哈希键。`group_key` 默认取 `payload.session_id`，保证不同会话的消息不混成一个计划，但同一会话的多条消息合并为一个"处理消息"意图。

### 6.2 优先级计算

```
Plan.priority = base_priority + urgency_bonus
```

明确不使用时间老化（`aging_factor = 0`）。旧计划通过**闲时拾取**单独通路消化，不靠优先级提升来被关注。

### 6.3 LLM 动作展开（expander 核心）

expander 将以下信息传给 LLM：

- **工具列表**：来自 `tool_registry.get_schemas()`，随服务动态变化
- **计划意图**：`plan.intent`
- **事项内容**：`plan.sub_items` 的 payload 摘要
- **Bot 人格**：来自 `SOUL.md`
- Plan 指导: 来自 `PLAN.md` .

LLM 返回 function call 序列，直接映射为 Action 对象。这意味着**无需为每个 intent 维护展开策略表**，新增工具只需注册，LLM 会自动发现并在合适场景使用。

### 6.4 精力评估与消耗

- `energy_cost` 在 expander 展开时由 `ENERGY_COST_TABLE` 按工具名赋值（静态配置）
- 实际执行后从 state 扣减
- 未来可记录预估与实际偏差，做自适应校准

### 6.5 自然节律与闲时拾取

```
activity = (最近10心跳中 ToDo 非空的比例)
闲时条件 = idle_counter >= 10 AND cognitive_load < 0.2

闲时 → Attention 阶段选 priority 最低的计划（消化积压）
长期闲时 → 自动生成 self_maintenance 计划（"没事找事"）
```

### 6.6 拟人化柔性任务

闹钟类任务注入时 `urgency: gentle`，生成的计划优先级较低。展开时第一个 Action 为 `evaluate_ignore`，该工具读取当前 BotState（精力、忙碌程度）和延迟时长，以概率决定本次"忽略"，忽略时将计划标记为"已推迟"并重新注入一个稍后的 gentle 提醒。

### 6.7 权重动态调整

```
任务全部完成：plan.weight *= 0.9
执行中失败：  plan.weight *= 1.1
变化率限制：  ±10% 每次
```

***

## 7. 边界情况与异常处理

### 7.1 精力不足中断与续接

中断时保留 Actions 队列不动，Attention 标记为 `PAUSED`。精力恢复到一定阈值后，executor 会重新尝试执行队列头部 Action，自然续接，无需额外恢复逻辑。

### 7.2 长期精力不足挂起

如果某个 Action 的 energy\_cost 超过 energy\_max，将永远无法执行。需在 expander 展开时做校验：若单个动作预估消耗 > energy\_max \* 0.8，拆分为更小动作或标记为不可行并跳过。

### 7.3 Action 执行失败

当前策略：记录错误、跳过该 Action，继续执行后续。可选策略：重试（在动作末尾重新入队）、中断整个 Attention 并将 Plan 重新入 Plans 队列。

### 7.4 抢占式注意力（未来扩展）

当前为协作式调度（Attention 完成才切换）。未来可在 executor 每步后检查 Plans 队列是否出现极高优先级（urgent）计划，若是则向注意力队列中push紧急事件, 同时将注意力队列入队的自然入队条件改为等于0时才入队, 这样就能实现较为合理的注意力抢占了

***

## 8. 配置参数表

| 参数名                         | 建议默认值  | 说明                 |
| --------------------------- | ------ | ------------------ |
| `HEARTBEAT_INTERVAL`        | 1.0s   | 心跳间隔               |
| `energy_max`                | 1024.0 | 精力上限               |
| `energy_regen_per_beat`     | 5.0    | 每心跳恢复量             |
| `base_plan_interval`        | 3      | 基础计划间隔（心跳数）        |
| `idle_heartbeats_threshold` | 10     | 连续多少心跳低活跃度后视为闲时    |
| `idle_cognitive_threshold`  | 0.2    | 认知负载低于此值才判定闲时      |
| `MAX_ACTIONS_PER_BEAT`      | 10     | 单心跳最大动作执行数，防止帧卡死   |
| `gentle_ignore_chance`      | 0.5    | 柔性任务被忽略的基础概率       |
| `self_maintenance_interval` | 50     | 空闲心跳超过此数后自动生成自维护计划 |
| `ENERGY_COST_TABLE`         | 见 §6.4 | 各工具类型的预估精力消耗       |

***

## 9. 术语表

| 术语             | 定义                                            |
| -------------- | --------------------------------------------- |
| ToDo 队列        | 外部 Services 注入的原始待办事件缓冲区                      |
| Plans 队列       | 合并后的意图级计划，按优先级排序                              |
| Attention      | 当前唯一关注的计划上下文，持有动作进度指针                         |
| Actions 队列     | 当前 Attention 展开的原子动作序列                        |
| 精力             | 全局行动资源，消耗与恢复驱动执行节奏                            |
| tool\_registry | Services 动态注册工具能力的注册表，LLM function call 的工具来源 |
| 自然节律           | 由 ToDo 活跃度决定的忙/闲模式                            |
| 闲时拾取           | 安静期间主动消化低优先级计划的机制                             |
| 柔性意图           | 不要求即时响应的自动任务标记（urgency: gentle）               |
| 协作式调度          | 只有当前 Attention 完成或暂停，才切换新计划                   |
| ActionExpander | expander.py 的核心逻辑，由 LLM + 工具列表动态生成动作序列        |

***

_本文档为 v2.0 修订版，基于 v1.0 增加了动态工具注册机制、重新划定了 brain/services 边界、明确了 planner/expander/executor 的单一职责分工，可直接作为重构实现的基础。_
