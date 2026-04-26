import os
from pathlib import Path
from polaris.config import Config
from polaris.utils.Logger import get_logger
from litellm import acompletion

logger = get_logger("LanguageService")

class LanguageService:
    def __init__(self):
        self.persona = self._load_persona()

    def _load_persona(self) -> str:
        persona_path = Config.PROJECT_ROOT / "soul" / "persona.md"
        if not persona_path.exists():
            logger.warning("未找到灵魂文档 soul/persona.md，将使用默认人格。")
            return "你是一个在赛博空间中的游荡者。"
        
        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info("灵魂文档加载完成。")
                return content
        except Exception as e:
            logger.error(f"加载灵魂文档失败: {e}")
            return "你是一个在赛博空间中的游荡者。"

    async def organize_reply(self, context: str, current_event: str) -> str:
        """
        根据灵魂文档、当前记忆上下文以及当下的事件，组织回复内容。
        """
        system_prompt = (
            f"以下是你的灵魂设定与人格描述：\n{self.persona}\n\n"
            f"请你严格按照上述人格进行思考与回复。不要做任何解释。\n"
            f"以下是你脑海中刚浮现的回忆片段（历史对话）：\n{context}\n\n"
        )

        user_prompt = (
            f"当前最新收到的消息/事件：\n{current_event}\n"
            f"请你作为自己，给出内心的回应或者想说出的话。只需要返回你的原话内容，不要输出任何如【思考】或（动作）的标记。"
        )

        logger.debug("语言模块正在酝酿词汇...")
        try:
            response = await acompletion(
                model=Config.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            reply_text = response.choices[0].message.content.strip()
            return reply_text
        except Exception as e:
            logger.error(f"组织语言时发生异常：{e}")
            return "......"

language_service = LanguageService()
