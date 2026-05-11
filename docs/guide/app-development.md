---
title: App 开发指南
description: 从目录结构到生命周期，系统化说明 AuroraBot 的 App 开发方式。
---

# App 开发指南

AuroraBot 把“应用”定义为环境的感知器与执行器。一个 App 不负责高阶推理，而是把外部变化转成事件，把内核决定的动作落成命令。

## 开发前先记住三件事

1. App 负责感知与执行，不负责复杂决策
2. App 应暴露原子命令，而不是隐藏复杂业务流程
3. App 的私有状态归 App 自己管理，内核不直接侵入

## 一个标准 App 的目录结构

```text
apps/<your_app>/
  __init__.py
  manifest.yaml
  runtime.py
  README.md
  config.example.json
```

## 核心文件说明

### `manifest.yaml`

它是应用的能力声明文件，负责告诉平台和内核：

- 这个应用是谁
- 它提供哪些命令
- 每个命令需要什么参数
- 命令返回值大致长什么样

示例：

```yaml
package: im.polaris.example
name: 示例应用
version: 1.0.0
brain_version: ">=5.0.0"
app_desc: >-
  描述这个应用适合在什么场景下被调用。
commands:
  - name: do_something
    description: 执行一个示例动作
    parameters:
      text:
        type: string
        description: 要处理的文本
        required: true
    returns:
      success:
        type: boolean
        description: 是否成功
```

### `runtime.py`

它负责应用的实际运行逻辑。框架会在这里找到应用类，绑定平台能力，并在生命周期内调度它。

示例：

```python
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.platform.application_api import PlatformAPI


class ExampleApplication:
    def __init__(self) -> None:
        self._api: PlatformAPI | None = None

    def _bind(self, api: "PlatformAPI") -> None:
        self._api = api

    def manifest_path(self) -> Path:
        return Path(__file__).with_name("manifest.yaml")

    async def on_start(self) -> None:
        pass

    async def on_tick(self) -> None:
        pass

    async def on_stop(self) -> None:
        pass

    def do_something(self, text: str) -> dict:
        return {"success": True}
```

## 平台注入的常用能力

通过 `_bind(self, api)` 之后，App 会拿到统一的 `PlatformAPI`。

### `api.emit_event(event)`

把外部变化上报给内核。

```python
api.emit_event(
    AppEvent(
        source=api.package,
        type="message.received",
        session_id="12345",
        summary="收到一条消息",
        payload={"text": "你好"},
    )
)
```

### `api.data_dir`

每个 App 都会拿到一个独立的数据目录，适合存放：

- 配置文件
- 缓存
- 临时状态
- 运行日志或快照

### `api.log(level, message)`

使用平台统一日志器记录运行信息。

### `api.package`

获取当前 App 在 `manifest.yaml` 中声明的包名。

## 生命周期

App 的运行通常遵循下面的顺序：

1. 平台发现并实例化应用
2. 调用 `_bind(api)` 注入平台能力
3. 调用 `on_start()` 完成初始化
4. 在循环中持续调用 `on_tick()`
5. 停止时调用 `on_stop()`

### `on_start()`

适合做：

- 读取本地配置
- 初始化连接
- 注册回调
- 恢复运行状态

### `on_tick()`

适合做：

- 时间轮询
- 检查内部队列
- 派发到期任务

不适合做：

- 长时间阻塞操作
- 重型同步 I/O

### `on_stop()`

适合做：

- 保存内存状态
- 关闭连接
- 清理资源

## 开发建议

### 让内核做决策，让 App 做执行

不要把“看到某个关键词就立刻执行复杂流程”这类逻辑写死在 App 里。更好的方式是把它抛成事件，由内核决定是否调用命令。

### 命令粒度保持原子化

好的命令应该：

- 语义明确
- 参数清晰
- 便于组合
- 便于测试

### 优先保证容错

尤其是在 `on_tick()`、文件读取、外部连接这些环节里，要优先考虑异常处理与降级路径。

## 推荐的开发流程

1. 先设计 `manifest.yaml`
2. 再实现 `runtime.py`
3. 用 `config.example.json` 说明配置格式
4. 补 `README.md` 说明能力边界
5. 通过 `app.py` 或未来的 `aur` 做独立调试

## 一个简单的自检清单

- 是否声明了清晰的 `package`
- 是否为每个命令写了准确描述
- 是否避免让 App 直接承担复杂决策
- 是否把私有状态都放在 `api.data_dir`
- 是否处理了配置缺失与文件损坏等异常

## 继续阅读

- 想理解平台如何调度 App：读 [平台运行时](../architecture/platform-runtime.html)
- 想理解命令如何最终被执行：读 [内核流水线](../architecture/kernel-pipeline.html)
