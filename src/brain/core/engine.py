import asyncio
import time
from typing import Dict, List, Tuple

from src.brain.core.executor import executor_registry
from src.brain.core.expander import expander_registry
from src.brain.core.models import Attention, AttentionState, Plan, TodoItem, Urgency
from src.brain.core.queues import Queues
from src.brain.core.state import State
from src.config import Config
from src.utils.Logger import get_logger

logger = get_logger()


class HeartbeatEngine:
    def __init__(self, state: State, queues: Queues):
        self.state = state
        self.queues = queues
        self._running = False
        self._task = None

    async def start(self, interval_seconds: float = 1.0):
        if self._running:
            return
        self._running = True
        logger.info("Heartbeat Engine starting...")
        self._task = asyncio.create_task(self._loop(interval_seconds))

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Heartbeat Engine stopped.")

    async def _loop(self, interval_seconds: float):
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    async def _tick(self):
        self.state.heartbeat_count += 1

        # 1. Regenerate energy
        self.state.regenerate_energy()
        self._repair_attention_state()

        has_todo = not self.queues.todo_queue.is_empty()
        self.state.record_activity(has_todo)

        # Update idle counter
        if not has_todo:
            self.state.idle_counter += 1
        else:
            self.state.idle_counter = 0

        self.state.refresh_plan_interval(
            backlog_size=self.queues.todo_queue.size() + self.queues.plan_queue.size(),
            has_active_attention=self.queues.current_attention is not None,
        )

        # 2. Plan phase
        if self.state.heartbeat_count % self.state.plan_interval == 0:
            self._plan_phase()

        # 3. Attention phase
        if (
            self.queues.action_queue.is_empty()
            and self.queues.current_attention is None
        ):
            self._attention_phase()

        # 4. Action phase
        await self._action_phase()

        # 5. Persist state and queues
        self.state.save()
        self.queues.save()

    def _plan_phase(self):
        items = self.queues.todo_queue.drain()
        if not items:
            return

        logger.debug(f"[Plan Phase] Processing {len(items)} TodoItems")

        groups: Dict[Tuple[str, str | None], List[TodoItem]] = {}
        for item in items:
            intent = Config.resolve_intent(item.type)
            group_key = item.group_key or item.payload.get("group_key")
            groups.setdefault((intent, group_key), []).append(item)

        for (intent, group_key), group_items in groups.items():
            base_priority = self._calculate_priority(group_items)

            existing_plan = self.queues.plan_queue.find_by_intent(intent, group_key)

            in_attention = (
                self.queues.current_attention
                and self.queues.current_attention.intent == intent
                and self.queues.current_attention.group_key == group_key
            )

            if existing_plan and not in_attention:
                existing_plan.sub_items.extend(group_items)
                existing_plan.priority = max(existing_plan.priority, base_priority)
                existing_plan.base_priority = max(
                    existing_plan.base_priority, base_priority
                )
                existing_plan.last_touched_at = time.time()
                self.queues.plan_queue.update(existing_plan)
                logger.debug(
                    f"[Plan Phase] Updated existing Plan: {intent} (priority: {existing_plan.priority})"
                )
            else:
                new_plan = Plan(
                    intent=intent,
                    group_key=group_key,
                    sub_items=group_items,
                    priority=base_priority,
                    base_priority=base_priority,
                )
                self.queues.plan_queue.push(new_plan)
                logger.debug(
                    f"[Plan Phase] Created new Plan: {intent} (priority: {new_plan.priority})"
                )

    def _repair_attention_state(self):
        attention = self.queues.current_attention
        action_queue_empty = self.queues.action_queue.is_empty()

        if attention is None:
            return

        if attention.state == AttentionState.COMPLETED:
            logger.warning(
                f"[Engine Repair] Clearing completed attention '{attention.intent}'"
            )
            self.queues.current_attention = None
            self.queues.action_queue.clear()
            return

        remaining_actions = attention.action_list[attention.current_index :]
        if action_queue_empty and remaining_actions:
            logger.warning(
                f"[Engine Repair] Restoring {len(remaining_actions)} actions for '{attention.intent}'"
            )
            self.queues.action_queue.replace(remaining_actions)
            if attention.state == AttentionState.PAUSED:
                attention.state = AttentionState.ACTIVE
            return

        if action_queue_empty and not remaining_actions:
            logger.warning(
                f"[Engine Repair] Clearing stale attention '{attention.intent}' with no remaining actions"
            )
            self.queues.current_attention = None
            return

    def _attention_phase(self):
        if self.queues.plan_queue.is_empty():
            if (
                self.state.is_idle_mode()
                and self.state.idle_counter % Config.SELF_MAINTENANCE_INTERVAL == 0
            ):
                # 没事找事：自维护计划
                logger.debug("[Attention Phase] Idle mode triggered self_maintenance")
                plan = Plan(intent="self_maintenance", priority=1.0, base_priority=1.0)
            else:
                return
        else:
            if self.state.is_idle_mode():
                # 闲时拾取：取最低优先级的消化
                plan = self.queues.plan_queue.pop_lowest()
                logger.debug(
                    f"[Attention Phase] Idle mode: Picked lowest priority plan: {plan.intent}"
                )
            else:
                plan = self.queues.plan_queue.pop_highest()
                logger.debug(
                    f"[Attention Phase] Picked highest priority plan: {plan.intent}"
                )

        # Create attention
        action_list = expander_registry.expand(plan.intent, plan.sub_items)
        total_energy = sum(a.energy_cost for a in action_list)

        attention = Attention(
            plan_id=plan.id,
            intent=plan.intent,
            group_key=plan.group_key,
            priority=plan.priority,
            total_energy_estimate=total_energy,
            action_list=action_list,
        )

        self.queues.current_attention = attention
        self.queues.action_queue.replace(action_list)
        logger.info(
            f"[Attention Phase] Focus shifted to '{plan.intent}' with {len(action_list)} actions (est. energy: {total_energy})"
        )

    async def _action_phase(self):
        execute_count = 0

        while (
            not self.queues.action_queue.is_empty()
            and execute_count < Config.MAX_ACTIONS_PER_BEAT
        ):
            next_action = self.queues.action_queue.peek()

            if self.state.energy_current < next_action.energy_cost:
                if self.queues.current_attention:
                    self.queues.current_attention.state = AttentionState.PAUSED
                    logger.debug(
                        f"[Action Phase] Paused '{self.queues.current_attention.intent}' due to low energy ({self.state.energy_current} < {next_action.energy_cost})"
                    )
                break  # Wait for next heartbeat

            if not await executor_registry.check_preconditions(next_action):
                self.queues.action_queue.pop()
                execute_count += 1
                if self.queues.current_attention:
                    self.queues.current_attention.current_index += 1
                continue

            # Energy is sufficient
            if (
                self.queues.current_attention
                and self.queues.current_attention.state == AttentionState.PAUSED
            ):
                self.queues.current_attention.state = AttentionState.ACTIVE
                logger.debug(
                    f"[Action Phase] Resumed '{self.queues.current_attention.intent}'"
                )

            action = self.queues.action_queue.pop()

            # Execute
            try:
                await executor_registry.execute(action)
                self.state.energy_current -= action.energy_cost
            except Exception as e:
                logger.error(
                    f"[Action Phase] Error executing action {action.type}: {e}"
                )

            execute_count += 1

            if self.queues.current_attention:
                self.queues.current_attention.current_index += 1

                # Check if attention is completed
                if self.queues.current_attention.current_index >= len(
                    self.queues.current_attention.action_list
                ):
                    logger.info(
                        f"[Action Phase] Completed attention '{self.queues.current_attention.intent}'"
                    )
                    self.queues.current_attention.state = AttentionState.COMPLETED
                    self.queues.current_attention = None
                    break  # Finish this attention, wait for next heartbeat to pick new attention

    def _calculate_priority(self, items: List[TodoItem]) -> float:
        urgency_bonus = {
            Urgency.GENTLE: 1.0,
            Urgency.NORMAL: 10.0,
            Urgency.URGENT: 100.0,
        }
        base_priority = max(urgency_bonus[item.urgency] for item in items)
        return base_priority + len(items) * 0.5
