import asyncio
from polaris.utils.Logger import get_logger
from polaris.config import Config

from polaris.brain.action.action import ACTION_ROUTER

logger = get_logger("BrainCore")
ATTENTIONS = Config.POLARIS_BRAIN / "core" / "attentions.json"
PLANS = Config.POLARIS_BRAIN / "core" / "plans.json"
ACTIONS = ACTION_ROUTER


class BrainLoop:
    def __init__(self):
        self.heart_beat = 5
        self.awake = False
        # TODO 使用注意力池文件存储各种结构化状态和注意事件(比如自己的精神状态啊, 事情解决的状态啊各种状态)

    async def start(self):
        self.awake = True
        while self.awake:
            try:
                # 规划阶段
                await self.plan()
                # 执行阶段
                await self.act()
                # 更新阶段
                await self.update()
            except Exception as e:
                logger.error(f"循环发生异常: {e}")
            await asyncio.sleep(self.heart_beat)

    def stop(self):
        self.awake = False

    async def plan(self):
        """规划阶段"""
        # TODO 根据当前注意力池, 更新计划池(每一个计划对象都有一个权重, 权重越高, 就越优先执行, 消费的精力也越多)
        pass

    async def act(self):
        """执行阶段"""
        # TODO 根据计划池和计划权重, 选择一部分执行(因为总精力有限), 并更新注意力池
        pass

    async def update(self):
        """更新阶段"""
        # TODO 对齐外部事件, 更新注意力池
        pass


# 全局单例
brain_instance = BrainLoop()
