# QQ App

`qq` 是一个消息收发应用, 负责接收 QQ 消息、维护会话目标, 并提供发送能力.

## 提供的命令

- `send_qq_message`
  - 向已知会话发送消息.
- `send_qq_private_message`
  - 向指定 QQ 用户发送私聊消息.
- `at_user_in_group`
  - 在群里 @ 某个用户并发送文本.

## 发出的事件

- `message.received`
  - 收到 QQ 消息后发出.

## app-data

应用自己的数据目录位于:

`data/app_data/im_polaris_qq/`

常见文件:

- `qq_events.json`
  - 收发消息事件记录.
- `session_targets.json`
  - 会话目标映射.

## 配置说明

当前这个应用没有 app-data 级配置项; 监听器开关属于启动参数, 应放在 `apps/config.yaml` 的对应应用条目下.

如果后续增加应用内部配置, 建议放在 `config.json` 中; 同目录下的 `config.example.json` 预留了这个入口.
