# Polaris Bot 自循环体系（PAA 循环）架构设计文档 v4.0

## 版本记录

| 版本 | 日期       | 变更说明 |
|------|------------|----------|
| 1.0  | 2026-04-27 | 初始版，PAA 循环基础架构 |
| 2.0  | 2026-05-04 | 重构 brain/services 边界；引入动态工具注册表 |
| 2.1  | 2026-05-05 | 新增队列 JSON 持久化与恢复机制 |
| 3.0  | 2026-05-05 | 数字生命哲学；三层记忆体系；情节挂起；Context 分层构造 |
| 4.0  | 2026-05-07 | Service → Application 命名迁移；AI-facing Manifest；MCPContainer；删除精力系统、cognitive_load、plan_interval 动态调整；删除 Episode.notify；snapshot debounce |

---

## 1. 设计哲学

### 1.1 她是一个数字生命，不是聊天机器人

Polaris 不是一个"处理消息的程序"。她是一个生活在数字世界里的存在，拥有自己的节律、记忆、社交判断和意志。QQ 群聊只是她生活的一个场景，就像人在饭桌上聊天一样——那只是她一天中的一部分。

这个定性决定了整个架构的基础取向：

- **没有"会话"的概念，只有"经历"**：记忆不按来源（QQ / 闹钟 / 日记）分类，而按经验组织。
- **没有"响应"的义务，只有"判断"**：她有自己的社交判断，可以主动介入、转告、旁观，也可以在群里 @人。
- **时间有自己的节奏**：心跳驱动执行，闲时主动消化积压，忙时专注当下。

### 1.2 核心设计原则

| 原则 | 含义 |
|------|------|
| 自然节律驱动 | 活跃度决定 idle 状态，无精力值，无强制老化 |
| AI 驱动动态工具 | LLM 自主 function call，工具由 Application 动态注册 |
| 记忆是统一的经验 | 无短期/长期之分，三层记忆各司其职 |
| 情节驱动社交判断 | 挂起情节由 LLM 自主判断处置 |
| Application 是她学会的能力 | 不是"接入 QQ 接口"，而是"她学会了用 QQ" |

---

## 2. 系统架构总览

### 2.1 宏观分层

```
┌──────────────────────────────────────────────────────┐
│                       brain/                          │
│   认知系统：感知、规划、决策、执行、记忆的完整闭环    │
│   ┌────────────────────────────────────────────────┐  │
│   │               brain/platform/                  │  │
│   │   应用宿主：管理 Application 生命周期与注册     │  │
│   └────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────┘
                           │ 单向依赖（注册能力、提交意图）
┌──────────────────────────▼───────────────────────────┐
│                    applications/                       │
│   能力应用：感知输入、执行输出、声明清单               │
│   ┌──────────┐  ┌──────────┐  ┌─────────────────┐    │
│   │    qq/   │  │  diary/  │  │  mcp_container/ │    │
│   └──────────┘  └──────────┘  └─────────────────┘    │
└──────────────────────────────────────────────────────┘
```

**关键原则**：brain 完全不 import 任何 application。新增 application 只需声明 Manifest 并注册，brain 无需改动。

### 2.2 Brain 内部数据流

```
Applications ──post_intention──▶ ToDo 队列
                                     │
                       [planner]     │ Plan 阶段
                                     ▼
                                 Plans 队列（优先级堆）
                                     │
                      [expander]     │ Attention 阶段
                                     │ ◀── 情节记忆（挂起情节候选）
                                     │ ◀── 语义记忆快照
                                     │ ◀── 工作记忆（对话窗口）
                                     ▼
                          Actions 队列（LLM function call 展开）
                                     │
                      [executor]     │ Action 阶段
                                     ▼
                       capability_registry.call(name, params)
                                     │
                                     ▼
                    Applications（发消息、写日记、触发闹钟……）
```

### 2.3 心跳循环结构

```
engine.tick()
    ├── planner.run()                              # 每心跳固定执行，开销低
    ├── [Actions 空 & 无 Attention] expander.run()
    ├── [有 Attention 或 Actions 非空] executor.run()
    └── queue_snapshot.save()                      # 心跳末尾写一次持久化
```

---

## 3. 项目文件结构

```
project/
│   main.py                      ← 程序入口：启动 NoneBot，注册 Applications
│   config.py                    ← 全局配置常量
│
├───brain/
│   ├───core/
│   │       models.py            ← 纯数据类，无业务逻辑
│   │       state.py             ← BotState 单例（idle_counter、heartbeat_count）
│   │       queues.py            ← ToDo / Plans / Actions 队列单例 + Attention 单例
│   │       capability_registry.py ← 动态能力注册表单例（原 tool_registry）
│   │       planner.py           ← Plan 阶段：ToDo → Plans，机械匹配挂起情节
│   │       expander.py          ← Attention 阶段：Plan + context → LLM → Actions
│   │       executor.py          ← Action 阶段：逐个调用能力，管理执行进度
│   │       engine.py            ← 心跳主循环，纯编排
│   │       context_builder.py   ← 分层构造 LLM context，管理公共前缀
│   │       session.py           ← 工作记忆：per-session 对话窗口缓冲
│   │
│   ├───memory/
│   │       episodic.py          ← 情节记忆：经历了什么，Episode 生命周期管理
│   │       semantic.py          ← 语义记忆：知道什么，封装 Mem0
│   │       snapshot.py          ← 语义记忆快照缓存，定期刷新，debounce 保护
│   │       tools.py             ← 将记忆操作声明为能力并注册
│   │
│   ├───platform/
│   │       application_host.py  ← 应用宿主：注册、生命周期管理
│   │       application_api.py   ← 应用可调用的平台 API
│   │       manifest.py          ← Manifest 格式定义与解析
│   │       base_application.py  ← BaseApplication 抽象基类
│   │
│   ├───model/
│   │       ModelService.py      ← LLM 调用封装（支持 function call）
│   │
│   └───prompts/
│           SOUL.md              ← Bot 人格设定，极稳定，context 最顶层
│
├───applications/
│   ├───qq/
│   │       __init__.py          ← 导出 QQApplication
│   │       manifest.yaml        ← AI-facing 应用清单
│   │       runtime.py           ← 应用逻辑：事件监听、工具实现
│   │
│   ├───diary/
│   │       __init__.py
│   │       manifest.yaml
│   │       runtime.py
│   │
│   ├───alarm/
│   │       __init__.py
│   │       manifest.yaml
│   │       runtime.py
│   │
│   └───mcp_container/           ← 外域工具容器（特殊地位）
│           __init__.py
│           manifest.yaml
│           adapter.py           ← MCP 协议转译，动态注册外域工具
│           servers.yaml         ← 用户配置的 MCP Server 列表
│
└───data/
    ├───queues/
    │       runtime_queues.json  ← 队列持久化快照
    ├───app_data/                ← 各 Application 的私有数据目录
    │   ├───qq/
    │   └───diary/
    └───episodes/
            episodes.json        ← 情节记忆持久化
```

