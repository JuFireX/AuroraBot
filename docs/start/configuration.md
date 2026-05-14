---
title: 配置说明
description: AuroraBot 的环境变量、平台配置与应用级配置说明。
order: 3
---

# 配置说明

AuroraBot 采用两层配置分离的策略：平台管"开不开、怎么启"，App 管"我的参数是什么意思"。

> ⚠️ 配置体系仍在早期阶段，部分项目尚未稳定。当前文档反映的是现阶段可用能力，后续会随框架演进而更新。

## 环境变量

通过项目根目录的 `.env` 文件设置：

| 变量       | 说明     | 可选值                                                |
| ---------- | -------- | ----------------------------------------------------- |
| `RUN_MODE` | 启动模式 | `app`（仅应用层）/ `agent`（仅内核） / `prod`（全量） |

更多环境变量（如 LLM API Key、数据库连接等）将在后续版本中逐步暴露。

## 平台级配置

### `apps/config.yaml`

平台视角的配置，决定哪些 App 被启用以及如何启动：

```yaml
# apps/config.yaml（示例结构）
apps:
  im.polaris.qq:
    enabled: true
  im.polaris.alarm:
    enabled: true
  im.polaris.diary:
    enabled: false
```

平台只关心"开没开、怎么启"，不关心 App 内部的业务参数。

## App 级配置

### `apps/<app>/config.example.json`

每个 App 自带一份配置示例，描述自身需要的参数。实际运行时，App 从 `data/app_data/<package>/config.json` 读取配置。

示例：

```json
{
  "reminder_interval_minutes": 30,
  "timezone": "Asia/Shanghai"
}
```

### 配置职责边界

| 配置位置                              | 管什么                            |
| ------------------------------------- | --------------------------------- |
| `apps/config.yaml`                    | 平台视角：这个 App 开不开、怎么启 |
| `data/app_data/<package>/config.json` | App 视角：我怎么理解我的参数      |

## 目录结构

```
AuroraBot/
  .env                    # 环境变量
  .env.dev / .env.prod    # 按环境拆分（可选）
  apps/
    config.yaml           # 平台级：App 启停
    <app>/
      config.example.json # App 级：参数模板
  data/
    app_data/
      <package>/
        config.json       # App 级：运行时配置
```

## 当前限制

- 配置热加载尚未支持，修改后需重启
- 配置校验尚未集成，错误配置可能导致静默失败
- `.env` 暴露的变量还很少，后续会随功能补全

## 怎么跑

通过环境变量 `RUN_MODE` 告诉她想以什么身份起床：

| 模式    | 干什么               |
| ------- | -------------------- |
| `app`   | 只跑身体（应用循环） |
| `agent` | 只跑脑子（内核循环） |
| `prod`  | 身体和脑子一起跑     |

## 本地预览文档站

```bash
cd docs
npm install
npm run docs:dev
```

## 目录速览

```text
AuroraBot/
  apps/                  # 应用层（她的感官）
  docs/                  # 你现在在看的文档站
  src/
    brain/
      agents/            # 内核内部的 stage agent 们
      kernel/            # 内核编排层
    platform/            # 应用宿主层
    main.py              # 启动入口
    config.py            # 全局配置
  tests/                 # 测试
  pyproject.toml         # Python 依赖与工具配置
```

## 跑起来后看哪里

想看她活没活着、在干什么，盯这几个地方：

| 路径                       | 里面放了什么      |
| -------------------------- | ----------------- |
| `data/app_data/*`          | 各 app 的私有数据 |
| `data/kernel/plans.json`   | 内核计划队列      |
| `data/kernel/actions.json` | 内核动作队列      |
| `data/queues/events.json`  | 宿主事件队列快照  |
| `logs/aurora.log`          | 运行日志          |

## 接下来读哪个

- 想搞清楚她长什么样：读 [系统架构总览](../architecture/system-overview.html)
- 想看她脑子怎么转：读 [内核运行时](../architecture/kernel-runtime.html)
- 想写个新 app：读 [App 开发指南](../develop/app-development.html)
