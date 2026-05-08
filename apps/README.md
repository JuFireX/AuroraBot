**现在项目的运行方式**

- [main.py](file:///e:/AuroraBot/src/main.py) 现在只做：
- 注册应用
- 启动 `ApplicationHost`
- 跑一个最小异步 loop
- 在 loop 里周期调用 `app_host.tick()`
- 不再启动旧 `engine`
- 不再恢复旧队列
- 不再注册记忆能力
- 不再碰 `todo/plan/action/attention`

**我重构了哪些边界**

- 应用上报不再依赖 `TodoItem`
- 新的一等契约在 [contracts.py](file:///e:/AuroraBot/src/brain/platform/contracts.py)：
- `AppEvent`
- `CommandSpec`
- `PlatformAPI` 现在提供的是：
- `emit_event()`
- `post_intention()` 作为兼容别名，但语义已经转成事件
- `register_command()`
- `log()`
- `data_dir`
- `package`
- `ApplicationHost` 现在负责：
- 注册应用
- 从 manifest 注册命令
- 保存命令表
- 接收事件
- 提供 `invoke_command()` / `peek_events()` / `drain_events()`

**应用层现在是什么状态**

- [qq/runtime.py](file:///e:/AuroraBot/src/applications/qq/runtime.py)
  - 已从旧 `TodoItem`、`session_buffer` 解耦
  - 收到消息时发 `AppEvent(type="message.received")`
  - 保留发送能力和本地事件记录
  - 新增 `enable_listener=False`，方便独立测试，不依赖 NoneBot 消息钩子
- [alarm/runtime.py](file:///e:/AuroraBot/src/applications/alarm/runtime.py)
  - 已从旧 `TodoItem` 解耦
  - 到点时发 `AppEvent(type="alarm_reminder" / "diary_prompt")`
- [diary/runtime.py](file:///e:/AuroraBot/src/applications/diary/runtime.py)
  - 已从旧语义记忆/快照系统解耦
  - 现在就是纯持久化写入，并发出 `AppEvent(type="diary.written")`
- [mcp_container/adapter.py](file:///e:/AuroraBot/src/applications/mcp_container/adapter.py)
  - 保留骨架
  - 顺手修了配置读取，改成真正按 YAML 读 `servers.yaml`

**独立测试入口**

- 我新增了项目根目录入口：[run_app_test.py](file:///e:/AuroraBot/run_app_test.py)
- 这个文件就是你要的“应用功能测试入口”
- 它不依赖旧内核
- 可以直接：
- 注册若干应用
- 调用某个应用命令
- 注入一个事件
- 单独跑若干次 `tick`

**怎么用**

- 查看当前注册的应用和命令：

```bash
uv run python .\run_app_test.py
```

- 独立调用日记应用命令：

```bash
uv run python .\run_app_test.py --apps diary alarm --command im.polaris.diary.write_diary --payload "{date: 2026-05-08, summary: 独立测试}"
```

- 独立向 QQ 应用注入一个事件：

```bash
uv run python .\run_app_test.py --apps qq --event-type message.received --event-source im.polaris.qq --session-id 2779675416 --payload "{text: 你好, user_id: '2779675416'}"
```

- 单独跑若干次应用 tick：

```bash
uv run python .\run_app_test.py --apps alarm --ticks 3
```

**注意**

- `payload` 现在支持：
- JSON
- 也支持更适合 PowerShell 的 YAML 风格简写，比如 `{date: 2026-05-08, summary: 独立测试}`

**测试结果**

- 单测已改成面向新框架：
- [test_application_host.py](file:///e:/AuroraBot/tests/test_application_host.py)
- [test_qq_application.py](file:///e:/AuroraBot/tests/test_qq_application.py)
- 原 manifest 测试保留：
- [test_manifest_loading.py](file:///e:/AuroraBot/tests/test_manifest_loading.py)
- `uv run python -m unittest discover -s tests -v` 通过，`5/5 OK`
- `run_app_test.py` 已实测通过：
- 独立调用 `Diary` 命令成功
- 独立注入 `QQ` 事件成功

**你现在得到的工程形态**

- 这是一个**应用框架**
- 不是旧的认知系统
- 应用已经可以：
- 独立注册
- 独立运行
- 独立发事件
- 独立执行命令
- 你后面只需要往这套边界后面接你自己的新内核，不用再碰应用实现的输入输出面

**建议你下一步**

- 先别急着写复杂认知层
- 先确定你自己的新 kernel 只吃两样东西：
- `AppEvent`
- `CommandSpec`
- 也就是：
- 应用负责“世界输入/输出”
- 你的内核负责“理解/调度/决策”