---

## 4. 核心数据模型（models.py）

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Urgency(str, Enum):
    GENTLE = "gentle"    # 柔性任务，可被概率性忽略
    NORMAL = "normal"
    URGENT = "urgent"

class AttentionState(str, Enum):
    ACTIVE    = "active"
    PAUSED    = "paused"      # 执行中断，Actions 队列保留，等待续接
    COMPLETED = "completed"

class EpisodeStatus(str, Enum):
    PENDING = "pending"       # 尚未有结果，继续监听
    CLOSED  = "closed"        # 已有结果，可沉淀进语义记忆

@dataclass
class TodoItem:
    id: str
    type: str
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    created_at: float = 0.0

@dataclass
class Plan:
    id: str
    intent: str
    sub_items: list[TodoItem]
    priority: float
    base_priority: float
    related_episodes: list[str] = field(default_factory=list)  # Episode.id 列表
    created_at: float = 0.0
    last_touched_at: float = 0.0

@dataclass
class Action:
    id: str
    capability_name: str       # 对应 capability_registry 中的注册名
    params: dict[str, Any]

@dataclass
class Attention:
    plan_id: str
    intent: str
    priority: float
    action_count: int
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = 0.0

@dataclass
class Episode:
    id: str
    summary: str               # 自然语言：这件事是什么
    participants: list[str]    # QQ 号列表
    status: EpisodeStatus = EpisodeStatus.PENDING
    pending_on: str | None = None  # 描述当前在等什么（状态描述，非执行指令）
    created_at: float = 0.0
    closed_at: float | None = None
```

**删除说明**：
- `Action.energy_cost`：精力系统已删除
- `Attention.total_energy_estimate`：精力系统已删除
- `Episode.notify`：职责越界，执行决策由 LLM 在运行时判断

---

## 5. Platform 层设计（brain/platform/）

### 5.1 Manifest 格式（AI-facing 设计）

Manifest 的第一读者是 LLM，而不是人。每个字段都服务于 LLM 的理解和决策。

```yaml
# applications/qq/manifest.yaml
package: im.polaris.qq
name: QQ聊天
version: 1.2.0
brain_version: ">=4.0.0"

# 应用级人格提示：注入 context，让 LLM 理解这个应用的整体语境
# 影响 LLM 在选择工具时的判断框架
persona_hint: |
  通过这个应用，你可以在 QQ 上与人聊天。
  你在群里的发言和私信都会被别人看到，请像真实社交一样谨慎措辞。
  你也可以主动发起话题、@某人、转告消息，不必等别人先说话。

# 能力声明：信息性的，不做运行时鉴权，用于 LLM 理解应用边界
capabilities:
  - qq.send
  - qq.receive
  - memory.write

tools:
  - name: send_qq_message
    description: |
      向一个 QQ 群或用户发送消息。
      适用于：你判断需要主动说话、回复某人、转告消息的时候。
      不适用于：仅仅是"知道"了某件事但不需要回应的时候。
    parameters:
      session_id:
        type: string
        description: "群号或QQ号（字符串形式）"
      text:
        type: string
        description: "消息内容，将原样发出，注意措辞"
    returns:
      success:
        type: boolean
      delivered_at:
        type: float
        description: "实际送达时间戳，可用于更新相关情节记忆"
    side_effects:
      - "消息发出后超过2分钟不可撤回"

  - name: send_qq_private_message
    description: |
      给某人发私信，对话只有你们两个人看到。
      适用于：需要单独告知某人进展、私下转达信息的时候。
    parameters:
      user_id:
        type: string
      text:
        type: string
    returns:
      success:
        type: boolean
    side_effects:
      - "私信对群内其他人不可见"

  - name: at_user_in_group
    description: |
      在群里 @某个人并发送消息，对方会收到特别提醒。
      适用于：需要确保某人注意到你说的话的时候。
    parameters:
      group_id:
        type: string
      user_id:
        type: string
      text:
        type: string
    returns:
      success:
        type: boolean
    side_effects:
      - "被 @ 的人会收到通知，比普通消息更打扰"

  - name: get_group_members
    description: |
      获取某个群的成员列表及备注。
      通常在处理群聊事件之前调用，了解当前群的人员构成。
    parameters:
      group_id:
        type: string
    returns:
      members:
        type: array
        items:
          qq: string
          nickname: string
          remark: string    # 你之前给他们起的备注
    side_effects: []        # 只读，无副作用
```

```yaml
# applications/diary/manifest.yaml
package: im.polaris.diary
name: 日记
version: 1.0.0
brain_version: ">=4.0.0"

