from datetime import datetime
from polaris.utils.Logger import get_logger

logger = get_logger("TimeService")


async def check_time(agent_state: dict, args: dict):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Bot 查看了时间: 现在是 {now}")
    # 将查看到的时间存入状态或者直接返回给内部循环使用
    agent_state["last_checked_time"] = now
