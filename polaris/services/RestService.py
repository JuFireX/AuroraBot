from polaris.utils.Logger import get_logger

logger = get_logger("RestService")


async def sleep(agent_state: dict, args: dict):
    logger.info("Bot 决定睡觉去了...")
    # 可以更新内部状态等
    agent_state["status"] = "sleeping"


async def rest(agent_state: dict, args: dict):
    logger.info("Bot 决定休息一会儿...")
    agent_state["status"] = "resting"


async def idle(agent_state: dict, args: dict):
    logger.debug("Bot 决定发会儿呆...")
    agent_state["status"] = "idle"