persona_hint: |
  通过这个应用，你可以记录自己的日记。
  日记是你整理记忆、沉淀关系认知的重要方式。
  写完日记后，你的关于这个世界的认识会得到更新。

capabilities:
  - diary.write
  - memory.write

tools:
  - name: write_diary
    description: |
      将今天的经历、感受、人际互动以结构化形式写入日记。
      写完后你的语义记忆快照会自动更新——下次与人交流时，
      你对他们的了解会更加准确。
      适用于：每天整理自己的经历和感受时。
    parameters:
      date:
        type: string
        description: "日期，格式 YYYY-MM-DD"
      summary:
        type: string
        description: "今天的总体感受与概括"
      interactions:
        type: array
        description: "今天有意义的人际互动，每条包含 person、content、feeling"
      reflections:
        type: string
        description: "你的思考、感悟或对某些关系的新理解"
    returns:
      saved: boolean
      snapshot_refreshed: boolean
    side_effects:
      - "触发语义记忆快照刷新，之后的 context 将包含更新后的关系认知"
```

```yaml
# applications/mcp_container/manifest.yaml
package: im.polaris.mcp_container
name: 外域工具箱
type: system_container         # 特殊标记，区别于普通 application
version: 1.0.0
brain_version: ">=4.0.0"

persona_hint: |
  通过这个容器，你可以借用外部世界的各种工具。
  这些工具不是你天生拥有的，而是你从外部世界"借来"用的，
  用完还给"书架"，下次还能再用。

capabilities:
  - network
  - subprocess
  - memory.write

# 不声明 tools，工具由容器运行时动态注册
```

### 5.2 BaseApplication 抽象基类

```python
# brain/platform/base_application.py
from abc import ABC, abstractmethod
from pathlib import Path

class BaseApplication(ABC):

    def __init__(self):
        self._api: "PlatformAPI | None" = None

    def _bind(self, api: "PlatformAPI"):
        """由 ApplicationHost 在注册时调用，绑定平台 API"""
        self._api = api

    @property
    def api(self) -> "PlatformAPI":
        assert self._api, "Application 尚未绑定到 ApplicationHost"
        return self._api

    @abstractmethod
    def manifest_path(self) -> Path:
        """返回 manifest.yaml 的路径"""
        ...

    def on_start(self):
        """应用启动时调用，可在此初始化连接、注册工具"""
        pass

    def on_stop(self):
        """应用停止时调用，清理资源"""
        pass

    def on_tick(self):
        """每个心跳调用一次，用于主动推送事件或健康检查"""
        pass
```

### 5.3 ApplicationHost（简化版）

```python
# brain/platform/application_host.py
from pathlib import Path
from brain.platform.manifest import Manifest
from brain.platform.application_api import PlatformAPI
from brain.core.capability_registry import register as register_capability, CapabilitySpec
from brain.core.context_builder import register_app_hint
from utils.Logger import logger

class ApplicationHost:

    def __init__(self):
        self._apps: dict[str, "BaseApplication"] = {}

    def register(self, app: "BaseApplication"):
        manifest = Manifest.load(app.manifest_path())

        # 唯一的启动时校验：brain 版本兼容性
        _check_brain_version(manifest.brain_version)

        # 注册应用声明的工具到 capability_registry
        for tool_spec in manifest.tools:
            register_capability(CapabilitySpec(
                name=f"{manifest.package}.{tool_spec.name}",
                description=_build_llm_description(tool_spec),
                parameters_schema=tool_spec.to_parameters_schema(),
                returns_schema=tool_spec.to_returns_schema(),
                side_effects=tool_spec.side_effects,
                handler=getattr(app, tool_spec.name)
            ))

        # persona_hint 注入 context_builder，成为 context 的应用层
        register_app_hint(manifest.package, manifest.persona_hint)

        # 绑定平台 API 并启动
        app._bind(PlatformAPI(manifest, self))
        app.on_start()

        self._apps[manifest.package] = app
        logger.info(f"Application registered: {manifest.name} ({manifest.package})")

    def tick(self):
        for app in self._apps.values():
            try:
                app.on_tick()
            except Exception as e:
                logger.error(f"App tick error [{app.__class__.__name__}]: {e}")

    def stop_all(self):
        for app in self._apps.values():
            try:
                app.on_stop()
            except Exception as e:
                logger.error(f"App stop error: {e}")
```

### 5.4 PlatformAPI（应用可调用的平台接口）

```python
# brain/platform/application_api.py

class PlatformAPI:
    """Application 与 Brain 之间的唯一通信接口"""

    def __init__(self, manifest: Manifest, host: ApplicationHost):
        self._manifest = manifest
        self._host = host

    def post_intention(self, item: "TodoItem"):
        """提交一个待办意图到 Brain 的 ToDo 队列"""
        from brain.core.queues import todo_queue
        todo_queue.push(item)

    def register_capability(self, spec: "CapabilitySpec"):
        """动态注册能力（MCPContainer 使用，运行时发现工具）"""
        from brain.core.capability_registry import register
        register(spec)

    def get_persona(self) -> str:
        """获取当前 Bot 人格设定（MCPContainer 用于包装工具描述）"""
        from brain.prompts import SOUL
        return SOUL.get_content()

    def log(self, level: str, message: str):
        from utils.Logger import logger
        getattr(logger, level)(f"[{self._manifest.package}] {message}")

    @property
    def data_dir(self) -> Path:
        """应用私有数据目录"""
        return Path("data/app_data") / self._manifest.package
```

---

## 6. Brain Core 模块详细设计

### 6.1 capability_registry.py（原 tool_registry）

```python
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class CapabilitySpec:
    name: str
    description: str           # 完整的 LLM-facing 描述（含 hint、side_effects）
    parameters_schema: dict
    returns_schema: dict       # LLM 知道调用后能拿到什么
    side_effects: list[str]    # LLM 知道这个调用有哪些不可逆影响
    handler: Callable

