from litellm import acompletion
from polaris.config import Config
from polaris.utils.Logger import get_logger
import json

logger = get_logger("ModelService")

SYSTEM_PROMPT_FORMAT = "按照指定Format回答Query。你必须输出纯JSON格式，不要包含任何 markdown 格式如 ```json。"


async def get_format_response(query: str, format: str) -> str:
    response = await acompletion(
        model=Config().MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_FORMAT},
            {"role": "user", "content": f"query: {query}\nformat: {format}"},
        ],
    )
    return response.choices[0].message.content


async def get_json_response(system_prompt: str, user_prompt: str) -> dict:
    """
    请求大模型并强制解析为 JSON 字典。
    适用于 Agent 的 Plan 阶段。
    """
    try:
        response = await acompletion(
            model=Config().MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                    + "\n\n请严格输出 JSON 格式，不要包含 ```json 标签。",
                },
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()

        # 兼容可能有 markdown 代码块的情况
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"大模型 JSON 解析失败: {e}")
        return {"action": "idle", "thought": f"解析失败: {e}"}
