---
title: 项目总览
description: 快速了解 AuroraBot 的定位、分层、运行方式与当前边界。
---

# 项目总览

AuroraBot 是一个面向本地运行场景的智能体实验项目。它不是单一聊天机器人，而是一套把应用接入、事件处理、计划生成与动作执行串起来的运行时骨架。

## 一句话理解

AuroraBot 的核心目标是：

> 让 `apps/*` 负责感知世界与执行动作，让 `kernel` 负责理解事件并编排下一步动作。

## 系统分层

| 层级       | 主要职责                                       | 关注点                     |
| ---------- | ---------------------------------------------- | -------------------------- |
| `apps`     | 感知外部输入、暴露原子命令、维护私有状态       | 接平台、接 SDK、做具体动作 |
| `platform` | 发现应用、注册命令、维护事件队列、调度生命周期 | 把应用跑起来               |
| `kernel`   | 消费事件、生成计划、展开动作、执行命令         | 决定下一步做什么           |

## 当前架构一眼图

```mermaid
flowchart TB
    subgraph ROW1[" "]
        direction LR
        EXT["外部输入"]
        APPS["Apps"]
        HOST["ApplicationHost"]
    end

    subgraph ROW2[" "]
        direction LR
        KERNEL["Plan / Expand / Execute"]
        CMD["命令调用"]
        RESULT["消息 / 提醒 / 持久化"]
    end

    EXT --> APPS --> HOST
    HOST -->|"事件"| KERNEL
    KERNEL --> CMD --> RESULT
    RESULT -.->|"反馈到环境"| EXT
```

## 当前已经具备的能力

- 应用宿主层已经可以自动发现并注册 `apps/*`
- 应用可以通过 `manifest.yaml` 声明命令能力
- 平台已经具备事件队列、命令调用和生命周期管理
- 内核已经具备 `plan -> expand -> execute` 的最小闭环
- 中间状态会落到 JSON 文件，便于调试与回放

## 这个项目适合做什么

- 试验多阶段 agent 的编排方式
- 试验事件驱动的应用接入模型
- 观察计划队列与动作队列的中间产物
- 逐步接入记忆、内容生成、LLM planner 等能力

## 当前边界与限制

- `ExpandAgent` 目前仍然是启发式展开，不是严格 planner
- 队列状态当前采用 JSON 文件持久化，偏调试形态
- 还没有正式的 `session router`
- 还没有完整的 `memory` 与 `content builder` 阶段
- 现阶段更像“可演进的骨架”，不是完成态产品

## 建议阅读顺序

1. [快速开始](./getting-started.html)
2. [系统架构总览](../architecture/system-overview.html)
3. [内核流水线](../architecture/kernel-pipeline.html)
4. [平台运行时](../architecture/platform-runtime.html)
5. [App 开发指南](../guide/app-development.html)
6. [AUR CLI 路线图](../roadmap/aur-cli.html)
