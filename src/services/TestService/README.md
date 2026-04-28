# NapCatQQ + NoneBot2 QQ 事件收发速查

本清单基于你当前项目依赖：

- `nonebot2 >= 2.5.0`
- `nonebot-adapter-onebot >= 2.4.6`
- 协议：`OneBot V11`（NapCat 作为实现端）

目标：把“接收 QQ 事件 + 发送 QQ 事件/动作（含引用回复、戳一戳）”放到一份文档里，开箱即用。

---

## 1. 接收事件（推荐入口）

### 1.1 四类入口

```python
from nonebot import on_message, on_notice, on_request, on_metaevent

msg_matcher = on_message(priority=5, block=False)      # 消息事件
notice_matcher = on_notice(priority=5, block=False)    # 通知事件（撤回、群成员变化、戳一戳等）
request_matcher = on_request(priority=5, block=False)  # 请求事件（加好友、加群）
meta_matcher = on_metaevent(priority=5, block=False)   # 元事件（心跳、生命周期）
```

### 1.2 常用事件类型（OneBot V11）

```python
from nonebot.adapters.onebot.v11 import (
    MessageEvent,
    PrivateMessageEvent,
    GroupMessageEvent,
    NoticeEvent,
    NotifyEvent,
    PokeNotifyEvent,
    GroupRecallNoticeEvent,
    FriendRecallNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupBanNoticeEvent,
    GroupAdminNoticeEvent,
    GroupUploadNoticeEvent,
    HonorNotifyEvent,
    LuckyKingNotifyEvent,
    RequestEvent,
    FriendRequestEvent,
    GroupRequestEvent,
    MetaEvent,
    HeartbeatMetaEvent,
    LifecycleMetaEvent,
)
```

### 1.3 典型接收写法

```python
from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, PokeNotifyEvent

msg = on_message(priority=5, block=False)
notice = on_notice(priority=5, block=False)

@msg.handle()
async def _(bot: Bot, event: MessageEvent):
    # 基本字段
    text = str(event.get_message())
    user_id = event.user_id
    session_id = event.get_session_id()
    is_group = isinstance(event, GroupMessageEvent)

    # 忽略自己发的消息（防自触发）
    if str(user_id) == str(bot.self_id):
        return

@notice.handle()
async def _(bot: Bot, event):
    if isinstance(event, PokeNotifyEvent):
        # 收到戳一戳
        target = event.target_id
        sender = event.user_id
```

---

## 2. 发送消息（文本/引用/艾特/多段）

### 2.1 推荐：`bot.send(event=..., message=...)`

优点：自动按事件上下文发送到正确会话（私聊或群聊）。

```python
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

async def reply_simple(bot: Bot, event):
    await bot.send(event=event, message="收到")

async def reply_quote(bot: Bot, event):
    # 引用回复（回复某条消息）
    # event.message_id 即当前触发消息的ID
    msg = MessageSegment.reply(event.message_id) + "这条我看到了"
    await bot.send(event=event, message=msg)

async def reply_at_quote(bot: Bot, event):
    # 群里常见：引用 + @发送者 + 文本
    msg = (
        MessageSegment.reply(event.message_id)
        + MessageSegment.at(event.user_id)
        + " 你好，这里是回复内容"
    )
    await bot.send(event=event, message=msg)
```

### 2.2 明确指定会话发送：`call_api`

`Bot` 在当前版本主要暴露 `call_api`，可直接调用 OneBot API。

```python
async def send_private(bot, user_id: int, text: str):
    await bot.call_api("send_private_msg", user_id=user_id, message=text)

async def send_group(bot, group_id: int, text: str):
    await bot.call_api("send_group_msg", group_id=group_id, message=text)

async def send_auto(bot, user_id: int, group_id: int | None, text: str):
    # message_type: "private" / "group"
    await bot.call_api(
        "send_msg",
        message_type="group" if group_id else "private",
        group_id=group_id,
        user_id=user_id,
        message=text,
    )
```

---

## 3. 戳一戳、撤回、转发等动作

### 3.1 戳一戳（推荐：消息段）

```python
from nonebot.adapters.onebot.v11 import MessageSegment

async def poke_user(bot, event, qq: int):
    # 通过 poke 消息段触发戳一戳（NapCat 常用）
    await bot.send(event=event, message=MessageSegment.poke(qq))
```

### 3.2 撤回消息

```python
async def recall_msg(bot, message_id: int):
    await bot.call_api("delete_msg", message_id=message_id)
```

