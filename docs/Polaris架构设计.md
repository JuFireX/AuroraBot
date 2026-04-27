# Bot 自循环体系（PAA 循环）开发文档

## 版本记录

| 版本 | 日期       | 作者     | 变更说明                                        |
| ---- | ---------- | -------- | ----------------------------------------------- |
| 1.0  | 2026-04-27 | 设计团队 | 初始详尽版，基于 Plan-Attention-Action 循环架构 |

---

## 1. 引言

本文档定义了一个名为 **PAA（Plan-Attention-Action）** 的 Bot 自循环体系。该体系模拟人类处理任务的方式：**收集待办 → 合并为计划 → 专注于一项计划 → 将其分解为原子动作逐个执行**，并引入 **精力值** 作为全局限制资源，使 Bot 呈现出自主节奏与“人味”。

### 1.1 核心设计理念

- **自上而下的分层调度**：ToDo（事件）→ Plans（意图）→ Attention（焦点）→ Actions（原子执行）
- **精力作为硬通货**：所有行动消耗精力，精力不足时暂停，恢复后继续。
- **自然节律驱动**：无老化机制，任务不会被强制过期。Bot 在群聊活跃时快速响应，在安静时自发消化积压的低优先级计划，形成类似人类的作息感。
- **拟人化自动任务**：闹钟、定时提醒等自动任务以“柔性意图”存在，Bot 可以因忙碌而暂时忽略，不会被强迫立即执行。
- **原子动作保证**：每一步均可中断、可恢复，系统可随时安全暂停。

---

## 2. 系统架构总览

系统由以下部分组成：

- **总 State**：保存 Bot 自身状态（精力、认知负载、调速参数等）。
- **外围 Services**：外部事件源（QQ消息服务、闹钟服务、系统提醒等），它们将待办事项注入 ToDo 队列。
- **四个核心队列**：
  - **ToDo 队列**：原始待办事项缓冲区。
  - **Plans 队列**：由 ToDo 合并生成的抽象计划列表。
  - **Attention 上下文**：当前 Bot 正在关注的唯一计划（或为 nil）。
  - **Actions 队列**：当前关注计划展开后产生的原子动作序列。
- **心跳循环引擎**：每个心跳内顺序执行 **Plan 阶段 → Attention 阶段 → 多个 Action 阶段**。

架构示意图（文字描述）：

```
Services ──push──> ToDo 队列
                     │
                     v (Plan 阶段读取并清空)
                 Plans 队列
                     │
                     v (Attention 阶段选出优先级最高)
              Attention 上下文 (计划 + 动作列表指针)
                     │
                     v (展开)
                 Actions 队列 (原子动作序列)
                     │
                     v (Action 阶段逐个弹出执行，消耗精力)
              [完成/暂停/中断]
```

**关键原则**：

- Plans 队列可同时存在多条计划；Attention 上下文同时最多只关注一条计划。
- Actions 队列由当前 Attention 独占，一旦 Attention 完成或暂停，剩余动作可保留或丢弃（视策略而定，推荐保留以续接）。
- 心跳循环永远优先处理 Actions 队列（即执行阶段），在没有剩余动作时才考虑发起新 Attention。

---

## 3. 核心组件详细设计

### 3.1 State（状态对象）

State 是一个持久化或常驻内存的结构，包含：

| 字段名                  | 类型           | 说明                                                         |
| ----------------------- | -------------- | ------------------------------------------------------------ |
| `energy_current`        | float          | 当前精力值                                                   |
| `energy_max`            | float          | 精力上限                                                     |
| `energy_regen_per_beat` | float          | 每次心跳自然恢复量                                           |
| `cognitive_load`        | float (0~1)    | 认知负载，影响 Plan 频率、注意力切换倾向等                   |
| `plan_interval`         | int (心跳次数) | 动态的 Plan 阶段间隔，当前需要隔多少心跳执行一次 Plan        |
| `base_plan_interval`    | int            | 基础计划间隔，根据负载自动调整时的基数                       |
| `busy_threshold`        | float          | 判定“忙碌”的活跃度阈值（如最近 10 秒内 ToDo 非空的心跳比例） |
| `idle_trigger_count`    | int            | 连续空闲心跳数阈值，触发闲时拾取                             |

