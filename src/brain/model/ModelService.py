import json
from dataclasses import dataclass
from typing import Any

from litellm import acompletion

from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger("ModelService")

SYSTEM_PROMPT_FORMAT = (
    "按照指定Format回答Query. 请务必输出纯JSON格式, 不要包含任何 markdown 标记"
)
MAX_TRIAL = 3


@dataclass
class LLMToolCall:
    name: str
    arguments: dict[str, Any]


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
        result[-1]["content"] = trim_text(
            result[-1]["content"], max(0, len(result[-1]["content"]) - overflow)
        )
    return result


async def chat_completion(
    messages: list[dict[str, Any]], total_limit: int | None = None, **kwargs: Any
) -> Any:
    clipped_messages = clip_messages_to_limit(messages, total_limit)
    return await acompletion(model=Config.MODEL, messages=clipped_messages, **kwargs)


async def llm_call(
    system: str,
    tools: list[dict[str, Any]],
    message: str,
) -> list[LLMToolCall]:
    openai_tools = [_adapt_tool_schema(tool) for tool in tools]
    response = await chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        tools=openai_tools,
        tool_choice="auto",
    )

    tool_calls = _extract_tool_calls(response)
    if tool_calls:
        return tool_calls

    content = str(getattr(response.choices[0].message, "content", "") or "").strip()
    content = _adapt_possible_json(content)
    parsed_calls = _parse_calls_from_content(content)
    if parsed_calls:
        return parsed_calls

    raise ValueError("LLM 未返回可解析的 tool calls")


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


def _adapt_tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    if tool.get("type") == "function":
        return tool
    return {
        "type": "function",
        "function": {
            "name": str(tool.get("name", "")),
            "description": str(tool.get("description", "")),
            "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
        },
    }


def _extract_tool_calls(response: Any) -> list[LLMToolCall]:
    message = response.choices[0].message
    raw_tool_calls = getattr(message, "tool_calls", None) or []
    parsed: list[LLMToolCall] = []
    for tool_call in raw_tool_calls:
        function = getattr(tool_call, "function", None)
        if function is None and isinstance(tool_call, dict):
            function = tool_call.get("function")
        name = _pick_attr(function, "name")
        arguments_raw = _pick_attr(function, "arguments")
        if not name:
            continue
        parsed.append(
            LLMToolCall(
                name=str(name),
                arguments=_parse_arguments(arguments_raw),
            )
        )
    return parsed


def _parse_calls_from_content(content: str) -> list[LLMToolCall]:
    if not content:
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("[ModelService] LLM 返回非 JSON 内容: %s", content)
        return []

    raw_calls: list[dict[str, Any]] = []
    if isinstance(payload, list):
        raw_calls = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("tool_calls"), list):
            raw_calls = [item for item in payload["tool_calls"] if isinstance(item, dict)]
        elif payload.get("name"):
            raw_calls = [payload]

    parsed: list[LLMToolCall] = []
    for item in raw_calls:
        name = str(item.get("name", "") or item.get("tool_name", ""))
        if not name:
            continue
        parsed.append(
            LLMToolCall(
                name=name,
                arguments=_parse_arguments(item.get("arguments", item.get("params", {}))),
            )
        )
    return parsed


def _pick_attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.warning(
                "[ModelService] Tool arguments 不是合法 JSON，已降级为空对象: %s",
                raw_arguments,
            )
            return {}
    return {}
