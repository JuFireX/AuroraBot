from litellm import completion
from polaris.config import Config
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.message import MessageSegment


@staticmethod
async def get_response(event: GroupMessageEvent | PrivateMessageEvent) -> str:
    response = completion(
        model=Config().MODEL,
        messages=[{"role": "user", "content": user_input + ", 回复不要超过50字."}],
    )
    return response.choices[0].message.content

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
    await group_msg.send(response.choices[0].message.content)

    # 方式 B：@发送者 + 文本
    # await group_msg.send(MessageSegment.at(user_id) + " 这是回复你的消息")

    # 方式 C：引用回复（最推荐，用户知道你在回哪条）
    # reply_seg = MessageSegment.reply(message_id)
    # await group_msg.send(reply_seg + response.choices[0].message.content)

    # 方式 D：调用 Bot API 直接发（更底层，可以指定群号）
    # await bot.send_group_msg(group_id=group_id, message="hello")
