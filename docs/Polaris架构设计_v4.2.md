# Polaris Bot 自循环体系（PAA 循环）架构设计文档 v4.2

## 版本记录

| 版本 | 日期       | 变更说明                                                                                                                                                |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1  | 2026-05-07 | Protocol 鸭子类型；activity_rate / activity_variability；状态感受翻译层                                                                                 |
| 4.2  | 2026-05-08 | 结合当前实现现状重写核心数据契约与运行语义；纳入持久 todo、单一 attention、planning_hint、JSON 动作规划、LLM/Capability 可观测性、QQ 聚合窗口与快照剪枝 |

---

## 0. 文档定位

这份 `v4.2` 不是对 `v4.1` 的字面增补，而是一次“取优整合”：

- 保留 `v4.1` 中仍然正确的设计哲学
- 吸收本轮真实开发中已经落地的架构重构
- 明确记录当前实现与 `v4.1` 的偏差
- 把已经暴露出来的工程问题直接写进设计，而不是留在聊天记录里

它的定位是：

- **对内**：作为当前代码状态的较准确抽象
- **对外**：作为和 Claude 讨论 `v5` 的过渡底稿
- **对未来**：给后续重构提供明确的“哪些已经稳定、哪些只是过渡实现、哪些必须在 v5 解决”

---

## 1. 差距总评：当前项目与 v4.1 有多大差距？

结论先说：

- **设计哲学层面**：大体一致，约 `75%` 保持同向
- **核心运行语义层面**：已经有明显偏移，约 `45%~55%` 属于“同主题下的重写”
- **实现完成度层面**：`planner / queues / models / platform / manifests / observability` 已明显前进；`expander / QQ 回复质量 / 执行补偿 / MCPContainer` 仍在过渡期

如果用一句话概括：

> 当前代码不再是“v4.1 文档的直接实现”，而是“以 v4.1 哲学为底、围绕持久 todo + 单一 attention + planning hint + JSON 动作规划重构后的 v4.1.5 过渡架构”。

### 1.1 基本一致的部分

- **数字生命哲学**仍成立：不是被动消息机器人，而是有节律、有判断、有记忆的主体
- **Brain / Application 解耦**仍成立：能力经 Manifest 注册，Brain 不直接依赖某个具体应用
- **三层记忆体系**仍成立：工作记忆 / 情节记忆 / 语义记忆分工明确
- **心跳驱动循环**仍成立：`planner -> expander -> executor -> snapshot`
- **ApplicationProtocol + ApplicationHost** 的方向仍然正确

### 1.2 已经发生方向性变化的部分

#### 1.2.1 Todo 不再 drain，Plan 不再是一次性产物

`v4.1` 里的 `planner` 还是“每心跳把 todo drain 掉，组装出 plan”。  
当前实现已经变成了：

- `TodoQueue` 是**带状态的持久 item store**
- `TodoItem` 有 `PENDING / CLAIMED / DONE / DROPPED`
- `planner` 不清空 todo，只处理 `PENDING`
- `plan` 会持续吸收同 `intent + session_id` 的新 todo

这不是小修小补，而是认知循环语义已经改变。

#### 1.2.2 Expander 不再走“闲时 pop_lowest / 忙时 pop_highest”

用户已经明确否定“饿死保护”与“self_maintenance 的主动插入”，当前实现也已经跟进：

- **永远只取最高优先级 `PENDING` plan**
- **同一时刻只有一个 `current_attention`**
- **attention 存在时不再并发展开其他计划**

这意味着 `v4.1` 文档中“闲时消化低优先级积压”的那一套，已经不再代表当前实现。

#### 1.2.3 LLM 规划接口从“原生 function call 交互式循环”退回到了“纯 JSON 动作列表”

`v4.1` 假设的是原生 tool calling。  
而当前 DeepSeek 实战暴露出一个关键问题：

- 模型天然倾向先出 `memory.recall`
- 但我们现在没有完整的 tool loop 把 recall 结果再喂回去继续规划
- 因此当前实现改成了：**一次性要求模型直接返回 JSON 动作列表**

这是一项重要的工程现实，必须写进 `v4.2`，否则文档会误导后续设计。

