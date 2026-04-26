import nonebot
from datetime import datetime
from polaris.utils.Logger import get_logger
from polaris.core.memory import memory_service
from polaris.core.language import language_service

logger = get_logger("AgentActions")

async def reply_qq(agent_state: dict, args: dict):
    """
    发送 QQ 消息的动作。
    参数需要：bot_id, 目标(group_id 或 user_id), trigger_event (触发此回复的事件文本)
    """
    bot_id = args.get("bot_id")
    group_id = args.get("group_id")
    target_id = args.get("target_id") # user_id
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
        await memory_service.add_memory(
            role="self", 
            content=final_reply, 
            metadata={"group_id": group_id, "user_id": target_id}
        )
        
    except KeyError:
        logger.warning(f"未找到 Bot 实例 {bot_id}，可能尚未连接。")
    except Exception as e:
        logger.error(f"reply_qq 执行失败: {e}")

async def check_time(agent_state: dict, args: dict):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"智能体看了一眼时间: {now}")
    agent_state["last_checked_time"] = now
    await memory_service.add_memory("self", f"(我看了一眼时间，现在是 {now})")

async def sleep(agent_state: dict, args: dict):
    duration_minutes = args.get("duration_minutes", 60)
    agent_state["status"] = "sleeping"
    # 在未来的 Tick 中，如果 status 是 sleeping，可以决定不予理会或直接跳过
    logger.info(f"智能体陷入沉睡，预计 {duration_minutes} 分钟。")
    await memory_service.add_memory("self", f"(意识逐渐模糊，我闭上眼睛沉睡...)")

async def rest(agent_state: dict, args: dict):
    agent_state["status"] = "resting"
    logger.info("智能体决定小憩片刻发发呆。")
    await memory_service.add_memory("self", f"(周遭的喧嚣让我疲惫，我决定稍作休息，放空一下...)")

async def idle(agent_state: dict, args: dict):
    # 发呆，什么都不做
    logger.debug("智能体处于发呆状态。")
    pass

# 服务路由表
ACTION_ROUTER = {
    "reply_qq": reply_qq,
    "check_time": check_time,
    "sleep": sleep,
    "rest": rest,
    "idle": idle
}
