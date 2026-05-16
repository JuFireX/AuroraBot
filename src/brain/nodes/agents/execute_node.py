from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.brain.kernel.base import (
    Agent,
    FileDescriptor,
    FilePattern,
    FileUpdate,
    NodeState,
)
from src.brain.kernel.state_store import parse_llm_json
from src.config import Config
from src.utils.log_utils import get_logger
from src.utils.time_utils import now_text

if TYPE_CHECKING:
    from src.platform.application_host import ApplicationHost

logger = get_logger("ExecuteAgent")

_DATA_DIR = Config.KERNEL_DATA_DIR

_EXECUTE_SYSTEM_PROMPT = """\
你是 AuroraBot 的执行节点。根据命令执行结果决定动作状态。

你会收到：
1. action：包含 command、kwargs 的动作对象
2. result：命令执行的返回结果

输出严格 JSON：
{
  "status": "done",
  "reasoning": "判断依据（一句话）",
  "next_step": null
}

status 取值：
- "done"：执行成功，无需后续
- "failed"：不可恢复的错误（参数错误、权限不足等）
- "retry"：临时错误（超时、网络问题），建议重试

规则：
- 执行成功返回 done
- 临时错误（timeout、connection、rate_limit）→ retry
- 参数错误、不可恢复 → failed
- next_step：仅在 failed/retry 时填写建议的下一步
"""