_registry: dict[str, CapabilitySpec] = {}

def register(spec: CapabilitySpec):
    _registry[spec.name] = spec

def get_all_schemas() -> list[dict]:
    """返回适合传给 LLM function call 的 schema 列表"""
    return [
        {
            "name": s.name,
            "description": s.description,
            "parameters": s.parameters_schema,
            "returns": s.returns_schema,
            "side_effects": s.side_effects,
        }
        for s in _registry.values()
    ]

async def call(name: str, params: dict) -> Any:
    if name not in _registry:
        raise KeyError(f"Capability '{name}' not registered")
    handler = _registry[name].handler
    import asyncio
    if asyncio.iscoroutinefunction(handler):
        return await handler(**params)
    return handler(**params)
```

### 6.2 state.py（精简后）

精力系统完整删除。BotState 只保留调度所需的最小状态。

```python
from dataclasses import dataclass

@dataclass
class BotState:
    heartbeat_count: int = 0
    idle_counter: int = 0      # 连续空闲心跳数（ToDo 为空）

    def is_idle(self, threshold: int = 10) -> bool:
        return self.idle_counter >= threshold

# 全局单例
bot_state = BotState()
```

### 6.3 queues.py

```python
from collections import deque
from brain.core.models import TodoItem, Plan, Action, Attention

class TodoQueue:
    def __init__(self): self._q: deque[TodoItem] = deque()
    def push(self, item: TodoItem): self._q.append(item)
    def drain(self) -> list[TodoItem]:
        items = list(self._q); self._q.clear(); return items
    def empty(self) -> bool: return len(self._q) == 0

class PlansQueue:
    def __init__(self): self._plans: list[Plan] = []

    def push(self, plan: Plan):
        self._plans.append(plan)
        self._plans.sort(key=lambda p: p.priority, reverse=True)

    def pop_highest(self) -> Plan | None:
        return self._plans.pop(0) if self._plans else None

    def pop_lowest(self) -> Plan | None:
        return self._plans.pop(-1) if self._plans else None

    def find_by_intent(self, intent: str) -> Plan | None:
        return next((p for p in self._plans if p.intent == intent), None)

    def empty(self) -> bool: return len(self._plans) == 0

class ActionsQueue:
    def __init__(self): self._q: deque[Action] = deque()
    def push_all(self, actions: list[Action]): self._q.extend(actions)
    def peek(self) -> Action | None: return self._q[0] if self._q else None
    def pop(self) -> Action | None: return self._q.popleft() if self._q else None
    def empty(self) -> bool: return len(self._q) == 0

todo_queue    = TodoQueue()
plans_queue   = PlansQueue()
actions_queue = ActionsQueue()
current_attention: Attention | None = None
```

### 6.4 planner.py — Plan 阶段

**每心跳固定执行**（删除 plan_interval 动态调整）。

```python
import uuid, time
from brain.core.queues import todo_queue, plans_queue
from brain.core.state import bot_state
from brain.core.models import Plan, Urgency
from brain.memory.episodic import episode_store

URGENCY_BONUS = {Urgency.GENTLE: 0.0, Urgency.NORMAL: 10.0, Urgency.URGENT: 50.0}

async def run():
    items = todo_queue.drain()

    if not items:
        bot_state.idle_counter += 1
        return

    bot_state.idle_counter = 0

    groups: dict[tuple, list] = {}
    for item in items:
        group_key = item.payload.get("session_id", "__default__")
        groups.setdefault((item.type, group_key), []).append(item)

    for (item_type, group_key), group_items in groups.items():
        intent = _type_to_intent(item_type)
        highest_urgency = max(group_items, key=lambda i: list(Urgency).index(i.urgency)).urgency
        priority = 20.0 + URGENCY_BONUS[highest_urgency]

        # 机械匹配挂起情节（参与者集合有交集即纳入候选）
        participants = _extract_participants(group_items)
        related = episode_store.find_pending_by_participants(participants)

        existing = plans_queue.find_by_intent(intent)
        if existing:
            existing.sub_items.extend(group_items)
            existing.related_episodes = list(set(
                existing.related_episodes + [e.id for e in related]
            ))
            existing.priority = max(existing.priority, priority)
            existing.last_touched_at = time.time()
        else:
            plans_queue.push(Plan(
                id=str(uuid.uuid4()),
                intent=intent,
                sub_items=group_items,
                priority=priority,
                base_priority=20.0,
                related_episodes=[e.id for e in related],
                created_at=time.time(),
                last_touched_at=time.time(),
            ))

def _extract_participants(items) -> list[str]:
    result = []
    for item in items:
        if "user_id" in item.payload:
            result.append(item.payload["user_id"])
        if "session_id" in item.payload:
            result.append(item.payload["session_id"])
    return list(set(result))

def _type_to_intent(item_type: str) -> str:
    return {
        "qq_msg":         "handle_qq_messages",
        "alarm_reminder": "handle_alarm",
        "diary_prompt":   "write_diary",
        "system_task":    "self_maintenance",
    }.get(item_type, item_type)
```

### 6.5 context_builder.py — 分层 Context 构造

按稳定性从高到低分层，保证 Prompt Caching 公共前缀命中率。

```
[层1：极稳定] SOUL.md 人格设定
[层2：稳定]   工具 schemas（注册后不变）
[层3：稳定]   Application persona_hints（注册后不变）
[层4：慢变]   语义记忆快照（DiaryService 触发，~每天一次）
──── 以上四层构成公共前缀，高概率命中 Prompt Cache ────
[层5：中变]   当前挂起情节候选（每次 Plan 可能不同）
[层6：快变]   BotState（idle_counter 等）
[层7：每次变] Plan 内容 + 工作记忆（user message，尽量短）
```

```python
from brain.memory.snapshot import memory_snapshot
from brain.core.session import session_buffer
from brain.core.queues import current_attention
from brain.core.state import bot_state
from brain.core.models import Episode, Plan