#### 1.2.4 Prompt 结构已经从“SOUL 主导”变为“PLAN + SOUL + planning_hint 协作”

当前 `context_builder` 的稳定结构是：

1. `PLAN.md`
2. `SOUL.md`
3. capability schemas
4. application planning hints
5. semantic snapshot
6. episode candidates
7. current feeling

也就是说：

- `SOUL.md` 负责人格与表达倾向
- `PLAN.md` 负责动作协议
- `planning_hint` 负责应用级完成标准

这比 `v4.1` 的 `persona_hint` 时代清晰得多。

### 1.3 当前最明显的短板

- **QQ 回复质量不稳定**：已能产出发送动作，但还会出现怪异、过短、重复、参数错名等问题
- **缺少回复质量门控**：现在只校验“是否是合法动作”，不校验“是否值得真的发出去”
- **Executor 仍偏薄**：有状态回写和错误反馈，但还缺真正的补偿机制
- **Deterministic fallback 仍存在**：尤其 QQ 仍保留过渡期兜底逻辑
- **MCPContainer 仍只是骨架**
- **记忆能力与工具描述仍偏英文 / 通用工程风格**，和中文人格语境还没有完全对齐

---

## 2. v4.2 设计目标

`v4.2` 的目标不是“再往现有代码上补 patch”，而是把当前已经形成的更合理结构正式命名：

1. **把 todo/plan/action/attention 的真实契约写清楚**
2. **把 planner / expander / executor 的新边界写清楚**
3. **把 prompt、planning_hint、Manifest 的职责分工写清楚**
4. **把 LLM observability 纳入正式架构**
5. **把 QQ 对话的聚合语义与多条发送动作写进体系**
6. **把当前已知过渡点明确标注，避免它们在 v5 讨论中被误当成“设计本意”**

---

## 3. 设计哲学

### 3.1 她是数字生命，不是消息处理器

这条没有变。

Polaris 不以“收到消息立即回复”为目的，而以“在自己的节律下处理当前值得处理的事项”为目的。QQ、提醒、日记、外域工具，都只是她接触世界的不同通道。

### 3.2 当前阶段的四个核心原则

| 原则                                | 含义                                                        |
| ----------------------------------- | ----------------------------------------------------------- |
| Todo 持久化                         | 原始意图不被 planner 清空，而是带状态流转                   |
| 单一 Attention                      | 任一时刻只有一个当前计划在被展开/执行                       |
| 完成导向展开                        | `expander` 不能只给准备动作，必须产出满足计划完成条件的动作 |
| 应用通过 planning_hint 定义完成标准 | 完成语义属于应用编排层，不属于 runtime 发送层               |

### 3.3 过渡期原则

当前仍允许存在过渡实现，但必须显式标注其性质：

- deterministic fallback 是**兜底**，不是理想路径
- QQ runtime 的 `|` 拆分是**兼容历史**，不是主设计
- JSON 动作列表规划是**当前模型现实下的工程折中**，不是最终理想交互协议

---

## 4. 系统架构总览

### 4.1 宏观分层

```text
src/
├── brain/
│   ├── core/       # 调度与状态核心：planner / expander / executor / queues / models
│   ├── memory/     # 工作记忆、情节记忆、语义记忆、快照、记忆能力
│   ├── model/      # LLM 调用封装、JSON 动作规划入口、日志与截断
│   ├── platform/   # ApplicationHost / PlatformAPI / Manifest
│   └── prompts/    # PLAN.md / SOUL.md
└── applications/   # qq / diary / alarm / mcp_container
```

### 4.2 实际数据流

```text
Application runtime
    └── post_intention(TodoItem)
            ▼
        TodoQueue(item store, with status)
            ▼
        planner.run()
            ▼
        PlansQueue(sorted store)
            ▼
        expander.run()
            ▼
        current_attention + ActionsQueue
            ▼
        executor.run()
            ▼
        capability_registry.call()
            ▼
        Application tools / memory tools
```

### 4.3 心跳循环

```python
async def tick():
    bot_state.heartbeat_count += 1
    await app_host.tick()
    await planner.run()
    if queues.actions_queue.empty() and queues.current_attention is None:
        await expander.run()
    if queues.current_attention is not None or not queues.actions_queue.empty():
        await executor.run()
    queues.persist_runtime_snapshot("heartbeat_tick")
```

