# AuroraBot App 开发者指南

欢迎来到 AuroraBot 应用开发指南。在 `apps` 目录下，你可以编写自己的 App 插件。本文档将向你介绍 App 的核心设计哲学、目录结构、以及开发中常用的 API。

## 1. 设计哲学 (Design Philosophy)

AuroraBot 的架构将“应用 (App)”和“大脑内核 (Brain)”解耦。App 的定位是 **环境的感知器与执行器**：
- **感知世界 (Events)**：App 负责监听外部环境的变化（如收到 QQ 消息、时钟到期、定时任务触发），并将其统一封装为 `AppEvent` 推送给大脑内核。
- **干预世界 (Commands)**：App 并不自己做复杂的业务决策。它在 `manifest.yaml` 中暴露出原子化的命令（Commands），大脑内核在分析事件后，会调用这些命令来产生实际效果（如发送消息、设置闹钟）。
- **状态隔离与持久化**：每个 App 拥有自己独立的数据目录，负责自身底层连接状态或临时数据的持久化（如通过 JSON 存储），内核不会直接干涉 App 的内部数据。

## 2. 核心应用结构

一个标准的 App 通常包含在 `apps/<your_app>/` 目录下，主要由两个文件组成：

### 2.1 `manifest.yaml`
应用的元数据声明文件。这里定义了应用的基本信息，以及暴露给内核的**命令 (Commands)**。

```yaml
package: im.polaris.example   # 应用的全局唯一标识
name: 示例应用
version: 1.0.0
brain_version: ">=5.0.0"
app_desc: >-
  描述应用的功能，内核会读取这里的描述以了解在什么场景下应该使用本应用的命令。
commands:
  - name: do_something          # 命令名称，需与 runtime.py 中的方法名一致
    description: 描述这个命令的作用，供 AI 大脑理解
    parameters:
      text:                     # 参数名
        type: string
        description: 参数说明
        required: true
    returns:
      success:
        type: boolean
        description: 返回结果说明
```

### 2.2 `runtime.py`
应用的运行逻辑，必须实现 `ApplicationProtocol` 定义的接口。框架会自动发现并加载其中的应用类。

```python
from pathlib import Path
from typing import TYPE_CHECKING
from src.brain.platform.contracts import AppEvent

if TYPE_CHECKING:
    from src.brain.platform.application_api import PlatformAPI

class ExampleApplication:
    def __init__(self):
        self._api: PlatformAPI | None = None

    # 1. 核心钩子：绑定平台 API
    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api

    # 2. 核心钩子：指向 manifest.yaml
    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    # 3. 生命周期钩子
    async def on_start(self) -> None:
        pass # 应用启动时的初始化逻辑，如读取本地配置

    async def on_tick(self) -> None:
        pass # 每帧轮询时调用，适合做定时任务检查

    async def on_stop(self) -> None:
        pass # 应用停止时的清理逻辑，如保存数据

    # 4. 命令实现 (与 manifest.yaml 中的 commands 对应)
    def do_something(self, text: str) -> dict:
        # 执行具体操作
        return {"success": True}
```

## 3. 常用 API 与上下文

通过实现 `_bind(self, api: "PlatformAPI")` 方法，应用会获得平台注入的 `api` 实例。这是应用与内核交互的唯一桥梁。

### `PlatformAPI` 常用属性与方法

- **`api.emit_event(event: AppEvent) -> None`**
  - **功能**：将事件上报给大脑内核处理。
  - **用法**：
    ```python
    api.emit_event(
        AppEvent(
            source=api.package,           # 通常填当前 app 的 package
            type="message.received",      # 事件类型
            session_id="12345",           # 发生此事件的会话/目标ID
            summary="这是一条摘要信息",      # 提供给内核的摘要
            payload={"text": "详细内容"}   # 附加的详细数据
        )
    )
    ```

- **`api.data_dir -> Path`**
  - **功能**：获取分配给当前 App 的**独立持久化数据目录**。
  - **用法**：你可以在此目录下自由创建 `.json` 或 `.db` 文件。例如 `self._config_file = api.data_dir / "config.json"`。平台已保证该目录存在。

- **`api.log(level: str, message: str) -> None`**
  - **功能**：调用平台统一日志器输出日志。也可直接使用 `src.utils.Logger.get_logger`。

- **`api.package -> str`**
  - **功能**：获取在 `manifest.yaml` 中声明的 package 名称。

## 4. 生命周期 (Lifecycle)

内核在调度 App 时，遵循以下生命周期规范：

1. **发现与注册**：解析 `manifest.yaml`，若命令声明无误，将其实例化。
2. **`_bind(api)`**：注入平台 API。
3. **`on_start()`**：异步调用。这是初始化异步资源、注册回调监听（例如 QQ 的 `on_message` 钩子）或加载本地 `data_dir` 数据的最佳时机。
4. **`on_tick()`**：在系统的主循环中频繁调用。**注意：** 此方法不应有阻塞操作。非常适合用于检查内部队列并触发超时事件（参考 Alarm 应用的 `_dispatch_due_alarms`）。
5. **`on_stop()`**：应用被卸载或系统退出时调用。务必在此处保存需要持久化的内存数据。

## 5. 开发建议

1. **让内核做决定，让 App 做执行**：App 内部不要写死复杂的业务逻辑（比如“收到特定关键字就回复XXX”），而是将关键字作为 `AppEvent` 抛出，由 Brain 决定如何调用 `send_message` 命令回复。
2. **命令粒度适中**：如 QQ 发送消息时，如果涉及长文本分段，建议在 `app_desc` 中告诉 AI “请多次调用发送命令分段发送”，而不是由 App 自己去猜测并在底层截断。
3. **容错与静默**：`on_tick` 中出现的异常会被内核捕捉，但最好在 App 内部做好 Try-Catch 防止应用崩溃；在读取 `api.data_dir` 的文件时，注意处理文件不存在或格式损坏的情况。