State 初始值示例：

- energy_current = 100
- energy_max = 100
- energy_regen_per_beat = 2
- cognitive_load = 0.5
- plan_interval = 3
- idle_trigger_count = 5

### 3.2 队列定义

#### 3.2.1 ToDo 队列

一个 FIFO 或优先级队列，存放外部 Service 注入的原始待办事项。

**条目结构 `TodoItem`**：

```json
{
  "id": "uuid",
  "type": "read_qq_msg | alarm_reminder | system_task | ...",
  "payload": { /* 类型相关数据 */ },
  "created_at": "timestamp",
  "urgency": "gentle | normal | urgent",    // 自动任务多为 gentle
  "suggested_time_window": { "start": ts, "end": ts } // 可选，用于柔性提醒
}
```

- `type` 用于 Plan 阶段的合并分组。
- `urgency` 影响合并后计划的初始优先级。

#### 3.2.2 Plans 队列

保存由 ToDo 合并生成的**意图级计划**。是一个按优先级排序的列表（可用堆或有序集合）。

**计划条目 `Plan`**：

```json
{
  "id": "uuid",
  "intent": "handle_qq_messages | trigger_alarm | self_maintenance | ...",
  "sub_items": [ /* 原始 TodoItem 引用或摘要列表 */ ],
  "priority": float,        // 动态优先级，越大越优先
  "base_priority": float,   // 首次生成时的基础值
  "weight": float,          // 自适应权重，可通过执行结果调整
  "created_at": "timestamp",
  "last_touched_at": "timestamp"
}
```

- `priority` 可随时间与环境变化（如被 Action 阶段动态调整），但本设计不使用强制老化，调整频率极低。
- `intent` 决定 Attention 阶段如何展开为动作列表。

**合并规则（Plan 阶段）**：

- 将 ToDo 中 `type` 相同的条目归为一组，必要时进一步依据 `payload` 中的会话/对象区分（例如按会话 ID 合并消息，但保留原始消息列表）。
- 每个分组生成一个 Plan，`sub_items` 保存分组内所有 TodoItem。
- 若分组内包含 `urgency: urgent`，则 `base_priority` 大幅提升。

#### 3.2.3 Attention 上下文

一个全局单例对象（或为 nil），代表 Bot 当前正在执行的计划。结构 `Attention`：

```json
{
  "plan_id": "uuid",
  "intent": "handle_qq_messages",
  "priority": float,
  "total_energy_estimate": float,   // 展开时预估总消耗
  "action_list": [ /* Action 的指针或拷贝 */ ],
  "current_index": int,            // 指向下一个要执行的动作索引
  "state": "active | paused | completed",
  "created_at": "timestamp"
}
```

注意：为了不让 Attention 和 Actions 队列耦合过深，建议 **Actions 队列里存放的就是 Attention 展开出的原子动作**，而 Attention 对象仅保留元数据和进度指针。当 Attention 被暂停时，Actions 队列中未执行的动作**保留不动**，下次恢复时直接从中断点继续。

#### 3.2.4 Actions 队列

一个 FIFO 队列，存放当前 Attention 展开出的原子动作序列。**每个心跳的 Action 阶段循环弹出队首的动作并执行**，直到精力不足或队列为空。

**原子动作 `Action`**：

```json
{
  "id": "uuid",
  "type": "recall_memory | generate_response | send_msg | update_memory | check_ignore_alarm | ...",
  "params": { /* 具体参数，如消息内容、会话ID */ },
  "energy_cost": float,         // 预估消耗，可被实际消耗覆盖
  "preconditions": [ /* 可选的执行前检查条件 */ ]
}
```

- 每个 Action 执行应为原子且幂等或可补偿。
- `energy_cost` 在 Attention 展开时赋值。

