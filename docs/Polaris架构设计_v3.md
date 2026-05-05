# Polaris Bot 自循环体系（PAA 循环）架构设计文档 v3.0

## 版本记录

| 版本 | 日期       | 变更说明                                                                                                    |
| ---- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| 1.0  | 2026-04-27 | 初始版，Plan-Attention-Action 循环基础架构                                                                  |
| 2.0  | 2026-05-04 | 重构 brain/services 边界；引入动态工具注册表；明确模块职责                                                  |
| 2.1  | 2026-05-05 | 新增三层队列 JSON 持久化与恢复机制                                                                          |
| 3.0  | 2026-05-05 | 引入数字生命设计哲学；重构记忆体系（情节/语义/工作）；新增情节挂起机制；引入 Context 分层构造与前缀缓存优化 |

---

## 1. 设计哲学

### 1.1 她是一个数字生命，不是聊天机器人

Polaris 不是一个"处理消息的程序"。她是一个生活在数字世界里的存在，拥有自己的节律、记忆、社交判断和意志。QQ 群聊只是她生活的一个场景，就像人在饭桌上聊天一样——那只是她一天中的一部分。

这个定性决定了整个架构的基础取向：

- **没有"会话"的概念，只有"经历"**：她的记忆不按来源（QQ / 闹钟 / 日记）分类，而按经验组织。
- **没有"响应"的义务，只有"判断"**：她有自己的社交判断，可以选择主动介入、转告、旁观，也可以在群里 @人，而不是被动等待指令后执行。
- **时间有自己的节奏**：精力值驱动执行节奏，闲时主动消化积压，忙时专注当下，呈现自然的作息感。

### 1.2 核心设计原则

| 原则             | 含义                                              |
| ---------------- | ------------------------------------------------- |
| 精力作为硬通货   | 所有行动消耗精力，不足时暂停，恢复后续接          |
| 自然节律驱动     | 活跃度决定 plan_interval，无强制老化机制          |
| AI 驱动动态工具  | LLM 自主 function call，工具由 services 动态注册  |
| 记忆是统一的经验 | 无短期/长期之分，只有情节记忆、语义记忆、工作记忆 |
| 情节驱动社交判断 | 挂起情节由 LLM 自主判断处置，不需要人触发         |

---

## 2. 系统架构总览

### 2.1 宏观分层

```
┌───────────────────────────────────────────────────┐
│                     brain/                         │
│  认知系统：感知、规划、决策、执行、记忆的完整闭环  │
│  不依赖任何具体外围服务                            │
└───────────────────┬───────────────────────────────┘
                    │ 单向依赖（注册工具、注入事件）
┌───────────────────▼───────────────────────────────┐
│                   services/                        │
│  外部适配器：感知输入、执行输出                    │
│  启动时向 brain 注册自己的工具能力                 │
└───────────────────────────────────────────────────┘
```

**关键原则**：brain 完全不 import 任何 service。新增 service 只需注册工具，brain 无需改动。

### 2.2 Brain 内部数据流

```
Services ──push──▶ ToDo 队列
                       │
             [planner] │ Plan 阶段
                       ▼
                   Plans 队列（优先级堆）
                       │
            [expander] │ Attention 阶段
                       │ ◀── 情节记忆（挂起情节候选）
                       │ ◀── 语义记忆快照
                       │ ◀── 工作记忆（当前 context 窗口）
                       ▼
               Actions 队列（LLM function call 展开）
                       │
            [executor] │ Action 阶段
                       ▼
              tool_registry.call(name, params)
                       │
                       ▼
             外围 Services（发消息、写日记、触发闹钟……）
```

### 2.3 心跳循环结构

```
engine.tick()
    ├── state.regenerate_energy()
    ├── [每 plan_interval 心跳] planner.run()
    ├── [Actions 空 & 无 Attention] expander.run()
    └── [有 Attention 或 Actions 非空] executor.run()
```

---

## 3. 项目文件结构

