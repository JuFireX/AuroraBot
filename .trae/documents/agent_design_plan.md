# Bot 功能实现与架构填充计划

## 概述 (Summary)

根据你最新提供的架构（基于文件系统解耦的状态/计划池和分离的职责模块），我将对 `polaris` 各核心模块的内容进行填充，以完成智能体的完整功能循环和基础记忆/语言组织能力。

## 当前状态分析 (Current State Analysis)

1. `polaris/main.py`: 已包含对 QQ 群聊和私聊的拦截，但放入注意力队列 (`attention_queue`) 的代码被注释，未与记忆模块连通。(留言: 需要谨慎设计注意事件队列. 思考该队列和attentions.json这个注意事件之间的关系)
2. `polaris/brain/core/agent.py`: `BrainLoop` 单例已经声明了基本的 `plan`, `act`, `update` 循环框架，但内部逻辑空缺，需要操作 `attentions.json` 和 `plans.json` 状态文件。
3. `polaris/brain/memory/memory.py`: `MemoryService` 框架已经建立，但读写记忆记录到本地文件 (`database/20260426.json`) 的逻辑未实现。(留言: 这个只是示例文件, 你可以使用更细粒度的时间)
4. `polaris/brain/language/language.py`: 已能读取 `SOUL.md`，但未实现调用 LLM 获取回复文本的实际逻辑。
5. `polaris/brain/model/ModelService.py`: 仅提供了 `get_format_response` (输出 JSON)，缺少输出纯文本的 `get_text_response`。(留言: 不需要, 文本同样使用格式化输出, 数据流转到发信模块时使用json中的字段即可)
6. `polaris/services/RestService.py` & `TimeService.py`: action 对应的服务函数参数签名与 `ACTION_ROUTER` 期望传入的 `(agent_state, args)` 不符。(留言: 这些服务都是需要重新设计的. 现在里面的都是残存代码, 属于脏代码, 没有参照意义)

## 详细实施计划 (Proposed Changes)

1. **更新** **`polaris/main.py`** **(事件入口)**
   - 取消注释 `brain_instance.attention_queue.put`，修正事件字段为 `{"type": "qq_msg", "bot_id": bot.self_id, "group_id": event.group_id, "target_id": event.user_id, "trigger_event": plain_text}` 以对齐 prompt 的要求。
   - 在收到消息时，同步调用 `memory_service.record(role=f"user_{event.user_id}", ...)` 将用户的发言录入记忆中。
2. **填充** **`polaris/brain/core/agent.py`** **(智能体主循环)**
   - **初始化**: 增加 `self.attention_queue = asyncio.Queue()`，并确保 `attentions.json` 和 `plans.json` 存在。
   - **`update()`**: 取出 `attention_queue` 中积累的新事件，追加到 `attentions.json` 中，更新当前的注意力池。
   - **`plan()`**: 读取 `attentions.json` 中的当前状态和事件，使用 `prompt_plan.md` 调用 `get_format_response` 获取 JSON 动作决策。生成新计划后存入 `plans.json` 并清空注意力池中的事件。
   - **`act()`**: 读取 `plans.json`，弹出队首计划，根据 `plan["action"]` 调用 `ACTION_ROUTER` 对应的服务，传入当前的 `state` 和 `args`。
3. **填充** **`polaris/brain/memory/memory.py`** **(基础全上下文记忆)**
   - 实现 `record()`: 将带时间戳和角色的发言追加到 `database/20260426.json` 文件（作为一个 JSON 数组）。
   - 实现 `recall(limit)`: 读取 JSON 文件，提取最近的记录（全上下文或限制条数），将其拼接成形如 `[时间] 角色: 内容` 的字符串上下文，供语言模块和决策模块使用。
   - 实现 `forget()`: 通过清空 JSON 列表来实现基础遗忘。
4. **更新** **`polaris/brain/model/ModelService.py`** **(模型交互)**
   - 新增 `get_text_response(system_prompt: str, user_prompt: str) -> str`，用于无需强制 JSON 格式的常规对话文本生成。
5. **填充** **`polaris/brain/language/language.py`** **(语言与回复组织)**
   - 实现 `organize_reply(context, trigger_event)`: 利用读取到的 `SOUL.md` 作为 system prompt，结合 `context` 和 `trigger_event` 作为 user prompt，调用 `get_text_response` 生成最终纯文本回复。
6. **更新服务参数签名 (`polaris/services/RestService.py`** **&** **`TimeService.py`)**
   - 修改 `sleep`, `rest`, `idle`, `check_time`，为其增加 `(agent_state: dict, args: dict)` 的参数定义，以确保 `ACTION_ROUTER` 的统一调用不抛出异常。

## 假设与约定 (Assumptions & Decisions)

- 为了避免文件并发读写异常，使用单进程异步下的阻塞文件读写 (JSON 读取/写入很快，不至于造成明显延迟，如果文件变大可以后续改用 `aiofiles`)。
- 注意力池在 `plan()` 阶段如果存在事件，就会调用 LLM。如果没有任何事件，则跳过 `plan()` 以节省 Token。(留言: 不行! 注意力池没有东西说明事情做完了, 那可以plan一些娱乐活动给自己啊! 我们写的又不是机器人, 一个数字生命有她自己的生活)
- 采用最基础的记忆上下文：直接将用户发言与 Bot 发言按时间线堆叠记录。

## 验证步骤 (Verification)

- 运行 `uv run .\bot.py`。
- 测试向 Bot 发送私聊消息，观察日志中事件进入 `attention_queue`、写入 `attentions.json`。
- 观察 `plan` 阶段日志是否正确生成了包含 `reply_qq` (或其它 action) 的 JSON 决策。
- 验证回复能否正常触发并生成具有 `SOUL.md` 风格的文字。
- 检查 `database/20260426.json` 中是否正常记录了对话上下文。