### 3.3 Service 接口

外围 Service 必须实现统一的注入接口：

```
Service → push_todo(item: TodoItem)
```

例如：

- QQService 收到新消息时，为每条消息（或按需聚合）生成 `read_qq_msg` 类型的 TodoItem，push 到 ToDo。
- AlarmService 到预定时间时，生成 `alarm_reminder` 类型的 TodoItem（urgency: gentle），注入 ToDo。

不允许 Service 直接操作 Plans 或 Actions 队列。

### 3.4 阶段描述

#### 3.4.1 Plan 阶段（计划心跳）

**触发条件**：由心跳循环根据 `state.plan_interval` 决定是否在本轮执行。例如 `plan_interval = 3`，则每 3 个心跳执行一次 Plan；也可动态调整（如忙时增大间隔、闲时减小）。

**执行步骤**：

1. 锁定 ToDo 队列，取出全部 TodoItem，并清空 ToDo。
2. 按 `type`（及可选的分组键）合并，形成若干组。
3. 对每组，如果 Plans 队列中已存在**相同 intent 且未附着 Attention 的 plan**，则考虑将新 item 合并进该 plan 的 `sub_items`，并刷新其优先级（取更高者），避免重复建计划。
4. 对于新建的计划，生成 `Plan` 对象，计算初始优先级 = base_priority + urgency_bonus + 时间衰减（极小或不使用）。由于无老化，只靠 urgency 和基值区分。
5. 将所有新/更新 Plan 按优先级插入 Plans 有序队列（大顶堆）。
6. 更新 State 的 `cognitive_load` 等指标（如根据 ToDo 积压率）。
7. 解锁。

**动态 plan_interval 调整建议**：

- 当 ToDo 积压数量 > 阈值（如5）时，临时将 `plan_interval` 设为 1（每个心跳都 Plan）。
- 当连续 N 个心跳 ToDo 为空（安静期），增大 `plan_interval` 至基础值甚至更大，降低内耗。
- 当 Attention 正忙且 Plans 不空，可适当增大间隔，避免频繁抢注意力。

#### 3.4.2 Attention 阶段（聚焦阶段）

**触发条件**：仅当 **Actions 队列为空** 且 **当前无活跃 Attention（或 Attention.state = completed）** 时执行。即：只有手上没事干了，才会去寻找下一个关注点。

**流程**：

1. 如果 Plans 队列为空，结束该阶段，下个心跳继续。
2. **“闲时拾取”特殊逻辑**：当 ToDo 为空（即时无新刺激）且 State 判定当前为安静期（如 `cognitive_load < 0.2` 且连续空闲心跳数超过阈值），可以从 Plans 队列中**选择优先级最低的计划**（即积压最久的事务）作为新 Attention，而非最高优先级。这模拟了“无聊时翻旧账”的行为。否则正常选取优先级最高的计划。
3. 从 Plans 队列中弹出选定的计划（或标记为已关注，防止再被选中），创建新的 `Attention` 对象，填入 plan_id、intent、priority。
4. 根据 `intent` 展开原子动作列表：
   - 例如 `handle_qq_messages`：遍历 sub_items 中的消息，生成 `[recall_memory, generate_response, send_msg, update_memory]` 等动作。也可能对多条消息批处理优化（如一次 recall 所有相关记忆）。
   - 例如 `alarm_reminder`（柔性）：生成 `[check_if_should_ignore, (若不应忽略则) alert_user, update_alarm_status]` 等。
   - 例如 `self_maintenance`：生成整理记忆、总结等动作。
5. 计算动作列表每个 Action 的预估 `energy_cost`，求和得到 `total_energy_estimate`，存入 Attention。
6. 将动作列表 **按顺序 push 到 Actions 队列**，并设置 `Attention.current_index = 0`，`state = active`。
7. 若在展开过程中发现精力预估已超过当前 `energy_current` 的某个比例（比如 50%），可以暂不填充全部动作，而只填充前半部分，预留后续调整空间（可选优化）。