class ExecuteNode(Agent):
    """执行 action 并理解结果的 Agent 节点。

    守护 ``actions/action_*.json`` 文件，当新的 pending action 到达时，
    调用宿主命令执行，将结果交给 LLM 判断状态（done / failed / retry），
    更新 action 与对应 plan 的状态。

    LLM 不可用时回退到机械判断（无异常 → done）。
    """

    def __init__(self, node_id: str, host: ApplicationHost) -> None:  # noqa: F821
        super().__init__(node_id, host, system_prompt=_EXECUTE_SYSTEM_PROMPT)
        self._actions_dir = _DATA_DIR / "actions"
        self._plans_dir = _DATA_DIR / "plans"

    @property
    def type(self) -> str:
        return "agent"

    @property
    def guards(self) -> list[FilePattern]:
        if self._config_watch is not None:
            return [FilePattern(p) for p in self._config_watch]
        return [FilePattern("actions/action_*.json")]

    @property
    def produces(self) -> list[FileDescriptor]:
        if self._config_emit is not None:
            return [FileDescriptor(p) for p in self._config_emit]
        return [
            FileDescriptor("actions/action.json"),
            FileDescriptor("plans/plan.json"),
        ]

    async def execute(self) -> list[FileUpdate]:
        """扫描 pending action，执行命令并让 LLM 判断结果。"""
        if not self._actions_dir.exists():
            return []

        pending_actions = self._scan_pending_actions()
        if not pending_actions:
            return []

        updates: list[FileUpdate] = []
        for action_path, action_data in pending_actions:
            try:
                command_name = str(action_data.get("command", ""))
                if not command_name:
                    logger.warning(f"action 缺少命令名: {action_path.name}")
                    continue

                # 标记 running
                action_data["status"] = "running"
                action_data["updated_at"] = now_text()
                updates.append(self._make_action_update(action_path, action_data))

                # 执行命令
                try:
                    result = await self._host.invoke_command(
                        command_name,
                        **self._normalize_kwargs(action_data.get("kwargs")),
                    )
                except Exception as exc:  # noqa: BLE001
                    # 命令执行本身抛异常 → 直接标记 failed，不调 LLM
                    action_data["status"] = "failed"
                    action_data["error"] = str(exc)
                    action_data["updated_at"] = now_text()
                    logger.warning(f"命令执行异常: {command_name}, error={exc}")
                    updates.append(self._make_action_update(action_path, action_data))
                    plan_update = self._update_plan_status(
                        str(action_data.get("plan_id", "")), "failed"
                    )
                    if plan_update is not None:
                        updates.append(plan_update)
                    continue

                # 让 LLM 判断结果
                judgement = await self._judge_result(action_data, result)
                action_data["status"] = judgement.get("status", "done")
                action_data["result"] = result
                action_data["judgement_reasoning"] = judgement.get("reasoning", "")
                action_data["judgement_next_step"] = judgement.get("next_step")
                action_data["updated_at"] = now_text()

                logger.info(
                    f"命令执行完成: {command_name} → status={action_data['status']}"
                )

                # 更新对应 plan 状态
                plan_status = (
                    "done" if action_data["status"] == "done" else action_data["status"]
                )
                plan_update = self._update_plan_status(
                    str(action_data.get("plan_id", "")), plan_status
                )
                if plan_update is not None:
                    updates.append(plan_update)

                updates.append(self._make_action_update(action_path, action_data))

            except Exception:
                logger.exception(f"ExecuteAgent 执行 action 失败: {action_path.name}")

        return updates

    async def _judge_result(
        self,
        action_data: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        """调用 LLM 判断执行结果。"""
        action_info = {
            "command": action_data.get("command", ""),
            "kwargs": action_data.get("kwargs", {}),
        }
        user_msg = (
            f"action:\n{json.dumps(action_info, indent=2, ensure_ascii=False)}\n\n"
            f"result:\n{json.dumps(result, indent=2, ensure_ascii=False)}\n\n"
            f"判断执行状态。"
        )
        messages = [{"role": "user", "content": user_msg}]

        try:
            raw = await self.think(messages, max_tokens=256)
        except Exception:
            logger.exception("ExecuteAgent LLM 调用失败，回退到机械判断")
            return self._fallback_judgement(result)

        parsed = parse_llm_json(raw)
        if parsed is None:
            logger.warning(f"ExecuteAgent LLM 输出不可解析，回退到机械判断: {raw!r}")
            return self._fallback_judgement(result)

        return {
            "status": str(parsed.get("status", "done")),
            "reasoning": str(parsed.get("reasoning", "")),
            "next_step": parsed.get("next_step"),
        }

    @staticmethod
    def _fallback_judgement(result: Any) -> dict[str, Any]:
        """LLM 不可用时的机械判断：命令没抛异常 → done。"""
        return {
            "status": "done",
            "reasoning": "LLM 不可用，使用机械回退（无异常视为成功）",
            "next_step": None,
        }

    def _scan_pending_actions(
        self,
    ) -> list[tuple[Path, dict[str, Any]]]:
        """扫描 actions 目录，返回 status == pending 的 action。"""
        pending: list[tuple[Path, dict[str, Any]]] = []
        for action_path in sorted(self._actions_dir.glob("action_*.json")):
            try:
                data = json.loads(action_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("status") == "pending":
                    pending.append((action_path, data))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(f"读取 action 文件失败 {action_path.name}: {exc}")
        return pending

    def _make_action_update(
        self,
        action_path: Path,
        action_data: dict[str, Any],
    ) -> FileUpdate:
        return FileUpdate(
            descriptor=FileDescriptor(
                path=f"actions/{action_path.name}",
                schema="json",
            ),
            content=action_data,
        )

    def _update_plan_status(
        self,
        plan_id: str,
        status: str,
    ) -> FileUpdate | None:
        if not plan_id:
            return None
        plan_path = self._plans_dir / f"plan_{plan_id}.json"
        if not plan_path.exists():
            return None
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan_data, dict):
                return None
            plan_data["status"] = status
            plan_data["updated_at"] = now_text()
            return FileUpdate(
                descriptor=FileDescriptor(
                    path=f"plans/{plan_path.name}",
                    schema="json",
                ),
                content=plan_data,
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"更新 plan 状态失败 {plan_path.name}: {exc}")
            return None

    @staticmethod
    def _normalize_kwargs(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def on_complete(self) -> None:
        if self.state != NodeState.ERROR:
            self.state = NodeState.IDLE
