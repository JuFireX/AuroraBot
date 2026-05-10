# Example App

`example` 是一个面向开发者的演示应用，用来说明 Aurora 应用应当如何组织。

它展示的能力包括：

- 生命周期接口：`manifest_path()`、`on_start()`、`on_stop()`、`on_tick()`
- 平台 API：`emit_event()`、`post_intention()`、`register_command()`、`log()`、`package`、`data_dir`
- 静态命令：通过 `manifest.yaml` 声明并自动注册
- 动态命令：运行时通过 `PlatformAPI.register_command()` 注册
- app-data：在 `data/app_data/im_polaris_example/` 下持久化自己的状态和笔记

## 提供的命令

- `echo_message`
  - 回显文本，并发出 `example.echoed` 事件
- `save_note`
  - 保存笔记到 app-data，并按需发出 `example.note_saved` 事件
- `publish_demo_event`
  - 手动发出一个自定义事件
- `dynamic_ping`
  - 运行时动态注册的命令，返回简单的 ping/pong 结果

## 发出的事件

- `example.started`
  - 启动时发出，演示 `post_intention`
- `example.echoed`
  - 执行 `echo_message` 后发出
- `example.note_saved`
  - 执行 `save_note` 且 `emit_event=true` 时发出
- `example.custom`
  - 执行 `publish_demo_event` 时默认发出

## app-data

应用自己的数据目录位于：

`data/app_data/im_polaris_example/`

常见文件：

- `notes.json`
  - `save_note` 产生的持久化数据
- `state.json`
  - 生命周期和 tick 状态快照

## 启动参数

可通过 `apps/config.yaml` 的 `startup` 字段传入：

- `greeting`
  - 启动事件中携带的欢迎文本
- `emit_startup_event`
  - 是否在启动时发出 `example.started`
