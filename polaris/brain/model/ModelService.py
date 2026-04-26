from litellm import acompletion
from polaris.config import Config
from polaris.utils.Logger import get_logger
import json

logger = get_logger("ModelService")

SYSTEM_PROMPT_FORMAT = "按照指定Format回答Query. 你必须输出纯JSON格式, 不要包含任何 markdown 格式如 ```json"


async def get_format_response(query: str, format: str) -> dict:
    response = await acompletion(
        model=Config().MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_FORMAT},
            {"role": "user", "content": f"query: {query}\nformat: {format}"},
        ],
    )

    content = response.choices[0].message.content.strip()
    content = _adapt_possible_json(content)
    try:
        json.loads(content)
    except json.JSONDecodeError:
        logger.error(f"转换为 JSON 失败: {content}")
        return {}
    return json.loads(content)


def _adapt_possible_json(content: str) -> str:
    """适配可能的 JSON 格式"""
    if content.startswith("```"):
        content = content.replace("```", "").strip()
    elif content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```JSON"):
        content = content.replace("```JSON", "").replace("```", "").strip()
    return content