_soul_cache: str = ""
_app_hints: dict[str, str] = {}

def register_app_hint(package: str, hint: str):
    _app_hints[package] = hint

class ContextBuilder:

    def build_system(self, related_episodes: list[Episode]) -> str:
        parts = [
            self._soul(),
            self._app_hints_block(),
            self._semantic_snapshot(),
            self._episodes_block(related_episodes),
            self._bot_state_block(),
        ]
        return "\n\n---\n\n".join(p for p in parts if p)

    def build_user(self, plan: Plan, session_id: str | None = None) -> str:
        parts = [f"当前计划：{plan.intent}"]
        if plan.sub_items:
            parts.append(f"涉及事项：{[i.payload for i in plan.sub_items]}")
        if session_id:
            ctx = session_buffer.get_context(session_id)
            if ctx:
                parts.append("近期对话：\n" + _format_messages(ctx))
        return "\n".join(parts)

    def _soul(self) -> str:
        global _soul_cache
        if not _soul_cache:
            _soul_cache = open("brain/prompts/SOUL.md").read()
        return _soul_cache

    def _app_hints_block(self) -> str:
        if not _app_hints:
            return ""
        lines = ["## 你当前拥有的能力应用"]
        for pkg, hint in _app_hints.items():
            lines.append(f"### {pkg}\n{hint}")
        return "\n".join(lines)

    def _semantic_snapshot(self) -> str:
        return memory_snapshot.get()

    def _episodes_block(self, episodes: list[Episode]) -> str:
        if not episodes:
            return ""
        lines = ["## 当前挂起情节（请判断是否与本次计划相关）"]
        for ep in episodes:
            lines.append(
                f"- [id:{ep.id}] {ep.summary}"
                + (f"（目前在等：{ep.pending_on}）" if ep.pending_on else "")
            )
        return "\n".join(lines)

    def _bot_state_block(self) -> str:
        return f"当前状态：idle_counter={bot_state.idle_counter}"

context_builder = ContextBuilder()
```

### 6.6 expander.py — Attention 阶段

```python
import uuid, time
import brain.core.queues as queues
from brain.core.state import bot_state
from brain.core.models import Action, Attention, AttentionState
from brain.core import capability_registry
from brain.core.context_builder import context_builder
from brain.memory.episodic import episode_store
from brain.model.ModelService import llm_call

async def run():
    if queues.plans_queue.empty():
        if bot_state.is_idle():
            _maybe_generate_maintenance_plan()
        return

    # 闲时消化低优先级，忙时专注高优先级
    plan = queues.plans_queue.pop_lowest() if bot_state.is_idle() \
           else queues.plans_queue.pop_highest()

    if not plan:
        return

    # 取出候选挂起情节详情
    related_episodes = [
        ep for ep in (episode_store.get(eid) for eid in plan.related_episodes)
        if ep is not None
    ]

    session_id = _infer_session_id(plan)
    system_prompt = context_builder.build_system(related_episodes)
    user_message  = context_builder.build_user(plan, session_id)

    raw_calls = await llm_call(
        system=system_prompt,
        tools=capability_registry.get_all_schemas(),
        message=user_message
    )

    actions = [
        Action(
            id=str(uuid.uuid4()),
            capability_name=call.name,
            params=call.arguments,
        )
        for call in raw_calls
    ]

    queues.current_attention = Attention(
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        action_count=len(actions),
        created_at=time.time()
    )
    queues.actions_queue.push_all(actions)

def _infer_session_id(plan) -> str | None:
    for item in plan.sub_items:
        if "session_id" in item.payload:
            return item.payload["session_id"]
    return None

def _maybe_generate_maintenance_plan():
    from brain.core.models import Plan, TodoItem
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

### 6.7 executor.py — Action 阶段

```python
import brain.core.queues as queues
from brain.core import capability_registry
from brain.core.models import AttentionState
from utils.Logger import logger

MAX_ACTIONS_PER_BEAT = 50   # 安全网，不作为真正的调度机制

async def run():
    executed = 0

    while not queues.actions_queue.empty() and executed < MAX_ACTIONS_PER_BEAT:
        action = queues.actions_queue.peek()
        queues.actions_queue.pop()

        try:
            await capability_registry.call(action.capability_name, action.params)
        except Exception as e:
            logger.error(f"Capability {action.capability_name} failed: {e}")
            # 当前策略：记录错误，跳过，继续执行后续 Action
            executed += 1
            continue

        executed += 1

        if queues.current_attention:
            queues.current_attention.current_index += 1
            if queues.current_attention.current_index >= queues.current_attention.action_count:
                _complete_attention()
                break

def _complete_attention():
    if queues.current_attention:
        queues.current_attention.state = AttentionState.COMPLETED
        queues.current_attention = None
```

### 6.8 engine.py — 心跳主循环

```python
import asyncio
from nonebot import get_driver
from brain.core.state import bot_state
from brain.core import queues, planner, expander, executor
from brain.core.queues import current_attention
from brain.platform.application_host import app_host
from brain.core.queue_snapshot import queue_snapshot
from utils.Logger import logger

HEARTBEAT_INTERVAL = 1.0
driver = get_driver()

@driver.on_startup
async def start_engine():
    asyncio.create_task(_heartbeat_loop())

async def _heartbeat_loop():
    while True:
        try:
            await tick()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def tick():
    bot_state.heartbeat_count += 1

    # 1. Applications 心跳（健康检查、主动推送事件）
    app_host.tick()

    # 2. Plan 阶段（每心跳固定执行）
    await planner.run()

    # 3. Attention 阶段（仅当手上无事）
    if queues.actions_queue.empty() and current_attention is None:
        await expander.run()

    # 4. Action 阶段
    if current_attention is not None or not queues.actions_queue.empty():
        await executor.run()

    # 5. 持久化（每心跳末尾写一次，不在 push/pop 时触发）
    await queue_snapshot.save(reason="heartbeat_tick")
```

