from datetime import datetime
from polaris.utils.Logger import get_logger

logger = get_logger("TimeService")


async def check_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Bot 查看了时间: 现在是{now}")