### 4.4 相比 v4.1 的实质变化

- 不再插入 `self_maintenance`
- 不再 idle 时消费最低优先级
- 不再从 `PlansQueue` 中直接 pop 出 plan 再消失
- 运行时快照现在是“**可恢复的活跃运行态**”，而不是“无上限堆积的历史残留”

---

## 5. 核心数据模型（v4.2 契约）

### 5.1 枚举

```python
class TodoStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    DROPPED = "dropped"

class PlanStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"

class AttentionState(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"

class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
```

### 5.2 TodoItem

```python
@dataclass(slots=True)
class TodoItem:
    id: str
    type: str
    payload: dict[str, Any]
    urgency: Urgency = Urgency.NORMAL
    status: TodoStatus = TodoStatus.PENDING
    claimed_by_plan_id: str | None = None
    created_at: float = 0.0
    last_seen_at: float = 0.0
```

`TodoItem` 现在表达的是“一个仍可追踪的原始意图项”，不是一次性消息缓冲。

### 5.3 Plan

```python
@dataclass(slots=True)
class Plan:
    id: str
    intent: str
    summary: str
    session_id: str
    priority: float
    base_priority: float
    status: PlanStatus = PlanStatus.PENDING
    source_todo_ids: list[str] = field(default_factory=list)
    related_episodes: list[str] = field(default_factory=list)
    attention_count: int = 0
    expand_fail_count: int = 0
    last_expanded_at: float = 0.0
    last_error: str = ""
    created_at: float = 0.0
    last_touched_at: float = 0.0
```

`Plan` 现在不再内嵌 `sub_items`，而是引用 `source_todo_ids`。这是当前实现与 `v4.1` 最大的契约差异之一。

### 5.4 Attention

```python
@dataclass(slots=True)
class Attention:
    id: str
    plan_id: str
    intent: str
    priority: float
    action_ids: list[str] = field(default_factory=list)
    source_todo_ids: list[str] = field(default_factory=list)
    current_index: int = 0
    state: AttentionState = AttentionState.ACTIVE
    started_at: float = 0.0
    last_advanced_at: float = 0.0
```

Attention 现在是一个真正可恢复的执行指针，而不是简单的“动作总数 + 当前索引”。

### 5.5 Action

```python
@dataclass(slots=True)
class Action:
    id: str
    plan_id: str
    capability_name: str
    params: dict[str, Any]
    order: int = 0
    status: ActionStatus = ActionStatus.PENDING
    result_summary: str = ""
    error_message: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
```

`Action` 已经从“只有 name + params 的壳子”进化成带执行生命周期的运行对象。

---

## 6. Queue 层设计

### 6.1 TodoQueue：带状态的 item store

关键语义：

- `push()`：追加原始意图
- `iter_pending()`：只取待处理意图
- `claim(todo_ids, plan_id)`：归属给某个 plan
- `mark_done()` / `mark_dropped()`：终态回写

### 6.2 PlansQueue：可更新的优先级存储

关键语义：

- `push(plan)`：更新或插入
- `highest_priority()`：取最高优先级且 `PENDING` 的 plan
- `find_merge_target(intent, session_id)`：按 `intent + session_id` 合并

### 6.3 ActionsQueue：带状态与恢复能力的动作存储

关键语义：

- `push_all(actions)`：写入动作序列
- `peek() / pop()`：按 pending 顺序执行
- `update(action)`：回写动作状态
- `remove_pending_ids(action_ids)`：attention 完结后清理 pending 指针

### 6.4 快照语义

`runtime_queues.json` 在 `v4.2` 中被重新定义为：

> **仅用于恢复当前活跃运行态，不用于保存完整历史。**

因此，持久化前会剪枝：

- `COMPLETED / FAILED` 的 plan
- 已结束且不再被当前 attention 引用的 action
- `DONE / DROPPED` 且不再受保护的 todo

这项修正已经进入实现。

---

## 7. Planner 设计（v4.2）

### 7.1 职责定义

`planner` 的职责是：

