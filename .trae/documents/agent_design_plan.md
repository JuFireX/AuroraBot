# 智能体拟人化架构与QQ接入设计方案

## 1. 概述与目标

本方案旨在将现有的事件驱动型 NoneBot2 机器人，重构为一个具备高度拟人化心智的自主智能体。智能体将以固定心跳（Tick）驱动的方式，在后台持续运行 `update_state -> plan -> action` 的无限自循环。
QQ消息不再直接触发回复，而是作为“注意力事件”（Attention Event）进入智能体的感知队列，由智能体在 plan 阶段决定是否、何时以及如何处理这些消息。

## 2. 核心架构设计

### 2.1 状态与驱动机制 (单进程异步协程)

* **心跳驱动 (Tick)**：智能体核心循环是一个运行在后台的 `asyncio.Task`，每隔一定时间（如 5-10 秒）执行一次完整循环。

* **无限自循环模型**：

  1. **`update_state`** **(感知与状态更新)**：

     * 从“注意力队列”中提取新到达的 QQ 消息等结构化注意力事件。

     * 更新智能体内部状态（如：当前时间、精力值、当前所处环境, 注意力重点, 所有注意力事件等）。
  2. **`plan`** **(规划阶段)**：

     * AI 决策模块（大模型）读取当前 State，输出标准 JSON 格式的执行计划。

     * 模型需决定接下来的行动优先级（例如：看到消息决定立刻回复，或者觉得累了决定先休息）。
  3. **`action`** **(执行阶段)**：

     * 解析 plan 输出的 JSON，路由并调用对应的 Service（服务）。

### 2.2 模块化服务 (Services)

在 action 阶段，智能体可以调用的能力被封装为独立模块：

* **`reply_qq`** **(回复消息)**：调用语言模块组织语言，并调用 NoneBot API 发送消息。

* **`sleep`** **/** **`rest`** **(睡觉/休息)**：修改智能体的内部状态（如设定睡眠时长），在此期间可降低 Tick 频率或在 plan 阶段直接忽略普通消息。

* **`recall`** **(回忆)**：调用 Memory 模块，根据当前对话场景检索相关上下文。

* **`organize_language`** **(组织语言)**：调用语言模块生成拟人化回复。

* **`check_time`** **(查看时间)**：获取当前系统时间供后续 plan 使用。

### 2.3 记忆模块 (Memory Service)

* 作为独立的异步服务/类实例运行，维护智能体的上下文。

* **功能**：

  * **上下文拼接**：提供 `action` 阶段的 `recall` 服务，将历史对话、当前状态拼接为 Prompt 友好的上下文。

  * **程序性遗忘**：定期清理久远的普通记忆，或通过大模型将短期记忆压缩为长期记忆（摘要），以控制 Token 消耗并模拟人类遗忘曲线。

  * 后期可能会改造为RAG增强检索的(或自研)记忆模块

### 2.4 语言模块 (Language Service)

* 在 `action` 阶段被调用（通常作为 `reply_qq` 的前置准备）。

* **功能**：

  * 读取 `soul/` 目录下的“灵魂文档”（包含人设、性格、语言风格、世界观等）。

  * 结合 Memory 模块提供的上下文，组织出符合拟人化设定的最终回复文本。

## 3. 具体修改计划 (Proposed Changes)

### 3.1 新增文件与目录

1. **`polaris/core/agent.py`**

   * 定义 `Agent` 类，包含 `run_loop()`, `update_state()`, `plan()`, `action()` 核心逻辑。

   * 定义全局注意力队列 `attention_queue`。
2. **`polaris/core/memory.py`**

   * 定义 `MemoryService`，实现短期记忆存储、记忆检索（recall）和定期遗忘/总结机制。
3. **`polaris/core/language.py`**

   * 定义 `LanguageService`，负责读取 `soul/` 目录并根据上下文请求大模型生成最终回复。
4. **`polaris/services/agent_actions.py`**

   * 实现具体的 Action 函数（`reply_qq`, `sleep`, `check_time` 等），供 Agent 的 action 阶段调用。
5. **`soul/persona.md`**

   * 创建初始的智能体灵魂文档，设定其拟人化性格与基础认知。

### 3.2 修改现有文件

1. **`polaris/main.py`**

   * **修改消息处理逻辑**：不再在 `handle_private` 和 `receive_group_event` 中直接调用大模型回复。改为将 `event` 对象和必要信息封装后，`put` 到 `attention_queue` 中。

   * **注册后台任务**：使用 NoneBot 的 `@driver.on_startup` 钩子，启动 Agent 的后台 `run_loop` 协程。
2. **`polaris/services/model/ModelService.py`** (可选)

   * 优化 JSON 结构化输出的请求方法，供 Agent 的 plan 阶段使用（利用 LiteLLM 的 JSON mode）。

## 4. 假设与决策 (Assumptions & Decisions)

* **决策输出**：Agent plan 阶段的大模型强制输出 JSON，例如 `{"thought": "思考过程", "action": "reply_qq", "args": {"target": "user_123"}}`。

* **并发安全**：由于使用单进程 `asyncio`，状态读写和队列操作天然具备较高的并发安全性，无需复杂的进程间锁机制。

* **发信能力**：QQ机器人的发送能力依赖 NoneBot 的 `Bot` 实例。我们在消息入队时会保存对应的上下文（如 group\_id, user\_id, bot\_id），以便 `reply_qq` 服务能在任意时刻主动发起消息。

## 5. 验证步骤 (Verification Steps)

1. 编写完核心循环后，启动 NoneBot，观察终端日志是否按设定的 Tick 频率稳定输出 `[Plan]`, `[Action]` 等心跳日志。
2. 向机器人发送 QQ 私聊消息，验证消息是否成功进入 Attention 队列，并在随后的 Tick 中被智能体“注意到”。
3. 验证智能体能否根据提示词（灵魂文档）正确调用 `recall` 和 `organize_language` 生成回复，并最终调用 `reply_qq` 成功将消息发送回 QQ。
4. 发送大量消息，验证 Memory 模块的程序性遗忘机制是否正常触发。

