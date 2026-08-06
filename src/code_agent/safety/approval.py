"""
safety/approval.py — три режима подтверждения.
"""
from typing import Callable, Optional

from code_agent.models import RiskLevel

class ApprovalDenied(Exception):
    pass

class ApprovalManager:
    def __init__(self, mode: str = "ask", ask_callback: Optional[Callable] = None):
        if mode not in ("ask", "auto", "read-only"):
            raise ValueError(f"Неизвестный режим подтверждения: {mode}")
        self.mode = mode
        self.ask_callback = ask_callback

    def require(self, prepared) -> None:
        if self.mode == "read-only":
            raise ApprovalDenied(f"Режим read-only: изменения запрещены ({prepared.tool_name})")

        if self.mode == "auto":
            return

        if self.ask_callback:
            approved = self.ask_callback(prepared)
        else:
            answer = input(
                f"\n⚠️ Требуется подтверждение: {prepared.tool_name} "
                f"с аргументами {prepared.arguments.model_dump()}\n"
                f"Разрешить? [y/N]: "
            ).strip().lower()
            approved = answer in ("y", "yes", "д", "да")

        if not approved:
            raise ApprovalDenied(f"Пользователь отклонил {prepared.tool_name}")