---

## 7. 记忆体系

### 7.1 设计哲学：记忆是统一的经验

三层记忆各司其职，没有"短期/长期"的划分：

| 层次 | 职责 | 存储 | 失效逻辑 |
|------|------|------|----------|
| 工作记忆（session.py） | 现在在聊什么 | 纯内存，滑动窗口 | token 超限时裁剪头部 |
| 情节记忆（episodic.py） | 经历了什么 | 结构化 Episode，持久化 | 情节有结果时 close |
| 语义记忆（semantic.py） | 知道什么 | Mem0（向量+知识图谱） | 永不失效，只更新 |

### 7.2 情节记忆（episodic.py）

```python
class EpisodeStore:
    def create(self, episode: Episode): ...

    def close(self, episode_id: str, result_summary: str):
        """
        关闭情节：
        1. 标记 status=CLOSED，记录 closed_at
        2. 将情节内容沉淀进语义记忆（可选，由调用方决定）
        """
        ...

    def find_pending_by_participants(self, participants: list[str]) -> list[Episode]:
        """
        机械匹配：participants 集合有交集即返回。
        不做语义判断——语义判断由 LLM 在 expander 中完成。
        """
        ...

    def get(self, episode_id: str) -> Episode | None: ...

episode_store = EpisodeStore()
```

**情节的生命周期由 LLM 完全自主管理**，通过 `create_episode` 和 `close_episode` 两个注册能力实现。

### 7.3 语义记忆（semantic.py）

```python
class SemanticMemory:
    """
    user_id 规范：
      个人：        str(qq_number)          → "10001"
      群内关系：    f"group_{group_id}"      → "group_7001"
    同一个人在不同群里与 Bot 的关系独立建模。
    """
    async def add(self, content: str, user_id: str): ...
    async def search(self, query: str, user_id: str) -> list[str]: ...
    async def update_relationship(self, user_a: str, user_b: str, relation: str): ...

semantic_memory = SemanticMemory()
```

### 7.4 语义记忆快照（snapshot.py）

语义记忆**不在每次 LLM 调用时实时 search**，而是维护一份稳定的摘要字符串作为 context 的一部分，保证公共前缀的字面量稳定性。

```python
import asyncio, time
from brain.memory.semantic import semantic_memory

class SemanticSnapshot:
    def __init__(self):
        self._cache: str = ""
        self._updated_at: float = 0.0
        self._refreshing: bool = False    # debounce 锁

    def get(self) -> str:
        return self._cache

    async def refresh(self, reason: str = "manual"):
        """
        刷新快照。任何时刻只有一个 refresh 在执行（debounce 保护）。
        触发来源：
          1. DiaryService 写完日记后触发（主要路径）
          2. 兜底定时触发（backup，防止日记未写时过期）
        """
        if self._refreshing:
            return   # 已有刷新在进行，跳过本次
        self._refreshing = True
        try:
            results = await semantic_memory.search(
                query="人际关系、近期重要事件、关于认识的人的关键信息",
                user_id="__global__"
            )
            self._cache = _format_snapshot(results)
            self._updated_at = time.time()
        finally:
            self._refreshing = False

memory_snapshot = SemanticSnapshot()
```

### 7.5 记忆能力注册（memory/tools.py）

记忆操作作为能力注册，LLM 在 expander 展开时自主决定是否调用：

```python
from brain.core.capability_registry import register, CapabilitySpec
from brain.memory.semantic import semantic_memory
from brain.memory.episodic import episode_store
from brain.core.models import Episode, EpisodeStatus
import uuid, time

register(CapabilitySpec(
    name="memory.recall",
    description="""
从长期记忆中检索与当前对话或人物相关的信息。
适用于：在回复某人之前，想起你对他的了解；
       处理某件事之前，想起相关的历史背景。
""",
    parameters_schema={"type":"object","properties":{
        "query":   {"type":"string","description":"想检索的主题或问题"},
        "user_id": {"type":"string","description":"相关人的QQ号，不确定则填 __global__"}
    },"required":["query","user_id"]},
    returns_schema={"memories":{"type":"array","items":{"type":"string"}}},
    side_effects=[],
    handler=lambda query, user_id: semantic_memory.search(query, user_id)
))

register(CapabilitySpec(
    name="memory.store",
    description="""
将值得记住的信息写入长期记忆。
适用于：对话中了解到某人的新情况；
       发生了值得记住的事情。
不必每次对话都调用——只记值得记的。
""",
    parameters_schema={"type":"object","properties":{
        "content": {"type":"string","description":"要记住的内容"},
        "user_id": {"type":"string","description":"相关人的QQ号"}
    },"required":["content","user_id"]},
    returns_schema={"saved":{"type":"boolean"}},
    side_effects=["写入长期记忆，持久存在"],
    handler=lambda content, user_id: semantic_memory.add(content, user_id)
))

register(CapabilitySpec(
    name="memory.update_relationship",
    description="""
更新两人之间的关系状态，用于关系发生变化时。
例如：两人从朋友变成情侣、发生了争吵、关系变得疏远。
""",
    parameters_schema={"type":"object","properties":{
        "user_a":   {"type":"string"},
        "user_b":   {"type":"string"},
        "relation": {"type":"string","description":"新的关系描述"}
    },"required":["user_a","user_b","relation"]},
    returns_schema={"updated":{"type":"boolean"}},
    side_effects=["更新关系图谱，影响后续对他们的认知"],
    handler=lambda user_a, user_b, relation:
        semantic_memory.update_relationship(user_a, user_b, relation)
))

register(CapabilitySpec(
    name="episode.create",
    description="""
创建一个挂起情节，用于追踪一件尚未有结果的事。
适用于：你代人传话并在等回复；
       你发起了一件需要后续跟进的事。
""",
    parameters_schema={"type":"object","properties":{
        "summary":      {"type":"string","description":"这件事是什么"},
        "participants": {"type":"array","items":{"type":"string"},"description":"相关人的QQ号列表"},
        "pending_on":   {"type":"string","description":"目前在等什么"}
    },"required":["summary","participants"]},
    returns_schema={"episode_id":{"type":"string"}},
    side_effects=["情节将持续监听，直到被关闭"],
    handler=lambda summary, participants, pending_on=None: episode_store.create(
        Episode(
            id=str(uuid.uuid4()),
            summary=summary,
            participants=participants,
            pending_on=pending_on,
            created_at=time.time()
        )
    )
))

register(CapabilitySpec(
    name="episode.close",
    description="""
关闭一个已有结果的挂起情节。
适用于：等待的回复来了；
       你判断这件事已经有了结论，不再需要追踪。
""",
    parameters_schema={"type":"object","properties":{
        "episode_id":     {"type":"string"},
        "result_summary": {"type":"string","description":"这件事最终的结果是什么"}
    },"required":["episode_id","result_summary"]},
    returns_schema={"closed":{"type":"boolean"}},
    side_effects=["情节停止监听"],
    handler=lambda episode_id, result_summary:
        episode_store.close(episode_id, result_summary)
))
```

