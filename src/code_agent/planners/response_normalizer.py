# code_agent/planners/response_normalizer.py
import logging
from typing import Any, Dict, Optional
from code_agent.models import AgentAction

logger = logging.getLogger(__name__)

class ResponseNormalizer:
    @staticmethod
    def normalize(raw: Optional[Dict[str, Any]]) -> AgentAction:
        if raw is None or not isinstance(raw, dict):
            return AgentAction(
                type="message",
                message="⚠️ Планировщик вернул пустой ответ. Попробуйте переформулировать задачу."
            )

        data = raw.copy()
        if "type" not in data or data["type"] not in ("tool_call", "finish", "message"):
            data["type"] = "message"
            data["message"] = data.get("message") or "Не удалось распознать действие."

        if data["type"] == "message":
            if not data.get("message"):
                data["message"] = "Планировщик не дал комментария."
            data.pop("tool", None); data.pop("summary", None); data.pop("arguments", None)

        elif data["type"] == "tool_call":
            if not data.get("tool"):
                data["type"] = "message"
                data["message"] = "Планировщик не указал инструмент."
            else:
                if not isinstance(data.get("arguments"), dict):
                    data["arguments"] = {}
                data.pop("message", None); data.pop("summary", None)

        elif data["type"] == "finish":
            if not data.get("summary"):
                data["type"] = "message"
                data["message"] = "Планировщик не предоставил итога."
            else:
                data.pop("message", None); data.pop("tool", None); data.pop("arguments", None)

        try:
            return AgentAction(**data)
        except Exception as e:
            logger.error("Ошибка создания AgentAction: %s", e)
            return AgentAction(
                type="message",
                message=f"⚠️ Внутренняя ошибка при разборе ответа: {e}"
            )
