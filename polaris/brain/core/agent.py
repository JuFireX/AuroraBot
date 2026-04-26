import json
import asyncio
from datetime import datetime
from polaris.utils.Logger import get_logger
from polaris.config import Config

from polaris.brain.action.action import ACTION_ROUTER
from polaris.brain.model.ModelService import get_format_response

logger = get_logger("BrainCore")
ATTENTIONS = Config.POLARIS_BRAIN / "core" / "attentions.json"
PLANS = Config.POLARIS_BRAIN / "core" / "plans.json"
ACTIONS = ACTION_ROUTER
MAX_ATTENTIONS = 40


class BrainLoop:
    def __init__(self):
        self.heart_beat = 10
        self.awake = False
        self.attention_queue = asyncio.Queue()
        self._ensure_files()

    def _default_data(self) -> dict:
        return {
            "state": {
                "mood": "calm",
                "energy": 100,
                "status": "idle",
                "social_drive": 20,
                "last_tick_at": "",
                "last_checked_time": "",
                "last_social_target": {},
            },
            "attentions": [],
        }

    def _normalize_data(self, raw_data) -> dict:
        default_data = self._default_data()
        if not isinstance(raw_data, dict):
            raw_data = {}

        state = raw_data.get("state", {})
        if not isinstance(state, dict):
            state = {}
        normalized_state = default_data["state"].copy()
        normalized_state.update(state)

        attentions = raw_data.get("attentions")
        if attentions is None:
            attentions = raw_data.get("events", [])
        if not isinstance(attentions, list):
            attentions = []

        normalized_attentions = []
        for item in attentions[-MAX_ATTENTIONS:]:
            if not isinstance(item, dict):
                continue
            normalized_item = item.copy()
            normalized_item.setdefault("type", "memo")
            normalized_item.setdefault("status", "active")
            normalized_item.setdefault(
                "created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            normalized_attentions.append(normalized_item)

        return {"state": normalized_state, "attentions": normalized_attentions}

    def _load_attentions(self) -> dict:
        try:
            with open(ATTENTIONS, "r", encoding="utf-8") as f:
                return self._normalize_data(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return self._default_data()

    def _write_attentions(self, data: dict):
        with open(ATTENTIONS, "w", encoding="utf-8") as f:
            json.dump(self._normalize_data(data), f, ensure_ascii=False, indent=2)

    def _append_attention(self, data: dict, item: dict):
        attention = item.copy()
        attention.setdefault("status", "active")
        attention.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        data.setdefault("attentions", []).append(attention)
        data["attentions"] = data["attentions"][-MAX_ATTENTIONS:]

    def _prepare_reply_args(self, state: dict, args: dict) -> dict:
        merged_args = (args or {}).copy()
        last_target = state.get("last_social_target", {})

        for key in ("bot_id", "group_id", "target_id"):
            if not merged_args.get(key) and last_target.get(key):
                merged_args[key] = last_target.get(key)

        if not merged_args.get("trigger_event"):
            merged_args["trigger_event"] = merged_args.get(
                "topic", "忽然想找你聊聊，看看你现在在做什么。"
            )

        return merged_args

    def _build_attention_text(self, attentions: list) -> str:
        if not attentions:
            return "暂无显著注意项，但你仍然有自己的生活节律、当前时间感和社交冲动。"

        lines = []
        for item in attentions[-12:]:
            attention_type = item.get("type", "memo")
            status = item.get("status", "active")
            content = item.get("content") or item.get("trigger_event") or ""
            created_at = item.get("created_at", "")
            lines.append(
                f"- [{created_at}] type={attention_type} status={status} content={content}"
            )
        return "\n".join(lines)

    def _ensure_files(self):
        if not ATTENTIONS.exists() or ATTENTIONS.stat().st_size == 0:
            self._write_attentions(self._default_data())
        else:
            self._write_attentions(self._load_attentions())
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
        attentions = self._load_attentions()
        attention_items = attentions.get("attentions", [])
        state = attentions.get("state", {})

        # 读取 plan 的 Prompt
        prompt_path = Config.PROMPTS_DIR / "prompt_plan.md"
        plan_prompt = '请严格以纯 JSON 格式输出：{"thought": "...", "action": "...", "args": {...}}'
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                plan_prompt = f.read()

        attention_text = self._build_attention_text(attention_items)
        query = (
            f"当前状态: {json.dumps(state, ensure_ascii=False)}\n"
            f"当前注意项:\n{attention_text}\n\n"
            f"{plan_prompt}"
        )
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

            self._append_attention(
                attentions,
                {
                    "type": "plan_note",
                    "status": "handled",
                    "content": response.get("thought", ""),
                    "action": response.get("action"),
                },
            )
            for item in attentions["attentions"]:
                if item.get("type") == "qq_msg" and item.get("status") == "active":
                    item["status"] = "handled"
                    item["handled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._write_attentions(attentions)

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
        attentions = self._load_attentions()
        state = attentions.get("state", {})
        args = plan.get("args", {})
        if action_name == "reply_qq":
            args = self._prepare_reply_args(state, args)

        logger.info(f"AI 决定执行动作: {action_name}, 内心独白: {plan.get('thought')}")

        if action_name in ACTIONS:
            try:
                # 执行具体动作
                await ACTIONS[action_name](state, args)

                # 写回可能被 action 更改的 state
                attentions["state"] = state
                self._append_attention(
                    attentions,
                    {
                        "type": "action_result",
                        "status": "handled",
                        "content": f"执行动作 {action_name}",
                        "action": action_name,
                    },
                )
                self._write_attentions(attentions)
            except Exception as e:
                logger.error(f"执行动作 {action_name} 失败: {e}", exc_info=True)
        else:
            logger.warning(f"未知动作: {action_name}")

        # 消耗完计划后写回
        with open(PLANS, "w", encoding="utf-8") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)

    async def update(self):
        """更新阶段"""
        data = self._load_attentions()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state = data["state"]
        state["last_tick_at"] = now

        current_minute = now[:16]
        if state.get("last_checked_time", "")[:16] != current_minute:
            self._append_attention(
                data,
                {
                    "type": "clock",
                    "status": "handled",
                    "content": f"现在是 {now}",
                },
            )
            state["last_checked_time"] = now

        if state.get("status") == "resting":
            state["energy"] = min(100, state.get("energy", 100) + 2)
        elif state.get("status") == "sleeping":
            state["energy"] = min(100, state.get("energy", 100) + 4)
        else:
            state["social_drive"] = min(100, state.get("social_drive", 20) + 3)

        has_new = False
        while not self.attention_queue.empty():
            event = self.attention_queue.get_nowait()
            event.setdefault("created_at", now)
            event.setdefault("status", "active")
            self._append_attention(data, event)
            if event.get("type") == "qq_msg":
                state["last_social_target"] = {
                    "bot_id": event.get("bot_id"),
                    "group_id": event.get("group_id"),
                    "target_id": event.get("target_id"),
                }
                state["social_drive"] = min(100, state.get("social_drive", 20) + 10)
            has_new = True

        if has_new or True:
            self._write_attentions(data)


# 全局单例
brain_instance = BrainLoop()