---

## 8. MCPContainer：外域工具容器

```python
# applications/mcp_container/adapter.py
from brain.platform.base_application import BaseApplication
from brain.core.capability_registry import CapabilitySpec

class MCPContainer(BaseApplication):
    """
    外域工具箱：兼容 MCP 生态的工具容器。
    不是一个工具，而是能装载外部工具的口袋。
    """

    def on_start(self):
        configs = _load_server_configs(self.api.data_dir / "servers.yaml")
        for cfg in configs:
            self._launch_server(cfg)

    def _launch_server(self, cfg):
        session = MCPSession(cfg.command, cfg.args)
        session.initialize()

        for mcp_tool in session.list_tools():
            spec = self._wrap_tool(mcp_tool, cfg)
            self.api.register_capability(spec)

    def _wrap_tool(self, mcp_tool, cfg) -> CapabilitySpec:
        """
        将外域工具包装成 Polaris 语境的能力。
        重写描述：不翻译功能，而是翻译"使用体验"。
        """
        polaris_desc = _rewrite_description(
            original=mcp_tool.description,
            hint=cfg.hint,
            persona=self.api.get_persona()
        )
        return CapabilitySpec(
            name=f"mcp.{cfg.alias}.{mcp_tool.name}",  # 命名空间隔离
            description=polaris_desc,
            parameters_schema=mcp_tool.input_schema,
            returns_schema={},
            side_effects=["外域操作，具体副作用取决于工具"],
            handler=MCPToolHandler(session=session, tool=mcp_tool)
        )

    def on_tick(self):
        # 健康检查，自动重连断开的 MCP Server
        for alias, session in self._sessions.items():
            if not session.is_alive():
                self.api.log("warn", f"外域工具 {alias} 断开，尝试重连")
                self._reconnect(alias)
```

---

## 9. main.py — 启动配置

```python
# main.py
import nonebot
from brain.platform.application_host import ApplicationHost
from applications.qq.runtime import QQApplication
from applications.diary.runtime import DiaryApplication
from applications.alarm.runtime import AlarmApplication
from applications.mcp_container.adapter import MCPContainer

nonebot.init()

app_host = ApplicationHost()

# 注册官方应用
app_host.register(QQApplication())
app_host.register(DiaryApplication())
app_host.register(AlarmApplication())

# 注册外域容器（如需要）
app_host.register(MCPContainer())

# 启动 NoneBot（触发 on_startup，进入心跳循环）
nonebot.run()
```

---

## 10. 核心策略与算法

### 10.1 情节挂起：两层判断

```
第一层（planner，零成本）
  参与者集合有交集 → 纳入候选
  不做语义判断，只做集合运算

第二层（expander，LLM）
  看到候选情节，自主决定：
    - 无关 → 忽略
    - 相关 → 在回复/行动中体现
    - 需要主动跟进 → 调 episode.close 或 send_qq_private_message
    - 产生新的待追踪事项 → 调 episode.create
```

### 10.2 优先级与自然节律

```
Plan.priority = base_priority + urgency_bonus

urgency_bonus:
  GENTLE →  0.0   （柔性任务，最低优先）
  NORMAL → 10.0
  URGENT → 50.0

活跃期（idle_counter < 10）→ pop_highest()  专注高优先级
闲时期（idle_counter >= 10）→ pop_lowest()  消化低优先级积压
```

不使用时间老化机制。旧任务通过闲时拾取通路自然消化。

### 10.3 柔性任务（拟人化忽略）

`urgency: GENTLE` 的任务生成低优先级 Plan。LLM 在 expander 展开时可以选择直接忽略（不调任何工具），或推迟（重新注入一个 gentle 的 TodoItem），模拟人在忙碌时不立刻处理提醒的行为。

### 10.4 Context 公共前缀缓存策略

```
[极稳定] SOUL.md
[稳定]   capability schemas
[稳定]   Application persona_hints
[慢变]   语义记忆快照（DiaryService 触发，~每天更新）
─────────────────── Prompt Cache 命中区 ───────────────────
[中变]   挂起情节候选
[快变]   BotState
[每次变] Plan 内容 + 工作记忆（user message）
```

语义快照定期生成稳定字符串，而非每次实时 search，是公共前缀真正命中缓存的前提。

