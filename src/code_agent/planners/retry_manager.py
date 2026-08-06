"""
Менеджер повторных попыток с экспоненциальной задержкой.
Используется для обёртки вызовов внешних API (Colab, Groq).
"""
import logging
import time
from typing import Callable, TypeVar, Any, Tuple, Optional

T = TypeVar('T')
logger = logging.getLogger(__name__)


class RetryManager:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        retryable_exceptions: Tuple[type, ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions

    def call(self, func: Callable[..., T], *args, **kwargs) -> Optional[T]:
        """
        Выполняет функцию с повторными попытками при возникновении исключений.
        Возвращает результат функции или None, если все попытки провалились.
        """
        last_exception = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt == self.max_attempts:
                    break
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                logger.warning(
                    "Попытка %d/%d завершилась ошибкой: %s. Повтор через %.2f с.",
                    attempt, self.max_attempts, e, delay
                )
                time.sleep(delay)
        # Все попытки исчерпаны
        logger.error("Все попытки (%d) завершились ошибкой: %s", self.max_attempts, last_exception)
        return None
