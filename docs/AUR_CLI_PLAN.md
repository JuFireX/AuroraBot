# AUR CLI 规划案

## 目标

将当前的应用测试入口 `app.py` 演进为统一的应用工具链，但对外统一使用更有辨识度的名字：`aur`。

`aur` 的职责分为两部分：

- 开发期工具：扫描应用、按配置加载应用、调用命令、注入事件、执行 tick。
- 分发期工具：打包 `.aur`、安装 `.aur`、卸载应用、初始化或修复应用配置。

这意味着 `app.py` 未来不再只是“测试脚本”，而是 `aur` 的早期实现载体。后续可以保留 `app.py` 作为兼容入口，但主语义应逐步迁移到 `aur`。

## 命名结论

- CLI 工具名统一使用 `aur`
- 包格式后缀统一使用 `.aur`
- 文档、命令帮助、后续脚本入口全部围绕 `aur` 命名

推荐的最终使用方式：

```bash
uv run python .\aur.py list
uv run python .\aur.py run
uv run python .\aur.py pack --app qq
uv run python .\aur.py install --file .\dist\qq-1.0.0.aur
```

在正式切换之前，也可以保留：

```bash
uv run python .\app.py ...
```

但应将其视为兼容层，而不是长期主入口。

## 与现状的衔接

当前项目已经具备 `aur` 的几块基础能力：