**注意**：Attention 阶段本身**不消耗精力**，只预估。

#### 3.4.3 Action 阶段（执行阶段）

每个心跳中，在 Plan 和 Attention 阶段后，进入 Action 循环执行，直到达到执行上限或精力不足。

**单次 Action 执行步骤**：

1. 若 Actions 队列为空，或 Attention 为 nil，直接跳出阶段。
2. 查看队列头部 Action（不弹出），获取其 `energy_cost`。
3. **精力检查**：如果 `state.energy_current < action.energy_cost`，则 **暂停当前 Attention**：
   - 保留 Actions 队列不动，记录 Attention 状态为 `paused`，保留 `current_index`。
   - 本轮 Action 阶段结束，等待下个心跳精力恢复后从该动作继续。
4. 若精力充足，弹出该 Action。
5. 执行前可选检查 `preconditions`，若不满足可采取跳过、重试或失败策略。
6. 执行原子操作（调用对应的内部处理器或外部 API）。
7. 实际消耗精力（可从 action 对象中扣除，或按照实际结果微调），更新 `energy_current`。
8. 更新 Attention 的 `current_index++`。
9. **动作后评估**：
   - 根据执行结果，可微调原 Plan 的 `weight` 或优先级（如任务顺利可略微降低权重，失败可提升以重试），但调整幅度温和。
   - 判断该 Action 是否为当前 Attention 动作链的最后一个，若是，标记 Attention 状态为 `completed`，从 Plans 队列中移除对应 Plan（或标记已完成），并清除 Attention 对象（设为 nil）。
10. 继续循环执行下一个 Action，直到精力不够或达到单心跳最大执行动作数（防止单帧卡死）。

**精力恢复时机**：可在每个心跳最开始时统一增加 `energy_regen_per_beat`，确保执行阶段消费的是恢复后的值。

---

## 4. 关键算法与策略

### 4.1 合并同类型待办

Plan 阶段用哈希表，Key = `(type, optional_group_key)`。例如 QQ 消息可增加 `session_id` 作为群键，保证不同群的消息不混成一个计划，但同群多条消息共享一个“处理消息”计划。

### 4.2 优先级计算

`Plan.priority = base_priority + urgency_bonus + weight * 0.1 + (time_since_created * aging_factor)`。  
由于明确不要老化，`aging_factor` 设为 0。因此计划优先完全由 `base_priority` 和 `urgency_bonus` 决定，确保急事优先。平静期通过闲时拾取单独通路处理旧计划。

### 4.3 动作列表展开

采用策略模式：为每个 `intent` 注册一个 `ActionExpander`，返回 `[Action]`。例如：

- `handle_qq_messages`:
  1. recall_memory(query: 聚合消息内容)
  2. generate_response(memory_context, messages)
  3. send_msg(response)
  4. update_memory(new_context)
- `alarm_reminder`:
  1. evaluate_ignore(当前状态) → 若结果“忽略”，则直接跳至 4.
  2. alert_user(alarm_info)
  3. wait_ack 或直接标记
  4. finalize_alarm

### 4.4 精力评估与消耗

- 每个 Action 的 `energy_cost` 由配置表定义（如 recall_memory=5, generate_response=15, send_msg=2 等）。
- 实际消耗可偏离预估值，执行后从 state 扣减，可记录偏差用于未来学习。
- 暂停 Attention 时，当前动作不执行，精力不扣。

### 4.5 权重动态调整

Action 阶段根据执行成功/失败或用户反馈，微调原计划的 `weight`：

- 任务全部顺当完成：`weight *= 0.9`
- 执行中出现部分失败：`weight *= 1.1`（可能使计划稍更优先被重试）
- 用户主动打断：可大幅提升或降低，视策略而定。
  注意避免震荡，变化率限制在 ±10% 以内。

### 4.6 自然节律与闲时拾取

