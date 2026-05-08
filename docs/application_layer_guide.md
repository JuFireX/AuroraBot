# 应用层结构与使用说明

## 1. 文档目的

这份文档只讨论 **应用层**，不讨论旧的 `PAA` 内核细节。

假设前提如下：

- 现有内核将被彻底推翻
- 只保留“异步启动 / 停止 / 周期 tick”的基础循环框架
- 未来的认知、会话、任务、执行等逻辑由新内核重新定义

在这个前提下，应用层应该被整理成一个 **稳定边界**：

- 应用负责接入外部世界
- 应用负责提供能力
- 应用负责产生事件
- 应用不负责认知决策
- 内核只通过统一接口与应用层交互

---

## 2. 应用层应该保留什么

如果你要推翻现有内核，我建议只保留下面这些应用层资产：

### 2.1 生命周期协议

当前已经存在一个很小且清晰的协议，见 [application_protocol.py](file:///e:/AuroraBot/src/brain/platform/application_protocol.py)：

```python
@runtime_checkable
class ApplicationProtocol(Protocol):
    def manifest_path(self) -> Path: ...
    async def on_start(self) -> None: ...
    async def on_stop(self) -> None: ...
    async def on_tick(self) -> None: ...
```

这套协议值得保留，因为它非常薄，而且和内核解耦。

### 2.2 ApplicationHost 作为装配器

当前 [application_host.py](file:///e:/AuroraBot/src/brain/platform/application_host.py) 的核心价值不是“PAA”，而是：

- 读取应用 `manifest`
- 绑定 `PlatformAPI`
- 注册应用暴露的工具能力
- 统一调用 `on_start / on_tick / on_stop`

这层可以保留，但要**降级成纯装配器**，不要再掺认知语义。

### 2.3 PlatformAPI 作为内核边界

当前 [application_api.py](file:///e:/AuroraBot/src/brain/platform/application_api.py) 的方向是对的：

- 内核不要让应用直接摸内部数据结构
- 应用只通过 `PlatformAPI` 和内核说话

这个思想建议保留，但 API 内容应该重整。

### 2.4 Manifest 机制

当前 [manifest.py](file:///e:/AuroraBot/src/brain/platform/manifest.py) 的能力声明模式值得保留：

- `package`
- `name`
- `version`
- `tools`
- `planning_hint`

其中最有价值的是：

- 工具 schema 声明
- 包名前缀命名空间
- 应用元数据

`planning_hint` 是否保留，可以由新内核决定；但 `manifest` 本身很值得保留。

### 2.5 各应用 runtime

现有应用 runtime 的价值主要在“外部接入逻辑”：

- [qq/runtime.py](file:///e:/AuroraBot/src/applications/qq/runtime.py)：QQ 事件接入与消息发送
- [alarm/runtime.py](file:///e:/AuroraBot/src/applications/alarm/runtime.py)：提醒调度与触发
- [diary/runtime.py](file:///e:/AuroraBot/src/applications/diary/runtime.py)：日记持久化
- [mcp_container/adapter.py](file:///e:/AuroraBot/src/applications/mcp_container/adapter.py)：MCP 容器配置装载

这些都属于“应用外设层”，应该和内核解耦保留。

---

## 3. 应用层不应该再承担什么

如果你要重建内核，我建议明确把下面这些东西从应用层剥离掉：

### 3.1 不负责认知

应用不要决定：

- 为什么要回复
- 回复哪些消息
- 当前任务优先级
- 是否创建计划
- 如何展开动作链

应用只上报事件，只执行命令。

### 3.2 不负责规划

应用不要理解：

- `todo`
- `plan`
- `attention`
- `action queue`

这些都属于内核内部模型，不应该泄露到应用实现里。

### 3.3 不负责人格

应用可以描述自己的平台约束，但不该承载人格逻辑。

例如：

- QQ 应用可以声明“文本会被真人看到”
- 但不该负责决定“小光现在该用什么语气说话”

### 3.4 不负责 fallback 决策

应用 runtime 不该负责：

- 文本兜底生成
- 对话补全
- 参数修补策略

这些都应该属于新内核中的规划层或执行前校验层。

---

## 4. 推荐的应用层结构

建议把应用层整理成下面四层，但都归到“应用系统”名下：

```text
applications/
├── protocols/      # 统一协议与抽象接口
├── manifests/      # 或继续每个应用自带 manifest
├── runtimes/       # 外部平台接入与执行逻辑
├── adapters/       # 平台 SDK / 协议桥接
└── services/       # 应用私有持久化、缓存、状态
```

如果不想动目录，也可以维持现有结构，但逻辑上请按下面职责理解。

### 4.1 Runtime

Runtime 是应用的“外部世界接口层”，负责：

- 接收外部事件
- 转成标准化事件
- 调用平台发送接口
- 读写本应用自己的持久数据

不负责认知与规划。

### 4.2 Manifest

Manifest 是应用对内核的“声明文件”，负责：

- 应用名字、版本、包名
- 暴露哪些工具
- 每个工具的参数和返回 schema
- 该应用的能力说明

### 4.3 Adapter

Adapter 是“外部 SDK 桥接层”，负责：

- OneBot / MCP / HTTP / WebSocket / 定时器 等接入
- 把第三方库的回调格式转成应用内部可读格式

### 4.4 Service

Service 是应用私有逻辑层，负责：

- 本地 JSON / YAML 持久化
- 目标缓存
- 外设状态管理
- 重试、节流、发送队列

它不该直接依赖内核内部模型。

---

## 5. 新内核下推荐的最小接口

如果你只保留异步循环框架，我建议把应用层对内核的交互压缩成下面这几个最小接口。

### 5.1 Application

```python
from pathlib import Path
from typing import Protocol


class Application(Protocol):
    def manifest_path(self) -> Path: ...
    async def on_start(self) -> None: ...
    async def on_stop(self) -> None: ...
    async def on_tick(self) -> None: ...
```

这基本就是当前协议，已经足够。

### 5.2 AppContext

建议新建一个比 `PlatformAPI` 更干净的上下文对象：

```python
class AppContext:
    def emit_event(self, event: AppEvent) -> None: ...
    def register_command(self, command: CommandSpec) -> None: ...
    def log(self, level: str, message: str) -> None: ...
    @property
    def data_dir(self) -> Path: ...
```

这里我建议把旧 `post_intention()` 改名成更中性的 `emit_event()`，因为你都准备推翻旧内核了，就别把 `todo` 概念继续固化在应用边界上。

### 5.3 AppEvent

建议应用只向内核发“事件”，不要发旧式 `TodoItem`：

```python
from dataclasses import dataclass, field
from typing import Any
import time
import uuid


@dataclass(slots=True)
class AppEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    type: str = ""
    session_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
```

建议字段语义如下：

- `source`：应用包名，例如 `im.polaris.qq`
- `type`：事件类型，例如 `message.received`、`alarm.triggered`
- `session_id`：会话或目标实体 ID
- `payload`：事件详情

### 5.4 CommandSpec

建议把旧 capability 注册也重新命名成更中性的命令或工具描述：

```python
@dataclass(slots=True)
class CommandSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    returns_schema: dict[str, Any]
    handler: Callable[..., Any]
```

如果以后你希望“工具”和“内部动作”分开，这里还可以继续拆。

---

## 6. 建议保留的装配流程

即使你推翻内核，我也建议保留下面这个启动流程，因为它很稳：

### 6.1 启动阶段

1. 加载配置
2. 初始化日志和数据目录
3. 初始化应用宿主 `ApplicationHost`
4. 注册所有应用
5. 让宿主依次调用每个应用的 `on_start()`
6. 启动新的异步主循环

### 6.2 运行阶段

异步主循环只保留基础骨架：

```python
async def run_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await app_host.tick()
        await kernel.tick()
        await asyncio.sleep(interval)
```

这里的重点是：

- `app_host.tick()` 只负责应用侧周期任务
- `kernel.tick()` 是新内核自己的事
- 两边不要互相知道内部细节

### 6.3 停止阶段

1. 发出 stop signal
2. 停止主循环
3. 依次调用应用 `on_stop()`
4. 由各应用自行持久化自己的本地状态

---

## 7. 当前四个应用应该怎么理解

### 7.1 QQ 应用

当前 [QQApplication](file:///e:/AuroraBot/src/applications/qq/runtime.py) 的应用层价值应被重新定义为：

- 接收 QQ 消息事件
- 维护 `session_id -> target` 的发送目标映射
- 执行发送消息命令
- 记录收发事件

不应该继续把它理解为“聊天大脑”。

建议未来对外只暴露两类东西：

- 事件：`message.received`
- 命令：`send_message`、`send_private_message`、`at_user`

### 7.2 Alarm 应用

当前 [AlarmApplication](file:///e:/AuroraBot/src/applications/alarm/runtime.py) 的价值是：

- 管理定时器
- 到点发出提醒事件
- 提供“创建提醒”命令

这很适合被保留成一个标准事件源。

建议未来对外抽象成：

- 事件：`alarm.triggered`
- 命令：`alarm.create`

### 7.3 Diary 应用

当前 [DiaryApplication](file:///e:/AuroraBot/src/applications/diary/runtime.py) 的价值是：

- 提供结构化持久化写入
- 刷新相关索引或快照

它本质上是“带副作用的存储命令应用”，不是事件驱动平台。

建议未来对外抽象成：

- 命令：`diary.write`

### 7.4 MCPContainer

当前 [MCPContainer](file:///e:/AuroraBot/src/applications/mcp_container/adapter.py) 还只是骨架：

- 加载 server config
- 还没有稳定接入远端能力

建议未来把它定位成：

- 动态工具源管理器
- 或外部工具代理容器

但别让它过早进入核心架构。

---

## 8. 推荐的 manifest 写法

如果你保留 manifest，我建议把它收敛成这套最小字段：

```yaml
package: im.polaris.qq
name: QQ聊天
version: 1.0.0
type: application

events:
  - message.received

commands:
  - name: send_message
    description: 向目标会话发送一条文本消息
    parameters:
      session_id:
        type: string
        required: true
      text:
        type: string
        required: true
```

### 8.1 为什么建议从 `tools` 改成 `commands`

因为你要彻底重做内核后，“tool” 这个名字很容易继续把新系统拉回旧的 LLM function-call 叙事。

如果你想保留兼容，也可以内部继续叫 `tools`，但我更建议：

- 对应用作者：叫 `commands`
- 对模型层：未来怎么映射都行

### 8.2 `planning_hint` 怎么办

当前它有价值，但如果你要彻底重建内核，我建议先把它降级成可选字段：

```yaml
notes:
  - 文本会被真人看到
  - 连续消息通常应合并理解后再回应
```

也就是说：

- 应用只提供平台约束说明
- 至于这些说明最终怎么进入模型上下文，由新内核决定

---

## 9. 应用层使用说明

这一节按“以后怎么新增一个应用”来写。

### 9.1 第一步：创建应用目录

建议结构：

```text
src/applications/my_app/
├── __init__.py
├── runtime.py
└── manifest.yaml
```

### 9.2 第二步：实现应用类

最小模板如下：

```python
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.brain.platform.application_api import PlatformAPI


class MyApplication:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        return None

    async def on_stop(self) -> None:
        return None

    async def on_tick(self) -> None:
        return None
```

如果你后面换成 `AppContext`，这里只需要替换类型名和调用方法，整体结构不变。

### 9.3 第三步：写 manifest

示例：

```yaml
package: im.polaris.my_app
name: 我的应用
version: 1.0.0
type: application
tools:
  - name: do_something
    description: 执行一个动作
    parameters:
      target:
        type: string
        description: 目标
        required: true
    returns:
      ok:
        type: boolean
        description: 是否成功
```

### 9.4 第四步：暴露命令处理函数

如果 manifest 里写了：

```yaml
tools:
  - name: do_something
```

那应用类里必须实现同名方法：

```python
async def do_something(self, target: str) -> dict[str, object]:
    return {"ok": True}
```

### 9.5 第五步：向内核发事件

如果应用接收到外部事件，应当：

1. 做平台格式清洗
2. 转成统一事件结构
3. 通过 `emit_event()` 交给内核

示例：

```python
self._api.emit_event(
    AppEvent(
        source="im.polaris.qq",
        type="message.received",
        session_id=session_id,
        payload={
            "user_id": user_id,
            "text": text,
            "is_group": is_group,
        },
    )
)
```

如果你在重构前暂时还没改 API 名字，就等价于现在的 `post_intention()`。

### 9.6 第六步：在主程序注册

在 [main.py](file:///e:/AuroraBot/src/main.py) 里加入：

```python
await app_host.register(MyApplication())
```

---

## 10. 应用开发时的规则

我建议你后续给自己定下面这些硬规则。

### 10.1 应用只关心输入输出

应用层永远只处理：

- 收到什么
- 发出什么
- 自己要保存什么

不要碰内核里的推理状态。

### 10.2 应用的本地状态只放自己目录

统一使用：

- `api.data_dir`

这样每个应用的缓存、事件、映射、配置都放自己名下，方便迁移和排查。

### 10.3 应用接口要幂等、易观测

命令处理函数最好：

- 返回结构化结果
- 对失败有明确返回
- 写清副作用

### 10.4 不在应用层偷偷塞认知策略

例如：

- 不在 QQ runtime 里判断“该不该回”
- 不在 Alarm runtime 里判断“提醒是否重要”
- 不在 Diary runtime 里判断“这段记忆值不值得写”

这些都交给新内核。

---

## 11. 我对你这次重构的建议

如果你要“只保留异步循环框架”，我建议你的第一步不是先写新内核，而是先把应用层边界固定住。

推荐顺序如下：

1. 保留 `ApplicationProtocol`
2. 把 `PlatformAPI` 重命名并缩成最小接口
3. 把 `post_intention()` 改成 `emit_event()`
4. 把 `CapabilitySpec` / `tool` 改成你更想要的 `CommandSpec` / `command`
5. 保持 `ApplicationHost` 只做装配
6. 再去重写新内核

这样做的好处是：

- 先把“外设边界”稳定住
- 后面怎么重写认知层都不会把应用全带崩

---

## 12. 最后的建议结论

如果未来系统要更清楚，我建议把应用层定义成一句话：

> **应用层是“世界接口层 + 命令执行层 + 应用私有状态层”，不是认知层，也不是规划层。**

只要你在重构时守住这条边界：

- QQ、Alarm、Diary、MCP 都能继续复用
- 新内核可以自由替换
- 异步循环框架也能保持极简

这会比继续围绕旧的 `PAA` 术语修修补补稳得多。