1. 读取 `PENDING` todo
2. 进行轻量分组与优先级整理
3. 将其合并进已有 plan，或创建新 plan
4. 回写 todo 的归属状态

它**不负责**：

- 产出具体动作
- 清空 todo
- 决定表达文本

### 7.2 当前策略

- 按 `(item.type, session_id)` 分组
- 转换 `type -> intent`
- 以 `base_priority + urgency_bonus` 计算优先级
- 通过参与者集合匹配挂起 `Episode`
- 合并目标为 `intent + session_id` 相同的 `PENDING/ACTIVE/BLOCKED` plan

### 7.3 QQ 聚合窗口

这是 `v4.2` 新写入设计的关键内容。

QQ 不应该“来一条回一条”。当前已经加入：

- `QQ_REPLY_DEBOUNCE_SECONDS`
- 同一 `session` 在短时间内的连续消息，会先缓一小段时间再形成计划
- 若当前 session 已有 `ACTIVE` plan，新消息暂缓，不与当前动作链粗暴并发

这使 planner 在 QQ 场景中第一次具备了“把多条消息看成同一轮对话材料”的能力。

### 7.4 当前缺口

- 还没有“这一轮对话应该回复哪些消息、不回复哪些消息”的显式对话层模型
- 目前仍然只是通过时间窗口和 plan 合并做近似

---

## 8. Expander 设计（v4.2）

### 8.1 职责定义

`expander` 的职责是：

1. 选出当前唯一要处理的 plan
2. 构建该 plan 的上下文
3. 调用模型把 plan 展开为 action 列表
4. 只有 action 序列满足“计划完成条件”时，才进入执行

### 8.2 选取规则

- 如果 `current_attention` 存在，或 `ActionsQueue` 非空，直接返回，不展开新计划
- 否则取 `PlansQueue.highest_priority()` 的最高优先级 `PENDING` plan

### 8.3 展开策略

当前策略是：

- 先尝试 LLM 展开
- 若失败或返回动作不满足完成条件，则走 deterministic fallback

### 8.4 “完成条件”是 v4.2 的核心概念

当前已有显式完成校验：

- `handle_qq_messages`：动作序列中必须含有 QQ 发送能力
- `write_diary`：动作序列中必须含有 `write_diary`
- 其他计划：只要有动作即可

这是对 `v4.1` 的重要提升，因为它开始显式地区分“准备动作”和“完成动作”。

### 8.5 当前 LLM 规划协议

当前不是完整 tool loop，而是：

- 上下文中提供工具 schema 与 planning hint
- 明确要求模型**一次性返回纯 JSON 动作列表**
- 不等待工具执行结果后继续第二轮规划

这是出于当前模型现实做出的工程折中：

- 避免模型只回 `memory.recall`
- 避免实现不完整的交互式工具循环

### 8.6 参数归一化

`expander` 现在还负责一层很务实的归一化：

- QQ 发送动作若把 `message` 写成 `text` 的别名，会自动修正
- 能从 plan 来源 todo 中补的 `session_id / user_id / group_id` 尽量自动补齐

这是 `v4.2` 必须承认的现实：

> 模型不只会“想错”，还会“拼错参数名”，因此 expander 需要承担轻量语义对齐职责。

### 8.7 当前缺口

- deterministic fallback 仍然存在，尤其 QQ fallback 还是过渡状态
- 还没有真正的“两阶段展开”
- 还没有回复质量门控，导致“合法但不自然”的动作也会被执行

---

## 9. Executor 设计（v4.2）

### 9.1 职责定义

`executor` 的职责保持简单，但不再是“纯 fire-and-forget”：

1. 校验 action 合法性
2. 执行 capability
3. 回写 action 状态、结果摘要、错误信息
4. 推进 attention 与 plan 状态

### 9.2 当前状态机

- 执行前：`PENDING -> RUNNING`
- 成功后：`RUNNING -> SUCCEEDED`
- 失败后：`RUNNING -> FAILED`

Attention 与 Plan 同步推进：

- 动作失败：`Attention -> FAILED`，`Plan -> BLOCKED`
- 动作全部完成：`Attention -> COMPLETED`，`Plan -> COMPLETED`