- **活跃度评估**：每个心跳计算 `activity_index = 最近 10 个心跳中 ToDo 非空的比例`。
- **安静判定**：`activity_index < 0.2` 且连续心跳数超过阈值 → 进入“闲时模式”。
- **闲时拾取触发**：在 Attention 阶段，若处在闲时模式且 Actions 为空，从 Plans 队列中取 **priority 最低** 的计划作为新 Attention（此行为称为“没事找事”），从而消化积压。若没有计划，可生成一个 `self_maintenance` 型计划（主动整理记忆等），让 Bot 有“独处人格”。

### 4.7 自动任务拟人化

- 闹钟类自动任务注入时 `urgency: gentle`，其生成的计划优先级较低。
- 展开动作列表时，第一个动作为 `evaluate_ignore`，它会读取当前 state（如是否正忙于高优对话、精力是否偏低）和距离预定时间的延迟，以概率决定本次“忽略”。若忽略，则直接完成 Attention 但标记原 Todo 为“已推迟”，并可再次注入一个新的 gentle 提醒（稍后时段）。这不会强迫 Bot，体现人性化拖延。

---

## 5. 数据流与状态转换图

### 5.1 心跳内流程（伪代码）

```
function heartbeat():
    regenerate_energy()

    if should_run_plan():
        plan_phase()

    // attention 阶段仅当手上无事
    if actions_queue.empty() and attention is None:
        attention_phase()

    // action 阶段循环
    while actions_queue not empty and energy_enough_for_next():
        action_phase_execute_one()
        if attention.state == completed:
            clear_attention()
            break   // 完成当前 attention 后立即退出，下个心跳再决定新 attention
```

### 5.2 Attention 生命周期状态图

```
null --[取计划]--> active --[动作全部完成]--> completed --> null
                  |
                  +--[精力不足]--> paused --[精力恢复+继续]--> active
```

Actions 队列随 Attention 切换而替换。

---

## 6. 边界情况与异常处理

### 6.1 精力不足中断与续接

- 中断时保留 Actions 队列和 Attention 的 `current_index`，不变动队列。
- 恢复时由于精力在每个心跳开始恢复，只需在 Action 阶段循环中再次检测，就能自然从断点继续执行。
- 多个心跳过去仍未恢复足够精力怎么办？可以设置一个最大挂起时间（柔性），超时后主动取消 Attention，并将原计划的 `weight` 调低或标记为“暂时搁置”并重新入 Plans 队列。

### 6.2 抢占式注意力（未来扩展）

当前设计为协作式：只有当 Attention 完成或暂停才会换计划。若要实现高优先级抢占，可在 Action 阶段每执行一个动作后，额外检查 Plans 队列是否有比当前 Attention 优先级极高的计划（如 urgency urgent 的新消息）。若有，可暂停当前 Attention，将其及其 Actions 队列推入一个暂存区，然后新建紧急 Attention。当前版本可先不实现。

### 6.3 空队列时的行为

- ToDo 空时 Plan 阶段无合并，不产生新计划，若有闲时拾取可能拉取旧计划。
- Plans 空且无 Attention：Bot 进入完全 idle 状态，每心跳只恢复精力，可能定期生成自维护计划。

### 6.4 展开动作执行失败

原子动作应设计为可重试或可补偿。若失败，可在 Action 阶段捕获异常，根据类型决定重试、跳过或将计划标记为失败。

---

## 7. 配置与可调参数

| 参数名                      | 建议默认值 | 说明                               |
| --------------------------- | ---------- | ---------------------------------- |
| `energy_max`                | 100        | 精力上限                           |
| `energy_regen_per_beat`     | 5          | 每心跳恢复量                       |
| `base_plan_interval`        | 3          | 基础计划间隔（心跳数）             |
| `busy_threshold`            | 0.6        | 活跃度阈值，低于此值可能进入闲时   |
| `idle_heartbeats_for_idle`  | 10         | 连续多少心跳低活跃度后视为闲时     |
| `max_actions_per_beat`      | 10         | 单心跳最大动作执行数，防止死循环   |
| `default_energy_cost`       | 见配置表   | 各动作类型的基础消耗               |
| `gentle_ignore_chance`      | 0.5        | 闲时自动任务忽略概率（模拟拖延）   |
| `self_maintenance_interval` | 50         | 空闲心跳后自动生成自维护计划的间隔 |

