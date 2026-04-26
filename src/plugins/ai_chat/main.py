from nonebot import on_message, on_command
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    PrivateMessageEvent,
    MessageSegment,
    Message,
)
from nonebot.params import CommandArg
from openai.types.responses import response
from .config import Config
from litellm import completion


# ============================================================
# 1. 群聊消息处理器（监听所有群消息）
# priority=10: 优先级，数字越小越早处理
# block=False: 处理完后继续传给其他插件（True=阻断）
# ============================================================
group_msg = on_message(rule=to_me(), priority=10, block=False)


@group_msg.handle()
async def handle_group(bot: Bot, event: GroupMessageEvent):
    # -------- 基础信息提取 --------
    user_id = event.user_id  # 发送者 QQ
    group_id = event.group_id  # 群号
    message_id = event.message_id  # 消息 ID（用于引用回复）
    raw_msg = event.raw_message  # 原始消息字符串（含 CQ 码）
    plain_text = event.get_plaintext()  # 纯文本内容（去掉 CQ 码）

    # ====== 【在这里插入你的 AI 调用】 ======
    user_input = plain_text.strip()
    response = completion(
        model=Config().MODEL,
        messages=[{"role": "user", "content": user_input + ", 回复不要超过50字."}],
    )

    # =======================================

    # 下面演示几种发送方式（选一个用即可）：

    # 方式 A：纯文本回复
    print(response)
    await group_msg.send(response.choices[0].message.content)

    # 方式 B：@发送者 + 文本
    # await group_msg.send(MessageSegment.at(user_id) + " 这是回复你的消息")

    # 方式 C：引用回复（最推荐，用户知道你在回哪条）
    # reply_seg = MessageSegment.reply(message_id)
    # await group_msg.send(reply_seg + response.choices[0].message.content)

    # 方式 D：调用 Bot API 直接发（更底层，可以指定群号）
    # await bot.send_group_msg(group_id=group_id, message="hello")


# ============================================================
# 2. 私聊消息处理器（只响应发给机器人的私聊）
# rule=to_me() 表示只处理"发给机器人"的消息
# ============================================================
private_msg = on_message(rule=to_me(), priority=5, block=False)


@private_msg.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent):
    user_id = event.user_id
    plain_text = event.get_plaintext()

    # ====== 【在这里插入你的 AI 调用】 ======
    user_input = plain_text.strip()
    response = completion(
        model=Config().MODEL,
        messages=[{"role": "user", "content": user_input + ", 回复不要超过50字."}],
    )
    # =======================================

    await private_msg.send(response.choices[0].message.content)


# ============================================================
# 3. 命令处理器（可选，演示如何解析参数）
# 用法：在群里发 "/hello 张三" 或 "/你好 张三"
# ============================================================
hello_cmd = on_command(
    "hello",
    aliases={"你好", "hi"},
    rule=to_me(),  # 需要 @ 机器人才触发
    priority=5,
    block=True,  # 阻断，不再传给其他插件
)


@hello_cmd.handle()
async def handle_hello(
    bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()
):
    # 提取命令后面的参数，如 "/hello 张三" -> "张三"
    name = args.extract_plain_text().strip() or "陌生人"

    # 组合消息：@用户 + 文本
    msg = MessageSegment.at(event.user_id) + f" 你好呀，{name}！"

    # finish = send + 结束本次会话
    await hello_cmd.finish(msg)