### 9.3 可观测性

当前已正式具备：

- `LLM_LOG_QUERY`
- `LLM_LOG_RESPONSE`
- `CAPABILITY_LOG_EXECUTION`
- `LLM_LOG_MAX_CHARS`

这意味着：

- 什么时候调用模型
- 模型具体回了什么
- 什么时候真正触发本地能力

这些都已经进入体系，而不再只是临时调试手段。

### 9.4 当前缺口

- 没有补偿链
- 没有质量门控后的二次拒发
- 没有“执行失败后自动再规划”的正式机制

---

## 10. Prompt / Context 体系

### 10.1 分层职责

#### `PLAN.md`

负责：

- 动作协议
- 输出格式
- “只产出动作，不直接聊天”
- 完成导向与多条消息 action 约束

#### `SOUL.md`

负责：

- 人格
- 说话风格
- 社交边界
- QQ 平台上的表达习惯

#### `planning_hint`

负责：

- 各应用“什么才算真正完成”
- 特定应用的编排偏好
- 不应写进通用 prompt 的业务规则

### 10.2 当前 `build_system()` 结构

```text
PLAN.md
SOUL.md
Available capabilities
Application planning hints
Semantic snapshot
Pending episodes
Current feeling
```

### 10.3 当前 `build_user()` 结构

```text
Current intent
Summary
Priority
Items (source todo payloads)
Related episode ids
Recent conversation
```

### 10.4 现状评价

这套结构比 `v4.1` 更接近正确方向，因为它把：

- 人格
- 行动协议
- 应用完成条件

这三层终于拆开了。

当前不足在于：

- 语言混用仍然明显，系统上下文中仍有不少英文标题
- capability 描述与中文人格语境尚未完全统一

---

## 11. Application / Platform 设计

### 11.1 Manifest 语义

当前 `Manifest` 正式字段是：

```python
package
name
version
brain_version
persona_hint
planning_hint
capabilities
tools
type
```

其中 `planning_hint` 是 `v4.2` 的关键补充，已经比 `v4.1` 仅有 `persona_hint` 更精确。

### 11.2 ApplicationHost

当前 `ApplicationHost` 负责：

- 加载 manifest
- 按 `package.tool_name` 注册 capability
- 将 `planning_hint` 注入 `context_builder`
- 注入 `PlatformAPI`
- 管理应用生命周期

### 11.3 PlatformAPI

当前 `PlatformAPI` 提供：

- `post_intention()`
- `register_capability()`
- `get_persona()`
- `log()`
- `data_dir`

### 11.4 能力注册表

当前 capability registry 已经适配 DeepSeek 的工具名限制：

- 内部 canonical name 可以保留 `im.polaris.qq.send_qq_message`
- 对模型暴露 alias，如 `im_polaris_qq_send_qq_message`
- 模型返回后再 resolve 回 canonical name

这项兼容层应当被视为正式架构，而不是临时修补。

---

## 12. 记忆体系

### 12.1 工作记忆

- `session_buffer`
- 以 `session_id` 为键维护最近对话
- 主要为 QQ 连贯性服务

### 12.2 情节记忆

- `Episode` 仍然是“挂起中的经历”
- planner 只做机械候选匹配
- expander 决定是否处理、创建或关闭

### 12.3 语义记忆

当前能力层已具备：

- `memory.recall`
- `memory.store`
- `memory.update_relationship`
- `episode.create`
- `episode.close`

### 12.4 语义快照

当前实现与 `v4.1` 也有一点差异：

- `v4.1` 设想通过搜索某个概括 query 刷新
- 当前实现是 `get_all(__global__)` 后裁成前 20 条，生成稳定文本快照

它更工程化，但对“摘要质量”控制还不够强，这会是 `v5` 可重点讨论的点。

---

## 13. QQ 应用专项说明

### 13.1 当前已经形成的共识

- **回复内容生成属于 brain，不属于 QQ runtime**
- **多条消息 = 多个发送 action**
- `QQ runtime` 只负责发送、记录、补工作记忆

### 13.2 当前实际行为

QQ runtime 仍保留：

- `|` 分段拆分兼容逻辑

但这在 `v4.2` 中应被明确标注为：

