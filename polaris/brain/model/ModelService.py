from litellm import acompletion
from polaris.config import Config
from polaris.utils.Logger import get_logger
import json
from typing import Any

logger = get_logger("ModelService")

SYSTEM_PROMPT_FORMAT = (
    "按照指定Format回答Query. 请务必输出纯JSON格式, 不要包含任何 markdown 标记"
)
MAX_TRIAL = 3


def trim_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: max(0, limit - 1)].rstrip() + "…"


def clip_messages_to_limit(
    messages: list[dict[str, Any]], total_limit: int | None = None
) -> list[dict[str, str]]:
    limit = total_limit or Config.AI_CONTEXT_CHAR_LIMIT
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        normalized.append({"role": role, "content": content})

    if not normalized:
        return normalized

    system_messages = [msg for msg in normalized if msg["role"] == "system"]
    other_messages = [msg for msg in normalized if msg["role"] != "system"]
    if limit <= 0:
        return []

    system_budget = min(limit, max(600, limit // 2)) if system_messages else 0
    system_clipped: list[dict[str, str]] = []
    used_system = 0
    for index, message in enumerate(system_messages):
        remaining = len(system_messages) - index
        reserve = max(0, remaining - 1) * 40
        available = max(0, system_budget - used_system - reserve)
        if available <= 0:
            break
        content = trim_text(message["content"], available)
        system_clipped.append({"role": "system", "content": content})
        used_system += len(content)

    remaining_budget = max(0, limit - used_system)
    selected_other_messages: list[dict[str, str]] = []
    used_other = 0
    for message in reversed(other_messages):
        available = remaining_budget - used_other
        if available <= 0:
            break
        content = trim_text(message["content"], available)
        selected_other_messages.append({"role": message["role"], "content": content})
        used_other += len(content)
        if used_other >= remaining_budget:
            break

    selected_other_messages.reverse()
    result = system_clipped + selected_other_messages

    total = sum(len(msg["content"]) for msg in result)
    if total > limit and result:
        overflow = total - limit
        result[-1]["content"] = trim_text(result[-1]["content"], max(0, len(result[-1]["content"]) - overflow))
    return result


async def chat_completion(
    messages: list[dict[str, Any]], total_limit: int | None = None, **kwargs: Any
):
    clipped_messages = clip_messages_to_limit(messages, total_limit)
    return await acompletion(model=Config.MODEL, messages=clipped_messages, **kwargs)


async def get_format_response(query: str, format: str) -> dict:
    trial = 0
    while trial < MAX_TRIAL:
        response = await chat_completion(
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
            trial += 1
            continue
        return json.loads(content)
    return {}


def _adapt_possible_json(content: str) -> str:
    """适配可能的 JSON 格式"""
    if content.startswith("```"):
        content = content.replace("```", "").strip()
    elif content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```JSON"):
        content = content.replace("```JSON", "").replace("```", "").strip()
    return content
