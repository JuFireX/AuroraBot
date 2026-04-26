from polaris.utils.Logger import get_logger


logger = get_logger("RestService")


async def sleep():
    logger.info(f"Bot 睡觉去了")


async def rest():
    logger.info("Bot 休息了一会儿")


async def idle():
    logger.debug("Bot 发会儿呆")