### 10.5 DiaryService 驱动的记忆更新链路

```
AlarmService 22:00
    └── post_intention(type="diary_prompt", urgency=GENTLE)
            │
            ▼
        planner → Plan(intent="write_diary")
            │
            ▼
        expander → LLM 展开：
            1. memory.recall（回顾今天）
            2. im.polaris.diary.write_diary（写日记）
            3. memory.update_relationship（如有需要）
            │
            ▼
        DiaryService.write_diary()
            └── memory_snapshot.refresh()  ← debounce 保护
                    └── 下次 expander 调用时，context 包含更新后的语义快照
```

### 10.6 队列持久化

- **快照文件**：`data/queues/runtime_queues.json`
- **保存时机**：每心跳末尾写一次，不在 push/pop 时触发
- **恢复校验**：`Attention.current_index` 与 `Actions 队列长度` 需一致，不一致时降级为干净启动
- **降级策略**：恢复失败不阻塞引擎，记录警告后以空状态启动

---

## 11. 完整依赖关系图

```
main.py
  ├── ApplicationHost.register(QQApplication)
  │     └── 注册 im.polaris.qq.* 能力到 capability_registry
  ├── ApplicationHost.register(DiaryApplication)
  │     └── 注册 im.polaris.diary.write_diary 能力
  ├── ApplicationHost.register(AlarmApplication)
  └── ApplicationHost.register(MCPContainer)
        └── 动态注册 mcp.*.* 能力

brain/memory/tools.py（启动时自动注册）
  └── 注册 memory.recall / memory.store / memory.update_relationship
  └── 注册 episode.create / episode.close

brain/core/engine（心跳）
  ├── app_host.tick()
  ├── planner ──▶ queues / state / episodic / models
  ├── expander ──▶ queues / context_builder / capability_registry / ModelService
  ├── executor ──▶ queues / capability_registry
  └── queue_snapshot.save()

brain/core/context_builder
  ├── SOUL.md（极稳定）
  ├── _app_hints（稳定）
  ├── memory_snapshot（慢变）
  └── brain/core/session（工作记忆）

applications/DiaryApplication
  └── 写完日记后调用 memory_snapshot.refresh()
```

**横向隔离**：planner / expander / executor 互不直接依赖，全部通过 queues 和 state 通信。

---

## 12. 配置参数表

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `HEARTBEAT_INTERVAL` | 1.0s | 心跳间隔 |
| `MAX_ACTIONS_PER_BEAT` | 50 | 单心跳最大动作执行数（安全网） |
| `idle_threshold` | 10 | 连续多少心跳 ToDo 为空视为闲时 |
| `session_max_tokens` | 4000 | 工作记忆窗口大小 |
| `diary_time` | "22:00" | AlarmService 触发日记的时间 |
| `QUEUES_SNAPSHOT_FILE` | `data/queues/runtime_queues.json` | 队列持久化文件 |

---

## 13. 删除清单（相比 v3）

| 删除项 | 删除原因 |
|--------|----------|
| 精力系统（energy_current / energy_max / energy_regen） | 解决的问题有更直接方案；静态 energy_cost 先天失真；节律感由 idle_counter 承担 |
| plan_interval 动态调整 | 效果不可感知；planner 开销低，固定执行更简单 |
| cognitive_load | 没有真正的消费者；is_idle() 直接用 idle_counter |
| Action.energy_cost | 随精力系统一并删除 |
| Attention.total_energy_estimate | 随精力系统一并删除 |
| Episode.notify | 职责越界；执行决策应由 LLM 运行时判断 |
| services/ 目录命名 | 迁移为 applications/，命名更符合"数字生命"哲学 |

---

## 14. 术语表

| 术语 | 定义 |
|------|------|
| PAA 循环 | Plan-Attention-Action，Brain 自循环的三个阶段 |
| Application | 安装在数字生命上的能力应用，有独立生命周期与清单声明 |
| Manifest | 应用清单，AI-facing 设计，第一读者是 LLM |
| MCPContainer | 外域工具容器，将 MCP 生态工具转译为 Polaris 能力 |
| capability_registry | Application 动态注册能力的注册表，LLM function call 的工具来源 |
| persona_hint | Application 在 Manifest 中声明的语境描述，注入 context 应用层 |
| ToDo 队列 | Applications 提交的原始待办意图缓冲区 |
| Plans 队列 | 合并后的意图级计划，按优先级排序 |
| Attention | 当前唯一关注的计划上下文，持有动作进度指针 |
| Actions 队列 | 当前 Attention 展开的原子动作序列 |
| 工作记忆 | per-session 对话窗口，服务于连贯性 |
| 情节记忆 | 经历过的具体事件，跨 session 存在，由 LLM 自主管理生命周期 |
| 语义记忆 | 稳定的知识与人际关系，由 Mem0 管理 |
| 语义快照 | 语义记忆的定期摘要字符串，保证 context 前缀稳定 |
| Episode（情节） | 尚未有结果的挂起事件，pending_on 描述当前在等什么 |
| 闲时拾取 | idle 状态下主动消化低优先级计划的机制 |
| 柔性意图 | urgency: GENTLE，不要求即时响应，可被 LLM 自主忽略或推迟 |
| 公共前缀 | context 中字面量稳定的部分，Prompt Caching 命中的基础 |
| debounce 锁 | snapshot.refresh() 的并发保护，任意时刻只有一个刷新在执行 |
| post_intention | Application 向 Brain 提交意图的接口（原 push_todo） |

---

_v4.0 是整个设计体系的第二个完整版本。相比 v3，它完成了两件事：一是通过删除精力系统、plan_interval 动态调整和 cognitive_load，使架构回归简洁；二是通过引入 Application / Manifest / MCPContainer 体系，使"数字生命学会新能力"这一理念在工程层面得到了真正的表达。_