> 仅用于兼容旧输出，不代表主设计。

### 13.3 当前仍未彻底解决的问题

- 回复质量不稳定
- 连发消息的合并仍是时间窗口近似，不是完整对话轮次模型
- 还缺发送前质量校验

---

## 14. 当前实现状态盘点（供 v5 讨论）

### 14.1 已相对稳定

- `models.py`
- `queues.py`
- `planner.py` 的持久 todo 与 plan 合并语义
- `ApplicationHost / Manifest / PlatformAPI`
- `capability_registry` alias 兼容层
- LLM / capability 日志观测
- 快照恢复与终态剪枝

### 14.2 正在过渡

- `expander.py`
- QQ 回复质量
- QQ 聚合语义
- prompt 中中英混合与能力描述风格

### 14.3 尚未成熟

- 执行补偿机制
- 发送质量门控
- 两阶段展开
- MCPContainer 真正接入

---

## 15. 相比 v4.1 的正式修订清单

### 15.1 保留

- 数字生命哲学
- 心跳驱动循环
- ApplicationProtocol 与动态能力注册
- 三层记忆体系
- Episode 作为挂起经历

### 15.2 修订

- `TodoQueue`：从 drain 队列改为带状态 item store
- `Plan`：从内嵌 `sub_items` 改为引用 `source_todo_ids`
- `Attention`：从 `action_count` 改为显式 `action_ids`
- `Action`：补足 `plan_id / order / status / result / error / timestamps`
- `planner`：不再清空 todo，改为 claim + merge
- `expander`：固定只取最高优先级，不再维护 self_maintenance
- `context_builder`：从 `persona_hint` 主导变为 `PLAN + SOUL + planning_hint` 协作
- `Manifest`：`planning_hint` 成为正式字段
- `ModelService`：当前规划模式为一次性 JSON 动作列表
- `queues snapshot`：改为只持久化可恢复的活跃运行态

### 15.3 明确删除

- self_maintenance 主动插入路径
- idle 时消费低优先级计划的正式语义
- 将 QQ runtime 视为“负责组织回复文本”的设计

---

## 16. 面向 v5 的建议议题

如果要和 Claude 讨论 `v5`，我建议围绕下面几项展开，而不是重新从零讲哲学：

### 16.1 对话轮次模型

当前只有“时间窗口聚合”，还没有真正的“这一轮对话由哪些消息构成”的显式层。

### 16.2 两阶段规划

建议明确拆成：

1. **理解/取材阶段**
2. **表达/发送阶段**

这样可以兼容模型先 recall 再表达的天然习惯。

### 16.3 回复质量门控

在 executor 前增加一层轻量校验，拦截：

- 过短
- 重复
- 自指令式文本
- 参数虽合法但明显不自然的回复

### 16.4 更清晰的完成语义系统

当前 `_actions_satisfy_plan()` 还是手工规则，v5 可以考虑把“完成条件”上升为 Manifest 或 Intent 策略的一等配置。

### 16.5 Memory / Snapshot 更强摘要层

现在 snapshot 还是“前 20 条拼接”，v5 可以讨论更稳定的语义摘要生成机制。

---

## 17. v4.2 结论

`v4.2` 对当前项目状态的判断是：

- 项目已经脱离 `v4.1` 文档的若干旧实现细节
- 但其核心哲学没有偏航，反而在若干地方更清晰了
- 当前最值得保留的成果是：
  - 持久 todo + 单一 attention
  - planning_hint 机制
  - JSON 动作规划
  - LLM / capability observability
  - QQ 多 action 发送方向
- 当前最应该在 `v5` 解决的问题是：
  - 回复质量稳定性
  - 对话轮次建模
  - 两阶段展开
  - 执行补偿与质量门控

因此，`v5` 最适合被定义为：

> **在 v4.2 的运行语义基础上，补齐“对话轮次层、两阶段规划层、动作质量门控层”的正式架构版本。**

---

_v4.2 的意义，不是“再给现有代码套一层新名字”，而是把这轮真实开发中已经证明有效的结构正式写下来，同时诚实承认过渡区与缺口。这样下一轮设计讨论才不会建立在过期文档之上。_
