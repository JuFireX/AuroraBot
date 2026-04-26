import nonebot
from polaris.utils.Logger import get_logger
from polaris.brain.memory.memory import memory_service
from polaris.brain.language.language import language_service

logger = get_logger("QQMsgService")


async def reply_qq(agent_state: dict, args: dict):
    """
    发送 QQ 消息的动作。
    参数需要：bot_id, 目标(group_id 或 user_id), trigger_event (触发此回复的事件文本)
    """
    bot_id = args.get("bot_id")
    group_id = args.get("group_id")
    target_id = args.get("target_id")  # user_id
    trigger_event = args.get("trigger_event")

    if not bot_id or not trigger_event:
        logger.warning(f"reply_qq 参数不足: {args}")
        return

    try:
        bot = nonebot.get_bot(bot_id)

        # 1. 唤起回忆上下文
        context = await memory_service.recall(limit=15)

        # 2. 组织语言（灵魂碰撞）
        final_reply = await language_service.organize_reply(context, trigger_event)

        # 3. 实际发送
        if group_id:
            await bot.send_group_msg(group_id=group_id, message=final_reply)
            logger.info(f"群 {group_id} 回复: {final_reply}")
        elif target_id:
            await bot.send_private_msg(user_id=target_id, message=final_reply)
            logger.info(f"私聊 {target_id} 回复: {final_reply}")
        else:
            logger.warning("未指定 target_id 或 group_id")
            return

        # 4. 自身发言刻入记忆
        await memory_service.record(
            role="self",
            content=final_reply,
            metadata={"group_id": group_id, "user_id": target_id},
        )

    except KeyError:
        logger.warning(f"未找到 Bot 实例 {bot_id}，可能尚未连接。")
    except Exception as e:
        logger.error(f"reply_qq 执行失败: {e}")
