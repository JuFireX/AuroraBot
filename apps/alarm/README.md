# Alarm App

`alarm` 是一个时序事件源应用，负责创建提醒，并在到点后向内核发出事件。

## 提供的命令

- `set_alarm`
  - 创建一个未来会触发的提醒。

## 发出的事件

- `alarm_reminder`
  - 普通提醒到点时发出。
- `diary_prompt`
  - 每日日记提醒到点时发出。

## app-data

应用自己的数据目录位于：

`data/app_data/im_polaris_alarm/`

常见文件：

- `alarms.json`
  - 提醒持久化数据。
- `config.json`
  - 应用自己的运行配置。

## 配置说明

可放入 `config.json` 的字段：

- `default_interval_seconds`
  - 默认提醒间隔，单位秒。
- `diary_time`
  - 每日日记提醒时间，格式 `HH:MM`。

可以直接复制同目录下的 `config.example.json` 到 app-data 目录中使用。
