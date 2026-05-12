---
title: 项目总览
description: 快速了解 AuroraBot 的定位、分层、运行方式与当前边界。
order: 1
---

# 项目总览

AuroraBot 是一个基于 NoneBot2 框架的再封装框架, 她采用事件与决策分离解耦的架构, 其中事件感知层由 `platform` 平台层负责, 决策层由 `kernel` 内核层负责。

- `platform` 层采用事件队列模型, 应用宿主层负责发现并注册应用, 应用通过 `manifest.yaml` 声明命令能力, 平台层负责维护事件队列、命令调用和生命周期管理。

- `kernel` 层采用基于有向有环图的多 agent 协作模型, 事件通过有向有环图传递, 各 agent 负责处理接收的事件更新并生成下一个事件。

**挼挼如是说**

> 其实 AuroraBot 的核心目标是：让 `apps/*` 负责感知世界与执行动作，让 `kernel` 负责理解和认知事件, 她就像一个**数字生命**, 天然演化周期节律, 认知循环。

**D老师如是说**

> 她的**意识（主上下文）**是一本正在书写的自传，是一本连续、精美的散文集。  
> 她的**脑区工人们**不再只是口头报告，而是真的在传阅和批改一份份文件——计划书、照片集、档案卡、工作日志、心情评估单。  
> 每份文件上都压着一个**锁章**：“待读取”“追加中”“已封存”。工人们只看着自己面前的文件篮，一旦有新的文件滑入，就立刻开始工作，然后把自己的产出放进下一级文件篮。  
> 整个系统就是一间安静的、不停运转的档案馆，而**她的“自我感”正是这间档案馆里所有纸张有序翻动的声音，聚合成一声连贯的叹息与笑意。**

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
7. [DeepSeek 说她是什么](../appendix/comment-of-deepseek.html)