- 应用扫描与动态实例化已经从硬编码切到目录发现，见 [app_discovery.py](file:///e:/AuroraBot/src/brain/platform/app_discovery.py)
- 应用总配置已经从系统级 `Config` 中解耦，统一由 [app_config.py](file:///e:/AuroraBot/src/brain/platform/app_config.py) 管理
- 当前独立测试入口是 [app.py](file:///e:/AuroraBot/app.py)
- 每个应用已经开始具备独立资料与示例配置，例如 [alarm/README.md](file:///e:/AuroraBot/apps/alarm/README.md) 和 [alarm/config.example.json](file:///e:/AuroraBot/apps/alarm/config.example.json)

因此，后续工作重点不是推翻重写，而是将这些能力收束到统一 CLI 结构里。

## `aur` 的职责边界

`aur` 应只处理“应用层”的事情，不直接承担内核推理职责。

它负责：

- 发现有哪些可用应用
- 依据 `apps/config.yaml` 判断是否启用
- 实例化并注册应用
- 直接调用应用命令做独立测试
- 注入测试事件
- 打包和安装应用
- 辅助应用配置初始化

它不负责：

- Brain 的认知推理
- Kernel 的长期调度策略
- 系统级 `.env` 管理

## CLI 结构建议

建议将 `aur` 设计为“子命令式” CLI，而不是继续扩展一组平铺参数。

推荐命令结构如下：

### `aur list`

列出当前扫描到的应用，以及它们在 `apps/config.yaml` 中的状态。

建议展示字段：

- `app_key`
- `package`
- `enabled`
- `has_readme`
- `has_config_example`

### `aur run`

按 `apps/config.yaml` 启动当前启用的应用。

建议能力：

- 默认读取 `apps/config.yaml`
- 支持 `--apps qq alarm`
- 支持 `--dry-run`

### `aur command`

直接调用某个应用命令，用于开发期调试。

示例：

```bash
uv run python .\aur.py command --app diary --name write_diary --payload "{date: 2026-05-08, summary: 测试}"
```

### `aur event`

向 host 直接注入测试事件。

示例：

```bash
uv run python .\aur.py event --apps qq --type message.received --source im.polaris.qq --session-id 123 --payload "{text: 你好}"
```

### `aur tick`

执行若干次应用 `tick`，便于测试时序应用。

示例：

```bash
uv run python .\aur.py tick --apps alarm --count 3
```

### `aur config init`

扫描 `apps/` 目录并生成一个初始化版的 `apps/config.yaml`。

这个能力已经有基础逻辑，后续只是转成正式子命令。

### `aur pack`

将某个应用目录打成 `.aur` 包。

示例：

```bash
uv run python .\aur.py pack --app qq --output .\dist\qq-1.0.0.aur
```

### `aur install`

安装一个 `.aur` 包到 `apps/` 目录，并自动补充 `apps/config.yaml` 条目。

### `aur uninstall`

卸载一个应用。

建议默认仅删除 `apps/<app>` 目录，不删除 app-data，除非显式传入 `--purge-data`。

## `.aur` 包格式建议

第一版不需要发明复杂格式，可以直接使用 zip，后缀名改成 `.aur`。

### 最小包内容

每个 `.aur` 包至少应包含：

- `manifest.yaml`
- `__init__.py`
- `runtime.py`
- 该应用依赖的其他 Python 文件
- `README.md`
- `config.example.json`
- `aur.yaml`

### `aur.yaml` 建议字段

建议定义如下元数据：

```yaml
format_version: 1
app_key: qq
package: im.polaris.qq
version: 1.2.0
brain_version: ">=4.1.0"
entry_dir: .
description: QQ聊天应用
files:
  - __init__.py
  - runtime.py
  - manifest.yaml
  - README.md
  - config.example.json
```

### 为什么要单独有 `aur.yaml`

虽然 `manifest.yaml` 已经描述了应用能力，但它更偏“运行时声明”；`aur.yaml` 更偏“分发元数据”。

两者关注点不同：

- `manifest.yaml` 给平台和内核看
- `aur.yaml` 给安装器、打包器和分发链路看

## 安装流程建议

`aur install` 的推荐流程：

1. 读取 `.aur` 压缩包
2. 校验 `aur.yaml`
3. 校验应用目录至少包含 `manifest.yaml` 和 `__init__.py`
4. 校验 `app_key` 与目录结构是否一致
5. 解包到 `apps/<app_key>/`
6. 若 `apps/config.yaml` 中不存在该应用，则自动补一条默认配置
7. 若包中有 `config.example.json`，提示用户复制到对应 app-data 目录

建议默认行为：

- 目标目录已存在时拒绝覆盖
- 通过 `--force` 才允许替换
- 安装不会自动删除旧 app-data

## 卸载流程建议

`aur uninstall` 的推荐流程：

1. 删除 `apps/<app_key>/`
2. 从 `apps/config.yaml` 中移除对应条目
3. 保留 `data/app_data/...`
4. 若用户传 `--purge-data`，再一并删除对应 app-data

这样能避免误删用户积累的数据。

## 打包流程建议

`aur pack` 的推荐流程：

1. 扫描 `apps/<app_key>/`
2. 校验必须文件是否存在
3. 读取 `manifest.yaml`
4. 读取 `aur.yaml`
5. 输出到 `dist/<app_key>-<version>.aur`

建议打包时做这些校验：

- `manifest.package` 存在
- `README.md` 存在
- `config.example.json` 存在
- 能通过 import 解析到应用入口类

## 配置哲学

应用配置应继续分两层：

### `apps/config.yaml`

这是“平台视角”的应用表，负责：

- 应用是否启用
- 应用启动参数
- 应用是否参与当前运行实例

### `app-data/<package>/config.json`

这是“应用自身”的持久化配置，负责：

- 应用内部运行参数
- 可迁移到部署环境的默认配置
- 不污染系统级 `Config`

也就是说：

- 启动前由平台关心的参数，放 `apps/config.yaml`
- 启动后由应用自己解释的参数，放 `app-data/.../config.json`

## 应用目录约定

建议未来将每个应用目录都视作可打包单元，至少包含：

- `__init__.py`
- `runtime.py`
- `manifest.yaml`
- `README.md`
- `config.example.json`

这套结构已经适合目录扫描，也适合直接封装成 `.aur`。

## 与 `app.py` 的整合建议

当前 [app.py](file:///e:/AuroraBot/app.py) 已经具备：

- 构建 `ApplicationHost`
- 注册选定应用
- 调命令
- 发事件
- 跑 tick

建议后续改造顺序是：

1. 先把 `app.py` 改造成子命令结构
2. 再把文件名和帮助文案逐步迁移到 `aur`
3. 最后接入 `pack/install/uninstall`

也就是说，当前的 [app.py](file:///e:/AuroraBot/app.py) 不需要废弃，而是应该被视作 `aur` 的前身。

## 分阶段实施建议

### 第一阶段：CLI 收口

目标：

- 把现有 `app.py` 的平铺参数改成子命令结构
- 对外帮助文案统一使用 `aur`

产物：

- `list`
- `run`
- `command`
- `event`
- `tick`
- `config init`

### 第二阶段：包规范落地

目标：

- 确定 `aur.yaml`
- 明确 `.aur` 的目录与校验规则

产物：

- `.aur` v0.1 格式说明

### 第三阶段：本地包管理

目标：

- 完成 `pack/install/uninstall`

产物：

- 本地打包
- 本地安装
- 配置自动补全

### 第四阶段：体验增强

目标：

- 加 `--force`
- 加 `--purge-data`
- 加版本冲突处理
- 加校验和或签名

## 当前结论

后续应用工具链统一命名为 `aur` 是合理的，原因如下：

- 辨识度比 `app.py` 更强
- 既能表示“应用工具”，也能表示“应用包格式”
- 适合承载开发、安装、打包三类能力

而当前的 [app.py](file:///e:/AuroraBot/app.py) 最适合作为 `aur` 的过渡实现入口，后续逐步重构即可。
