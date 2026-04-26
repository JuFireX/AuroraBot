from polaris.utils.Logger import get_logger

logger = get_logger("RestService")


async def sleep(agent_state: dict, args: dict):
    logger.info("Bot 决定进入较深的休眠状态...")
    agent_state["status"] = "sleeping"
    agent_state["energy"] = min(100, agent_state.get("energy", 100) + 12)
    agent_state["mood"] = "quiet"
    agent_state["social_drive"] = max(0, agent_state.get("social_drive", 0) - 8)


async def rest(agent_state: dict, args: dict):
    logger.info("Bot 决定靠岸休息一会儿...")
    agent_state["status"] = "resting"
    agent_state["energy"] = min(100, agent_state.get("energy", 100) + 6)
    agent_state["mood"] = "soft"
    agent_state["social_drive"] = max(0, agent_state.get("social_drive", 0) - 2)


async def idle(agent_state: dict, args: dict):
    logger.debug("Bot 决定神游一会儿，顺便留意想不想找人说话...")
    agent_state["status"] = "idle"
    agent_state["mood"] = "wandering"
    agent_state["social_drive"] = min(100, agent_state.get("social_drive", 0) + 5)
