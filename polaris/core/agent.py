import asyncio
import json
import random
from polaris.utils.Logger import get_logger
from polaris.core.memory import memory_service
from polaris.services.model.ModelService import get_json_response
from polaris.services.agent_actions import ACTION_ROUTER

logger = get_logger("AgentCore")

class AgentLoop:
    def __init__(self):
        self.attention_queue = asyncio.Queue()
        self.state = {
            "status": "awake",  # awake, sleeping, resting
            "energy": 100,      # 精力值
            "mood": "calm",     # 情绪
        }
        self.tick_rate = 5      # 循环心跳间隔(秒)
        self._running = False
        
    async def start(self):
        self._running = True
        logger.info("智能体心智循环已启动。")
        while self._running:
            try:
                await self.update_state()
                plan = await self.plan()
                if plan:
                    await self.action(plan)
            except Exception as e:
                logger.error(f"心智循环发生异常: {e}")
            await asyncio.sleep(self.tick_rate)
            
    def stop(self):
        self._running = False
        logger.info("智能体心智循环已停止。")
        
    async def update_state(self):
        """
        感知与状态更新阶段。
        从队列获取新事件，如果是睡觉状态则可能忽略。
        """
        events = []
        while not self.attention_queue.empty():
            events.append(await self.attention_queue.get())
            
        if not events:
            return
            
        # 简单模拟状态变化：收到大量消息消耗精力
        if len(events) > 3:
            self.state["energy"] = max(0, self.state["energy"] - 10)
            
        # 将事件写入短期记忆
        for event in events:
            if event.get("type") == "qq_msg":
                content = event.get("content", "")
                group_id = event.get("group_id")
                user_id = event.get("user_id")
                sender = f"群 {group_id} 的成员 {user_id}" if group_id else f"用户 {user_id}"
                mem_content = f"[{sender}] 对我说：{content}"
                await memory_service.add_memory("user", mem_content, metadata=event)
                
        # 累积到当前待处理事件池中
        if "recent_events" not in self.state:
            self.state["recent_events"] = []
        self.state["recent_events"].extend(events)
        
    async def plan(self) -> dict | None:
        """
        规划阶段。大模型根据当前 State 决定下一步行动。
        """
        events = self.state.get("recent_events", [])
        
        # 状态机简易恢复逻辑
        if self.state["status"] in ["sleeping", "resting"]:
            self.state["recent_events"] = [] # 沉睡时错过消息
            if random.random() < 0.1: # 10%概率醒来
                self.state["status"] = "awake"
                self.state["energy"] = 100
                await memory_service.add_memory("self", "(我从沉睡中苏醒，感到精力恢复了...)")
                logger.info("智能体已苏醒。")
            return None

        if not events and self.state["status"] == "awake":
            if random.random() < 0.05: # 5%概率主动发呆休息
                return {"action": "rest", "args": {}, "thought": "周围很安静，稍微休息一下。"}
            return None

        system_prompt = (
            "你是一个在赛博空间中的游荡者（智能体），正在进行思考与计划。\n"
            f"你当前的内部状态：{json.dumps(self.state, ensure_ascii=False)}\n"
            "你需要根据注意到的事件，决定唯一的一个接下来的动作。\n"
            "你可以选择调用的 action 只有以下几种：\n"
            "1. `reply_qq`: 回复消息。args必须包含 `bot_id`(机器人ID), `group_id`(如果有), `target_id`(发件人ID), `trigger_event`(对方说的话)。\n"
            "2. `sleep`: 睡觉，接下来会忽略消息。args可空。\n"
            "3. `rest`: 小憩。args可空。\n"
            "4. `check_time`: 查看时间。args可空。\n"
            "5. `idle`: 发呆，忽略当前这些事件。args可空。\n\n"
            "请严格以纯 JSON 格式输出，必须包含以下三个字段：\n"
            "- `thought`: 你的内心独白（意识流风格，例如“这消息太吵了，我想闭上眼”）\n"
            "- `action`: 上述动作名称之一\n"
            "- `args`: 动作所需参数字典\n"
        )
        
        # 提取待处理事件供决策
        event_descriptions = []
        for e in events:
            if e.get("type") == "qq_msg":
                content = e.get("content", "")
                group_id = e.get("group_id", "")
                user_id = e.get("user_id", "")
                bot_id = e.get("bot_id", "")
                desc = f"QQ消息 (发件人:{user_id}, 群:{group_id}, 机器人号:{bot_id}) -> {content}"
                event_descriptions.append(desc)

        user_prompt = f"你刚刚注意到了这些事情：\n" + "\n".join(event_descriptions) + "\n你决定接下来做什么？"
        
        logger.debug(f"智能体开始思考，注意力池中有 {len(events)} 件新事件...")
        plan_json = await get_json_response(system_prompt, user_prompt)
        logger.info(f"[Plan 结果] {plan_json}")
        
        # 决策完毕，清空当前注意力池
        self.state["recent_events"] = []
        return plan_json
        
    async def action(self, plan: dict):
        """
        执行阶段。路由调用具体服务。
        """
        action_name = plan.get("action", "idle")
        args = plan.get("args", {})
        thought = plan.get("thought", "")
        
        if thought:
            await memory_service.add_memory("self", f"(思考: {thought})")
            
        action_func = ACTION_ROUTER.get(action_name)
        if action_func:
            logger.info(f"执行动作: {action_name}")
            await action_func(self.state, args)
        else:
            logger.warning(f"未知动作: {action_name}，自动转为 idle")
            await ACTION_ROUTER["idle"](self.state, args)

# 全局单例
agent_instance = AgentLoop()
