---
title: 快速开始
description: 从环境准备到启动运行，快速把 AuroraBot 跑起来。
order: 2
---

# 快速开始

就一件事：用最短的路径把她叫醒，然后知道去哪儿看她活得好不好。

## 你要准备好

- Python `3.10+`
- `uv`
- Node.js `20+`（只在本地预览文档站时需要）

## 装依赖

```bash
uv sync
```

## 启动

```bash
uv run .\bot.py
```

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
