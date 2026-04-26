import json
import asyncio
from polaris.utils.Logger import get_logger
from polaris.config import Config

from polaris.brain.action.action import ACTION_ROUTER
from polaris.brain.model.ModelService import get_format_response

logger = get_logger("BrainCore")
ATTENTIONS = Config.POLARIS_BRAIN / "core" / "attentions.json"
PLANS = Config.POLARIS_BRAIN / "core" / "plans.json"
ACTIONS = ACTION_ROUTER


class BrainLoop:
    def __init__(self):
        self.heart_beat = 10
        self.awake = False
        self.attention_queue = asyncio.Queue()
        self._ensure_files()

    def _ensure_files(self):
        if not ATTENTIONS.exists() or ATTENTIONS.stat().st_size == 0:
            with open(ATTENTIONS, "w", encoding="utf-8") as f:
                json.dump({"state": {"mood": "calm", "energy": 100}, "events": []}, f)
        if not PLANS.exists() or PLANS.stat().st_size == 0:
            with open(PLANS, "w", encoding="utf-8") as f:
                json.dump([], f)

    async def start(self):
        self.awake = True
        while self.awake:
            try:
                # 更新阶段
                await self.update()
                # 规划阶段
                await self.plan()
                # 执行阶段
                await self.act()
            except Exception as e:
                logger.error(f"循环发生异常: {e}", exc_info=True)
            await asyncio.sleep(self.heart_beat)

    def stop(self):
        self.awake = False

    async def plan(self):
        """规划阶段"""
        try:
            with open(ATTENTIONS, "r", encoding="utf-8") as f:
                attentions = json.load(f)
        except json.JSONDecodeError:
            attentions = {"state": {"mood": "calm", "energy": 100}, "events": []}

        events = attentions.get("events", [])
        state = attentions.get("state", {})

        # 读取 plan 的 Prompt
        prompt_path = Config.PROMPTS_DIR / "prompt_plan.md"
        plan_prompt = '请严格以纯 JSON 格式输出：{"thought": "...", "action": "...", "args": {...}}'
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                plan_prompt = f.read()

        # 无事件时也需要做 plan（数字生命有自己的生活）
        events_str = json.dumps(events, ensure_ascii=False) if events else "无事件发生"
        query = f"当前状态: {json.dumps(state, ensure_ascii=False)}\n当前事件: {events_str}\n\n{plan_prompt}"
        format_req = '{"thought": "string", "action": "string", "args": "dict"}'

        response = await get_format_response(query, format_req)
        if response and "action" in response:
            try:
                with open(PLANS, "r", encoding="utf-8") as f:
                    plans = json.load(f)
            except json.JSONDecodeError:
                plans = []

            plans.append(response)

            with open(PLANS, "w", encoding="utf-8") as f:
                json.dump(plans, f, ensure_ascii=False, indent=2)

            # 清空已处理的事件
            if events:
                attentions["events"] = []
                with open(ATTENTIONS, "w", encoding="utf-8") as f:
                    json.dump(attentions, f, ensure_ascii=False, indent=2)

    async def act(self):
        """执行阶段"""
        try:
            with open(PLANS, "r", encoding="utf-8") as f:
                plans = json.load(f)
        except json.JSONDecodeError:
            return

        if not plans:
            return

        # 弹出一个计划执行
        plan = plans.pop(0)
        action_name = plan.get("action")
        args = plan.get("args", {})

        logger.info(f"AI 决定执行动作: {action_name}, 内心独白: {plan.get('thought')}")

        if action_name in ACTIONS:
            try:
                with open(ATTENTIONS, "r", encoding="utf-8") as f:
                    attentions = json.load(f)
                state = attentions.get("state", {})

                # 执行具体动作
                await ACTIONS[action_name](state, args)

                # 写回可能被 action 更改的 state
                attentions["state"] = state
                with open(ATTENTIONS, "w", encoding="utf-8") as f:
                    json.dump(attentions, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"执行动作 {action_name} 失败: {e}", exc_info=True)
        else:
            logger.warning(f"未知动作: {action_name}")

        # 消耗完计划后写回
        with open(PLANS, "w", encoding="utf-8") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)

    async def update(self):
        """更新阶段"""
        try:
            with open(ATTENTIONS, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {"state": {"mood": "calm", "energy": 100}, "events": []}

        has_new = False
        while not self.attention_queue.empty():
            event = self.attention_queue.get_nowait()
            data.setdefault("events", []).append(event)
            has_new = True

        if has_new:
            with open(ATTENTIONS, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


# 全局单例
brain_instance = BrainLoop()
