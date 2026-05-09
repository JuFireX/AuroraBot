# Diary App

`diary` 是一个结构化日记写入应用，负责把总结、互动和反思保存到本地，并向内核回报写入结果。

## 提供的命令

- `write_diary`
  - 写入一条结构化日记记录。

## 发出的事件

- `diary.written`
  - 日记成功写入后发出。

## app-data

应用自己的数据目录位于：

`data/app_data/im_polaris_diary/`

常见文件：

- `diaries.json`
  - 日记持久化数据。

## 配置说明

当前这个应用没有额外的 app-data 级配置项。

如果后续增加配置，建议继续放在 `config.json` 中；同目录下的 `config.example.json` 预留了这个入口。