---

## 8. 实现建议与伪代码蓝图

下面给出核心数据结构与循环的伪代码原型，供开发对照。

```
// ---- 数据结构 ----
class State:
    energy: float
    max_energy: float
    regen: float
    plan_interval: int
    idle_counter: int

class TodoItem:
    id, type, payload, urgency, created_at

class Plan:
    id, intent, sub_items, priority, base_priority, weight

class Attention:
    plan_id, intent, priority, total_energy_est
    action_list: List<Action>
    current_idx: int
    state: enum {ACTIVE, PAUSED}

class Action:
    id, type, params, energy_cost

// ---- 全局队列 ----
todo_queue: Queue<TodoItem>
plans: PriorityQueue<Plan>  // 按 priority 最大堆
current_attention: Attention?
action_queue: Queue<Action>

// ---- 核心循环 ----
on_heartbeat():
    state.energy = min(state.max_energy, state.energy + state.regen)

    if heartbeat_count % state.plan_interval == 0:
        plan_phase()

    if action_queue.empty() and current_attention is None:
        attention_phase()

    execute_count = 0
    while not action_queue.empty() and execute_count < MAX_ACTIONS_PER_BEAT:
        next_action = action_queue.peek()
        if state.energy < next_action.energy_cost:
            if current_attention:
                current_attention.state = PAUSED
            break

        action_queue.pop()
        state.energy -= execute_action(next_action)
        current_attention.current_idx++
        execute_count++

        if current_attention.current_idx == len(current_attention.action_list):
            complete_attention()

def plan_phase():
    items = drain(todo_queue)
    groups = group_by_type(items)
    for group in groups:
        existing = find_plan_by_intent(group.intent)
        if existing and existing not in current_attention:
            existing.sub_items.extend(group.items)
            existing.priority = max(existing.priority, calc_priority(group))
            plans.update(existing)
        else:
            new_plan = Plan(intent=group.intent, sub_items=group.items,
                           priority=calc_priority(group))
            plans.push(new_plan)

def attention_phase():
    if plans.empty():
        if is_idle_and_long_idle():
            generate_self_maintenance_plan() // 没事找事
        return

    if is_idle_mode():   // 闲时模式：取最低优先级
        plan = plans.pop_lowest()
    else:
        plan = plans.pop_highest()

    attention = Attention(plan)
    attention.action_list = expand_actions(plan.intent, plan.sub_items)
    attention.total_energy_est = sum(a.energy_cost for a in attention.action_list)
    attention.state = ACTIVE
    current_attention = attention
    action_queue = Queue(attention.action_list)  // 替换队列

def is_idle_mode():
    return state.idle_counter >= IDLE_THRESHOLD and todo_queue.empty()
```

---

## 9. 附录：术语表

| 术语         | 定义                                        |
| ------------ | ------------------------------------------- |
| ToDo 队列    | 外部的原始待办事件缓冲区                    |
| Plans 队列   | 合并后的意图级计划，优先级排序              |
| Attention    | 当前唯一关注的计划上下文，持有动作列表      |
| Actions 队列 | 当前 Attention 展开的原子动作序列           |
| 精力         | 全局行动资源，消耗与恢复驱动执行节奏        |
| 自然节律     | 由群聊活跃度决定的忙/闲模式                 |
| 闲时拾取     | 安静期间主动消化低优先级计划的机制          |
| 柔性意图     | 不要求即时响应的自动任务标记                |
| 协作式调度   | 只有当前 Attention 完成或暂停，才切换新计划 |

---

本开发文档完整描述了 PAA 自循环体系的架构、数据结构、流转流程和边界策略，可直接作为原型实现与后续迭代的基础。如需进一步细化特定模块（如动作配置表、Service 适配器接口规范），可在此基础上继续扩展。