```
project/
│   main.py                  ← 程序入口，启动 NoneBot，注册所有 Services
│   config.py                ← 全局配置常量
│
├───brain/
│   ├───core/
│   │       models.py        ← 纯数据类，无业务逻辑
│   │       state.py         ← BotState 单例（精力、认知负载、心跳计数）
│   │       queues.py        ← ToDo / Plans / Actions 队列单例 + Attention 单例
│   │       tool_registry.py ← 动态工具注册表单例
│   │       planner.py       ← Plan 阶段：ToDo → Plans，机械匹配挂起情节
│   │       expander.py      ← Attention 阶段：Plan + context → LLM → Actions
│   │       executor.py      ← Action 阶段：逐个调用工具，管理精力消耗
│   │       engine.py        ← 心跳主循环，纯编排
│   │       context_builder.py ← 分层构造 LLM context，管理公共前缀
│   │       session.py       ← 工作记忆：per-session 对话窗口缓冲
│   │
│   ├───memory/
│   │       episodic.py      ← 情节记忆：经历了什么，管理 Episode 的生命周期
│   │       semantic.py      ← 语义记忆：知道什么，封装 Mem0 的 add/search
│   │       snapshot.py      ← 语义记忆快照缓存，定期刷新，保证 context 前缀稳定
│   │       tools.py         ← 将记忆操作注册为工具（recall / store / update_relation）
│   │
│   ├───model/
│   │       ModelService.py  ← LLM 调用封装（支持 function call）
│   │
│   └───prompts/
│           SOUL.md          ← Bot 人格设定，极稳定，作为 context 最顶层
│           PLAN.md          ← expander 系统提示补充
│
└───services/
    ├───QQService/
    │       core.py          ← OneBot 适配器，注册 QQ 相关工具，注入 TodoItem
    ├───AlarmService/
    │       core.py          ← 定时任务，注册闹钟工具，注入 alarm_reminder 事件
    ├───DiaryService/
    │       core.py          ← 日记服务，注册结构化日记写入工具，触发语义记忆更新
    └───TestService/
            core.py          ← 测试用 Mock，注册假工具，用于场景回放
```

---

## 4. 核心数据模型（models.py）

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Urgency(str, Enum):
    GENTLE = "gentle"   # 柔性任务，可被忽略
    NORMAL = "normal"
    URGENT = "urgent"

class AttentionState(str, Enum):
    ACTIVE    = "active"
    PAUSED    = "paused"     # 精力不足，保留队列等待续接
    COMPLETED = "completed"

class EpisodeStatus(str, Enum):
    PENDING = "pending"      # 尚未有结果，继续监听
    CLOSED  = "closed"       # 已有结果，写入情节记忆

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
    tool_name: str
    params: dict[str, Any]
    energy_cost: float = 1.0

@dataclass
class Attention:
    plan_id: str
    intent: str
    priority: float
    total_energy_estimate: float
    action_count: int
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    created_at: float = 0.0

@dataclass
class Episode:
    id: str
    summary: str                     # 自然语言描述这件事是什么
    participants: list[str]          # QQ 号列表
    status: EpisodeStatus = EpisodeStatus.PENDING
    pending_on: str | None = None    # "等 B 回复" 之类的自然语言描述
    notify: str | None = None        # "完成后私信 10001"
    created_at: float = 0.0
    closed_at: float | None = None
```

---

## 5. 核心模块详细设计

### 5.1 tool_registry.py — 动态工具注册表

Services 启动时自报家门，LLM 在 expander 中自主选择工具。这是 v2 引入的最重要的架构决策，**brain 不预定义任何工具接口**。

```python
@dataclass
class Tool:
    name: str
    description: str         # 给 LLM 看，决定它是否选择此工具
    parameters_schema: dict  # JSON Schema
    handler: Callable

_registry: dict[str, Tool] = {}

def register(tool: Tool): ...
def get_schemas() -> list[dict]: ...      # 传给 LLM function call
async def call(name: str, params: dict):  # executor 调用
    ...