### 3.3 合并转发（群/私聊）

```python
from nonebot.adapters.onebot.v11 import MessageSegment

async def forward_demo(bot, event):
    nodes = [
        MessageSegment.node_custom(user_id=123456, nickname="A", content="第一条"),
        MessageSegment.node_custom(user_id=123456, nickname="A", content="第二条"),
    ]
    # 发送到当前会话
    await bot.send(event=event, message=MessageSegment.forward(nodes))
```

---

## 4. `MessageSegment` 常用构造（发消息时拼装）

你当前版本可用的主要构造方法：

- `MessageSegment.text(...)`
- `MessageSegment.reply(message_id)`（引用）
- `MessageSegment.at(user_id)`（@某人）
- `MessageSegment.poke(user_id)`（戳一戳）
- `MessageSegment.face(id_)`
- `MessageSegment.image(...)`
- `MessageSegment.record(...)`
- `MessageSegment.video(...)`
- `MessageSegment.share(...)`
- `MessageSegment.music(...)`, `music_custom(...)`
- `MessageSegment.xml(...)`, `json(...)`
- `MessageSegment.node(...)`, `node_custom(...)`, `forward(...)`
- `MessageSegment.dice()`, `rps()`, `shake()`, `location(...)`, `contact_user(...)`, `contact_group(...)`

拼接方式：

```python
msg = (
    MessageSegment.reply(event.message_id)
    + MessageSegment.at(event.user_id)
    + " 这是一条带引用和艾特的消息"
)
await bot.send(event=event, message=msg)
```

---

## 5. 请求与通知的处理模板

### 5.1 处理加好友请求

```python
from nonebot import on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent

req = on_request(priority=5, block=False)

@req.handle()
async def _(bot: Bot, event: FriendRequestEvent):
    # approve=True 通过，False 拒绝
    await bot.call_api(
        "set_friend_add_request",
        flag=event.flag,
        approve=True,
        remark="你好",
    )
```

### 5.2 处理加群请求/邀请

```python
from nonebot.adapters.onebot.v11 import GroupRequestEvent

@req.handle()
async def _(bot: Bot, event: GroupRequestEvent):
    await bot.call_api(
        "set_group_add_request",
        flag=event.flag,
        sub_type=event.sub_type,  # "add" / "invite"
        approve=True,
        reason="欢迎",
    )
```

---

## 6. OneBot V11 常用 API 名称（可直接 `call_api`）

### 6.1 消息相关

- `send_private_msg`
- `send_group_msg`
- `send_msg`
- `delete_msg`
- `get_msg`
- `get_forward_msg`

### 6.2 群管理

- `set_group_kick`
- `set_group_ban`
- `set_group_anonymous_ban`
- `set_group_whole_ban`
- `set_group_admin`
- `set_group_anonymous`
- `set_group_card`
- `set_group_name`
- `set_group_leave`
- `set_group_special_title`

### 6.3 请求处理

- `set_friend_add_request`
- `set_group_add_request`

### 6.4 信息获取

- `get_login_info`
- `get_stranger_info`
- `get_friend_list`
- `get_group_info`
- `get_group_list`
- `get_group_member_info`
- `get_group_member_list`
- `get_group_honor_info`

### 6.5 运行状态

- `get_status`
- `get_version_info`
- `set_restart`
- `clean_cache`

---

## 7. 你项目里现成可参考的位置

- 接收消息并入队：`polaris/services/QQService/core.py` 的 `handle_message`
- 自动回复发送：`polaris/services/QQService/core.py` 的 `execute_qq_send_msg`

---

## 8. 最小可运行示例（接收 + 引用回复 + 戳一戳）

```python
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

matcher = on_message(priority=5, block=False)

@matcher.handle()
async def _(bot: Bot, event: MessageEvent):
    if str(event.user_id) == str(bot.self_id):
        return

    text = str(event.get_message()).strip()

    if text == "ping":
        # 引用回复
        await bot.send(
            event=event,
            message=MessageSegment.reply(event.message_id) + "pong",
        )
        return

    if text == "戳我":
        # 戳一戳
        await bot.send(event=event, message=MessageSegment.poke(event.user_id))
        return

    await bot.send(event=event, message="收到")
```

---

如果你愿意，我可以下一步再给你补一份“NapCat 扩展 API（官方扩展字段/动作）”专门表，把 OneBot 标准和 NapCat 特有能力分开，后面查起来更快。
