# code_agent/planners/safe_planner.py
import logging
from typing import Optional, Any
from code_agent.models import AgentAction
from code_agent.planners.base import Planner
from code_agent.planners.response_normalizer import ResponseNormalizer
from code_agent.planners.retry_manager import RetryManager

logger = logging.getLogger(__name__)

class SafePlanner(Planner):
    def __init__(
        self,
        inner_planner: Planner,
        retry_manager: Optional[RetryManager] = None,
        normalizer: Optional[ResponseNormalizer] = None,
    ):
        self.inner = inner_planner
        self.retry_manager = retry_manager or RetryManager()
        self.normalizer = normalizer or ResponseNormalizer()

    def next_action(self, goal: str, context: dict, tools_schema: list) -> AgentAction:
        def _call_inner() -> Optional[Any]:
            try:
                return self.inner.next_action(goal, context, tools_schema)
            except Exception as e:
                logger.error("Ошибка при вызове внутреннего планировщика: %s", e)
                raise

        result = self.retry_manager.call(_call_inner)

        if result is None:
            return AgentAction(
                type="message",
                message="⚠️ Планировщик не ответил после нескольких попыток. Проверьте соединение."
            )

        # Если это уже AgentAction, проверяем содержимое
        if isinstance(result, AgentAction):
            # Если type='message' и message пустое — заменяем
            if result.type == "message" and not result.message:
                return AgentAction(
                    type="message",
                    message="⚠️ Планировщик вернул пустое сообщение (заменено)."
                )
            # Если type='tool_call' и нет reason — добавим стандартный
            if result.type == "tool_call" and not result.reason:
                result.reason = "Выполняю действие по задаче"
            return result

        # Если словарь — нормализуем
        if isinstance(result, dict):
            return self.normalizer.normalize(result)

        # Иначе — ошибка
        return AgentAction(
            type="message",
            message=f"⚠️ Планировщик вернул данные неожиданного формата: {result}"
        )