```

**Service 注册示例**：

```python
# services/QQService/core.py
register(Tool(
    name="send_qq_message",
    description="向指定 QQ 群或用户发送文本消息",
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
```

---

### 5.2 记忆体系

#### 设计哲学：记忆是统一的经验

不存在"短期记忆"和"长期记忆"的概念区分。只有三种形态：

| 类型                    | 职责                         | 存储形态                     |
| ----------------------- | ---------------------------- | ---------------------------- |
| 工作记忆（session.py）  | 当前在聊什么，服务于连贯性   | 纯内存，per-session 滑动窗口 |
| 情节记忆（episodic.py） | 她经历了什么，服务于事件追踪 | 结构化 Episode 对象，持久化  |
| 语义记忆（semantic.py） | 她知道什么，服务于关系感知   | Mem0（向量 + 知识图谱）      |

**情节的结束由结果决定，而非时间**。一件事有了结果（B 回复了、饭局结束了），对应的情节才 closed，沉淀到情节记忆，其中提炼出的稳定知识写入语义记忆。

#### 工作记忆（session.py）

```python
class SessionBuffer:
    """per session_id 的对话上下文滑动窗口"""
    def __init__(self, max_tokens: int = 4000):
        self._sessions: dict[str, deque[Message]] = {}
        self.max_tokens = max_tokens

    def append(self, session_id: str, msg: Message): ...
    def get_context(self, session_id: str) -> list[Message]: ...
    def _trim(self, session_id: str): ...  # 超出 token 预算时从头裁剪

session_buffer = SessionBuffer()
```

- 按 `session_id`（QQ号或群号）隔离，不跨 session 共享。
- 只保证本次对话的连贯性，不承担跨时间的关系感知。

#### 情节记忆（episodic.py）

```python
class EpisodeStore:
    def create(self, episode: Episode): ...
    def close(self, episode_id: str, summary: str): ...
    def find_pending_by_participants(self, participants: list[str]) -> list[Episode]:
        """planner 的机械匹配：参与者集合有交集即返回"""
        ...
    def get_all_pending(self) -> list[Episode]: ...

episode_store = EpisodeStore()
```

#### 语义记忆（semantic.py）

封装 Mem0，提供干净的接口。`user_id` 在此层统一规范：

```python
# user_id 规范：
#   个人：str(qq_number)               → "10001"
#   群内关系：f"group_{group_id}"      → "group_7001"
# 同一个人在不同群里与 bot 的关系独立建模

class SemanticMemory:
    async def add(self, content: str, user_id: str): ...
    async def search(self, query: str, user_id: str) -> list[str]: ...
    async def update_relationship(self, user_a: str, user_b: str, relation: str): ...

semantic_memory = SemanticMemory()
```

#### 语义记忆快照（snapshot.py）

语义记忆**不在每次 LLM 调用时实时 search**，而是定期生成摘要字符串缓存在内存里。这保证了 context 里语义记忆部分的字面量稳定，使 Prompt Caching 的公共前缀真正命中。

```python
class SemanticSnapshot:
    _cache: str = ""
    _updated_at: float = 0.0

    def get(self) -> str:
        return self._cache

    async def refresh(self):
        """由 DiaryService 在日记写入后触发，或心跳周期性触发"""
        summary = await semantic_memory.search("人际关系与近期重要事件", user_id="__global__")
        self._cache = _format_snapshot(summary)
        self._updated_at = time.time()

memory_snapshot = SemanticSnapshot()
```

#### 记忆工具注册（memory/tools.py）

记忆操作作为工具注册进 `tool_registry`，LLM 在 expander 展开时自主决定是否调用：

```python
register(Tool(
    name="recall_memory",
    description="从长期记忆中检索与当前对话或人物相关的信息，在回复前使用",
    parameters_schema={...},
    handler=lambda query, user_id: semantic_memory.search(query, user_id)
))

register(Tool(
    name="store_memory",
    description="将本次交互中值得记住的信息写入长期记忆",
    parameters_schema={...},
    handler=lambda content, user_id: semantic_memory.add(content, user_id)
))

register(Tool(
    name="update_relationship",
    description="更新两个人之间的关系状态",
    parameters_schema={...},
    handler=lambda user_a, user_b, relation: semantic_memory.update_relationship(...)
))

register(Tool(
    name="create_episode",
    description="创建一个新的挂起情节，用于追踪一件尚未有结果的事",
    parameters_schema={...},
    handler=lambda summary, participants, pending_on, notify:
        episode_store.create(Episode(...))
))

register(Tool(
    name="close_episode",
    description="关闭一个已有结果的挂起情节",
    parameters_schema={...},
    handler=lambda episode_id, summary: episode_store.close(episode_id, summary)
))
```

---

### 5.3 planner.py — Plan 阶段

**职责**：ToDo → Plans（合并、优先级），以及挂起情节的机械匹配。

```python
async def run():
    items = todo_queue.drain()
    if not items:
        bot_state.idle_counter += 1
        _adjust_plan_interval(idle=True)
        return

    bot_state.idle_counter = 0
    _adjust_plan_interval(idle=False)

    groups = _group_by_type_and_session(items)

    for (item_type, group_key), group_items in groups.items():
        intent = _type_to_intent(item_type)
        priority = _calc_priority(group_items)

        # 机械匹配挂起情节（只看参与者集合，不做语义判断）
        participants = _extract_participants(group_items)
        related_episodes = episode_store.find_pending_by_participants(participants)

        existing = plans_queue.find_by_intent(intent)
        if existing:
            existing.sub_items.extend(group_items)
            existing.related_episodes = list(set(
                existing.related_episodes + [e.id for e in related_episodes]
            ))
            existing.priority = max(existing.priority, priority)
        else:
            plans_queue.push(Plan(
                id=str(uuid.uuid4()),
                intent=intent,
                sub_items=group_items,
                priority=priority,
                base_priority=20.0,
                related_episodes=[e.id for e in related_episodes],
                created_at=time.time(),
            ))

    bot_state.cognitive_load = min(1.0, len(items) / 20.0)
```

**关键设计**：机械匹配只做参与者集合的交集判断，成本为零。语义判断留给 expander 的 LLM。

---

### 5.4 context_builder.py — 分层 Context 构造

**核心目标**：最大化 Prompt Caching 的公共前缀命中率，同时保证 LLM 有足够的上下文做判断。

按稳定性从高到低分层，越靠前越稳定，越利于缓存：

```python
class ContextBuilder:

    def build_system(
        self,
        related_episodes: list[Episode],
        session_id: str | None = None
    ) -> str:
        parts = [
            self._soul(),              # 极稳定：SOUL.md，几乎不变
            self._tool_hints(),        # 稳定：工具注册后不变
            self._semantic_snapshot(), # 慢变：DiaryService 触发刷新
            self._episodes(related_episodes),  # 中变：当前挂起候选
            self._bot_state(),         # 快变：每心跳变化
        ]
        # 前三层在大多数请求中字面量完全相同 → 高概率命中缓存
        return "\n\n---\n\n".join(filter(None, parts))

    def build_user(self, plan: Plan, session_id: str | None = None) -> str:
        parts = [f"当前计划：{plan.intent}"]
        if plan.sub_items:
            parts.append(f"涉及事项：{[i.payload for i in plan.sub_items]}")
        if session_id:
            ctx = session_buffer.get_context(session_id)
            if ctx:
                parts.append("近期对话上下文：" + _format_messages(ctx))
        # user message 尽量短，只放动态内容
        return "\n".join(parts)

    def _soul(self) -> str:
        return _read_once("brain/prompts/SOUL.md")   # 启动时读入缓存

    def _semantic_snapshot(self) -> str:
        return memory_snapshot.get()                 # 快照字符串，字面量稳定

    def _episodes(self, episodes: list[Episode]) -> str:
        if not episodes:
            return ""
        lines = ["当前挂起情节（你需要判断它们是否与本次计划相关）："]
        for ep in episodes:
            lines.append(f"- [{ep.id}] {ep.summary}（等待：{ep.pending_on}，完成后：{ep.notify}）")
        return "\n".join(lines)

    def _bot_state(self) -> str:
        s = bot_state
        return f"当前状态：精力 {s.energy_current:.0f}/{s.energy_max}，" \
               f"认知负载 {s.cognitive_load:.1f}"
```

---

### 5.5 expander.py — Attention 阶段

**职责**：选取计划，构造 context，调用 LLM，展开为 Action 序列。

**关键设计**：LLM 在此处做所有的社交判断——挂起情节是否相关、是否需要主动通知、用哪些工具、以什么顺序。

```python
async def run():
    if plans_queue.empty():
        if bot_state.is_idle():
            _maybe_generate_maintenance_plan()
        return

    plan = plans_queue.pop_lowest() if bot_state.is_idle() \
           else plans_queue.pop_highest()

    # 取出本计划关联的挂起情节详情
    related_episodes = [
        episode_store.get(eid)
        for eid in plan.related_episodes
        if episode_store.get(eid)
    ]

    # 推断本次对话的 session_id（用于注入工作记忆）
    session_id = _infer_session_id(plan)

    # 分层构造 context
    system_prompt = context_builder.build_system(related_episodes, session_id)
    user_message  = context_builder.build_user(plan, session_id)

    # LLM function call：自主选择工具，规划动作序列
    raw_calls = await llm_call(
        system=system_prompt,
        tools=tool_registry.get_schemas(),
        message=user_message
    )

    actions = [
        Action(
            id=str(uuid.uuid4()),
            tool_name=call.name,
            params=call.arguments,
            energy_cost=ENERGY_COST_TABLE.get(call.name, 5.0)
        )
        for call in raw_calls
    ]

    total_cost = sum(a.energy_cost for a in actions)
    queues.current_attention = Attention(
        plan_id=plan.id,
        intent=plan.intent,
        priority=plan.priority,
        total_energy_estimate=total_cost,
        action_count=len(actions),
        created_at=time.time()
    )
    actions_queue.push_all(actions)
```

---

### 5.6 executor.py — Action 阶段

**职责**：逐个弹出 Action，检查精力，调用工具，更新进度。

```python
async def run():
    executed = 0
    while not actions_queue.empty() and executed < MAX_ACTIONS_PER_BEAT:
        action = actions_queue.peek()

        if not bot_state.has_energy(action.energy_cost):
            if current_attention:
                current_attention.state = AttentionState.PAUSED
            break  # 保留队列，等下次心跳精力恢复后续接

        actions_queue.pop()
        try:
            await tool_registry.call(action.tool_name, action.params)
        except Exception as e:
            logger.error(f"Action {action.tool_name} failed: {e}")
            # 当前策略：跳过，继续执行后续 Action
            executed += 1
            continue

        bot_state.consume_energy(action.energy_cost)
        executed += 1

        if current_attention:
            current_attention.current_index += 1
            if current_attention.current_index >= current_attention.action_count:
                _complete_attention()
                break
```

**中断续接**：Attention 标记 `PAUSED` 时 Actions 队列保留不动，下次心跳精力恢复后自然续接，无需额外恢复逻辑。

---

### 5.7 engine.py — 心跳主循环

**职责**：纯编排，不含任何业务逻辑。

```python
HEARTBEAT_INTERVAL = 1.0

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
    bot_state.regenerate_energy()

    if bot_state.heartbeat_count % bot_state.plan_interval == 0:
        await planner.run()

    if actions_queue.empty() and current_attention is None:
        await expander.run()

    if current_attention is not None or not actions_queue.empty():
        await executor.run()

    # 每心跳末尾写一次快照（只此一次，不在 push/pop 时触发）
    await queue_snapshot.save(reason="heartbeat_tick")
```

---

## 6. 服务模块详细设计

### 6.1 DiaryService — 日记服务（新增）

DiaryService 是语义记忆更新的核心通路，与 AlarmService 联动。

**生命周期**：

```
AlarmService 每天特定时间
    │ 注入 alarm_reminder（type="diary_prompt"）
    ▼
planner 生成 Plan（intent="write_diary"）
    ▼
expander 展开 Actions：
    1. recall_memory（回顾今天发生了什么）
    2. write_diary（DiaryService 提供的工具）
    3. update_relationship（如有需要）
    ▼
DiaryService.write() 被调用
    │ 写入结构化日记
    │ 触发 memory_snapshot.refresh()  ← 语义记忆快照更新
    ▼
下一次 expander 调用时，context 中的语义快照已是最新的
```

**工具注册**：

```python
# services/DiaryService/core.py
register(Tool(
    name="write_diary",
    description="将今天的经历、感受、人际互动以结构化形式写入日记，并触发记忆快照更新",
    parameters_schema={
        "type": "object",
        "properties": {
            "date":        {"type": "string"},
            "summary":     {"type": "string", "description": "今天的总结"},
            "interactions": {"type": "array",  "description": "重要的人际互动列表"},
            "reflections": {"type": "string",  "description": "感受与思考"}
        },
        "required": ["date", "summary"]
    },
    handler=_write_diary_and_refresh_snapshot
))
```

### 6.2 AlarmService

```python
# 定时注入 diary_prompt 事件
register(Tool(
    name="set_alarm",
    description="设置一个在指定时间触发的提醒",
    parameters_schema={...},
    handler=_set_alarm
))

# 每天 22:00 自动注入
todo_queue.push(TodoItem(
    id=str(uuid.uuid4()),
    type="alarm_reminder",
    payload={"alarm_type": "diary_prompt", "message": "该写日记了"},
    urgency=Urgency.GENTLE
))
```

### 6.3 QQService

除发消息工具外，还需注册用于社交判断场景的工具：

```python
register(Tool(name="send_qq_message", ...))         # 发消息
register(Tool(name="send_qq_private_message", ...)) # 私信
register(Tool(name="at_user_in_group", ...))        # 在群里 @人
```

事件监听注入 TodoItem：

```python
@msg_handler.handle()
async def handle_qq_msg(event: MessageEvent):
    session_buffer.append(
        session_id=str(event.group_id or event.user_id),
        msg=Message(role="user", content=event.get_plaintext(), timestamp=time.time())
    )
    todo_queue.push(TodoItem(
        id=str(uuid.uuid4()),
        type="qq_msg",
        payload={
            "session_id": str(event.group_id or event.user_id),
            "user_id":    str(event.user_id),
            "text":       event.get_plaintext(),
        },
        urgency=Urgency.NORMAL,
        created_at=time.time()
    ))
```

---

## 7. 关键算法与策略

### 7.1 情节挂起的两层判断

```
第一层（planner，零成本）：参与者集合有交集 → 纳入候选
第二层（expander，LLM）：语义相关性 → 自主决定如何处置
```

LLM 看到候选情节后，可以：

- 认为无关，忽略
- 认为相关，在回复中体现
- 主动关闭情节（调 `close_episode`）
- 主动创建新情节（调 `create_episode`）
- 主动通知相关人（调 `send_qq_private_message`）

**这就是她社交判断的实现**——不是规则，是 LLM 在充分上下文下的自主决策。

### 7.2 Context 前缀缓存策略

```
[层1：极稳定] SOUL.md 人格设定
[层2：稳定]   工具列表 schemas（注册后不变）
[层3：慢变]   语义记忆快照（DiaryService 触发刷新，每天约更新一次）
──── 以上三层构成公共前缀，高概率命中 Prompt Cache ────
[层4：中变]   当前挂起情节候选（每次 plan 可能不同）
[层5：快变]   BotState（精力、负载）
[层6：每次变] Plan 内容 + 工作记忆（user message，尽量短）
```

语义快照不实时 search，而是定期生成稳定字符串，是公共前缀能真正命中缓存的前提。

### 7.3 优先级与自然节律

```
Plan.priority = base_priority + urgency_bonus
```

不使用时间老化机制。旧计划通过**闲时拾取**通路消化：

```
活跃期 → pop_highest()  专注处理高优先级
闲时期 → pop_lowest()   顺带消化低优先级积压
```

闲时判断：`idle_counter >= 10 AND cognitive_load < 0.2`

### 7.4 柔性任务（拟人化忽略）

闹钟类任务 `urgency: GENTLE`，生成的 Plan 优先级较低。LLM 在 expander 展开时可以选择 `evaluate_ignore` 工具，该工具综合当前精力、忙碌程度、延迟时长，以概率决定本次"忽略"并推迟，模拟人在忙时不立刻处理提醒的行为。

### 7.5 队列持久化（v2.1 保留）

- 快照文件：`data/queues/runtime_queues.json`
- 保存时机：**仅在每心跳末尾写一次**（v2.1 改进：不在 push/pop 时触发，避免高频 IO）
- 恢复时校验：`Attention.current_index` 与 `Actions 队列长度` 需保持一致
- 启动恢复失败时降级为干净启动，不阻塞引擎

---

## 8. 完整依赖关系图

```
main.py
  ├──▶ services/QQService      ──register──▶  brain/core/tool_registry
  ├──▶ services/AlarmService   ──register──▶  brain/core/tool_registry
  ├──▶ services/DiaryService   ──register──▶  brain/core/tool_registry
  └──▶ brain/core/engine       ──starts──▶   heartbeat loop

brain/core/engine
  ├──▶ planner.py    ──uses──▶  queues / state / models / episodic
  ├──▶ expander.py   ──uses──▶  queues / state / tool_registry / context_builder / ModelService
  └──▶ executor.py   ──uses──▶  queues / state / tool_registry

brain/core/context_builder
  ├──▶ brain/memory/snapshot   (语义记忆快照)
  ├──▶ brain/core/session      (工作记忆)
  └──▶ brain/prompts/SOUL.md

brain/memory/tools.py
  ──register──▶ brain/core/tool_registry
  ──uses──▶     brain/memory/semantic / episodic

services/DiaryService
  ──triggers──▶ brain/memory/snapshot.refresh()
```

**横向隔离**：planner / expander / executor 互不直接依赖，全部通过 queues 和 state 通信。

---

## 9. 配置参数表

| 参数名                      | 默认值                            | 说明                         |
| --------------------------- | --------------------------------- | ---------------------------- |
| `HEARTBEAT_INTERVAL`        | 1.0s                              | 心跳间隔                     |
| `energy_max`                | 100.0                             | 精力上限                     |
| `energy_regen_per_beat`     | 5.0                               | 每心跳恢复量                 |
| `base_plan_interval`        | 3                                 | 基础计划间隔（心跳数）       |
| `idle_heartbeats_threshold` | 10                                | 判定闲时的连续空闲心跳数     |
| `idle_cognitive_threshold`  | 0.2                               | 判定闲时的认知负载上限       |
| `MAX_ACTIONS_PER_BEAT`      | 10                                | 单心跳最大动作执行数         |
| `session_max_tokens`        | 4000                              | 工作记忆窗口大小             |
| `diary_time`                | "22:00"                           | AlarmService 触发日记的时间  |
| `snapshot_refresh_interval` | 86400s                            | 语义快照兜底刷新间隔（每天） |
| `QUEUES_SNAPSHOT_FILE`      | `data/queues/runtime_queues.json` | 队列持久化文件               |

---

## 10. 里程碑规划

| 里程碑  | 目标              | 关键产出                                         |
| ------- | ----------------- | ------------------------------------------------ |
| M1 ✅   | PAA 核心闭环      | engine → planner → expander（确定性）→ executor  |
| M1.5 ✅ | 队列持久化        | runtime_queues.json，重启可恢复                  |
| M2      | 记忆体系接入      | episodic / semantic / session，memory/tools 注册 |
| M2.5    | DiaryService      | 日记写入 + 快照刷新，语义记忆开始积累            |
| M3      | LLM function call | expander 接入真实模型，工具自主选择              |
| M3.5    | QQ/Alarm 迁移     | Services 完整迁移到 v3 工具注册边界              |
| M4      | 情节挂起闭环      | create/close episode 工具，planner 机械匹配验证  |

---

## 11. 术语表

| 术语            | 定义                                                               |
| --------------- | ------------------------------------------------------------------ |
| PAA 循环        | Plan-Attention-Action，bot 自循环的三个阶段                        |
| ToDo 队列       | Services 注入的原始待办事件缓冲区                                  |
| Plans 队列      | 合并后的意图级计划，按优先级排序                                   |
| Attention       | 当前唯一关注的计划上下文，持有动作进度指针                         |
| Actions 队列    | 当前 Attention 展开的原子动作序列                                  |
| 精力            | 全局行动资源，消耗与恢复驱动执行节奏                               |
| tool_registry   | Services 动态注册能力的注册表，LLM function call 的工具来源        |
| Episode（情节） | 尚未有结果的挂起事件，跨 session 存在，由 LLM 自主判断处置         |
| 工作记忆        | per-session 对话窗口，服务于连贯性                                 |
| 情节记忆        | 她经历过的具体事件，服务于事件追踪                                 |
| 语义记忆        | 她知道的稳定知识与人际关系，由 Mem0 管理                           |
| 语义快照        | 语义记忆的定期摘要字符串，保证 context 前缀稳定以命中 Prompt Cache |
| DiaryService    | 日记服务，语义记忆的更新通路，由 AlarmService 每日触发             |
| 闲时拾取        | 安静期间主动消化低优先级计划的机制                                 |
| 柔性意图        | urgency: gentle，不要求即时响应，可被概率性忽略                    |
| 公共前缀        | context 中字面量稳定的部分，Prompt Caching 命中的基础              |

---

_v3.0 是整个设计体系的第一个完整版本。它以"数字生命"为哲学基础，以 PAA 循环为执行骨架，以三层记忆体系为认知基础，以动态工具注册为扩展机制，形成一个自洽的、可持续演化的架构。_
