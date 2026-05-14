---
title: 快速开始
description: 从环境准备到启动运行，快速把 AuroraBot 跑起来。
order: 2
---

# 快速开始

从环境准备到启动运行，快速把 AuroraBot 跑起来。

::: info
此版本暂时只支持从源码运行. 后期会提供一键包安装.
:::

## 前期准备

- Python `3.10+`
- _当你需要本地查看文档站时:_ Node.js `20+`

## 克隆仓库

```bash
git clone https://github.com/JuFireX/AuroraBot.git
cd AuroraBot
```

::: tip
或者你可以通过 [Releases](https://github.com/JuFireX/AuroraBot/releases) 下载最新稳定版本的源码压缩包, 并解压到 `AuroraBot` 目录下.
:::

## 安装依赖

我们推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖:

```bash
pip install uv
uv sync
```

## 配置密钥

```bash
cp .env.example .env
```

::: tip
在 `.env` 中配置你的密钥:

```
# 适配器配置
ONEBOT_ACCESS_TOKEN=

# 模型配置
DEEPSEEK_URL_BASE=https://api.deepseek.com #默认为Deepseek
DEEPSEEK_API_KEY=
LITELLM_MODEL=deepseek/deepseek-v4-flash #默认为Deepseek

# 记忆配置
MEM0_API_KEY=
```

更多配置说明见 [配置说明](./configuration)
:::

## 启动Bot

```bash
uv run bot.py
```

此时你的Bot将会以默认人格`小光`启动，但是你还没有手段来与她互动. 你需要启动你的OneBot适配器，例如 [NapCat](https://github.com/NapNeko/NapCatQQ), 然后就可以试着向她发送消息了!

::: tip
NapCat 的启动方式参见 [NapCat 官方文档](https://napneko.github.io/guide/boot/Shell)
:::

::: info
框架第一适配 NapCat 适配器. 其他适配器将在后续版本中逐渐支持.
:::
