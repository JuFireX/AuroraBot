---
title: 快速开始
description: 从环境准备到启动运行，快速把 AuroraBot 跑起来。
---

# 快速开始

这一页聚焦一件事：用最短路径把项目跑起来，并知道运行后该去哪里看状态。

## 环境准备

- Python `3.10+`
- `uv`
- Node.js `20+`

如果你只运行项目本体，前两项即可；如果你要本地预览文档站，则还需要 Node.js。

## 安装项目依赖

```bash
uv sync
```

## 启动项目

```bash
uv run .\bot.py
```

## 常见运行模式

通过环境变量 `RUN_MODE` 控制运行方式：

| 模式    | 含义                       |
| ------- | -------------------------- |
| `app`   | 只启动应用循环             |
| `agent` | 只启动内核循环             |
| `prod`  | 同时启动应用循环和内核循环 |

## 文档站本地预览

```bash
cd docs
npm install
npm run docs:dev
```

## 目录速览

```text
AuroraBot/
  apps/                  # 应用层
  docs/                  # 文档站
  src/
    brain/
      agents/            # 内核内部 stage agents
      kernel/            # 内核编排层
    platform/            # 应用宿主层
    main.py              # 启动入口
    config.py            # 全局配置
  tests/                 # 测试
  pyproject.toml         # Python 依赖与工具配置
```

## 运行后重点关注哪里

运行时最值得观察的通常是这些位置：

| 路径                       | 用途              |
| -------------------------- | ----------------- |
| `data/app_data/*`          | 各 app 的私有数据 |
| `data/kernel/plans.json`   | 内核计划队列      |
| `data/kernel/actions.json` | 内核动作队列      |
| `data/queues/events.json`  | 宿主事件队列快照  |
| `logs/aurora.log`          | 运行日志          |

## 推荐的阅读下一步

- 想看整体边界：读 [系统架构总览](../architecture/system-overview.html)
- 想看内核流水线：读 [内核流水线](../architecture/kernel-pipeline.html)
- 想写新应用：读 [App 开发指南](../guide/app-development.html)
