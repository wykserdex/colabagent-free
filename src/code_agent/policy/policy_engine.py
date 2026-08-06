from typing import Literal, List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

class ActionStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUEST_APPROVAL = "request_approval"

class PolicyDecision(BaseModel):
    status: ActionStatus
    reason: str
    required_role: Optional[str] = None

class PolicyEngine:
    """
    Детерминированный движок политик безопасности.
    LLM предлагает действие, но этот движок решает, можно ли его выполнить.
    """
    def __init__(self, mode: str = "supervised"):
        self.mode = mode
        # Матрица разрешений: инструмент -> режим -> разрешение
        # ВАЖНО: раньше action_key определялся по substring-эвристике
        # ("write" in tool_name и т.п.), из-за чего code.run_script (запуск
        # произвольного Python-скрипта) не попадал ни под одно правило и
        # тихо классифицировался как fs.read — то есть выполнялся без
        # approval даже в supervised. Явная карта по точным именам инструментов
        # надёжнее и не ломается при добавлении новых тулов с похожими словами.
        self.tool_action_map: Dict[str, str] = {
            "filesystem.list_files": "fs.read",
            "filesystem.read_file": "fs.read",
            "filesystem.write_file": "fs.write",
            "code.apply_patch": "fs.patch",
            "code.run_script": "code.execute",
            "tests.run": "code.execute",
            "search.search_text": "fs.read",
            "git.status": "git.read",
            "git.diff": "git.read",
        }

        self.rules = {
            "fs.read": {
                "autonomous": True,
                "supervised": True,
                "explain-only": False,
                "review": True
            },
            "fs.write": {
                "autonomous": True,  # В автономном режиме можно писать без спроса (в пределах safe paths)
                "supervised": "approval",
                "explain-only": False,
                "review": False
            },
            "fs.patch": {
                "autonomous": True,
                "supervised": "approval",
                "explain-only": False,
                "review": False
            },
            # Выполнение кода (скрипты, тесты) — не то же самое, что fs.read.
            # Требует подтверждения даже в supervised, т.к. может делать что угодно
            # в пределах прав процесса (сеть, запись через сам скрипт и т.д.)
            "code.execute": {
                "autonomous": True,
                "supervised": "approval",
                "explain-only": False,
                "review": False
            },
            # Чтение git-состояния (status/diff) — безобидно, не требует approval
            # даже в supervised, в отличие от git.commit.
            "git.read": {
                "autonomous": True,
                "supervised": True,
                "explain-only": False,
                "review": True
            },
            "shell.run": {
                "autonomous": "approval",  # Даже автономный режим спрашивает для shell
                "supervised": "approval",
                "explain-only": False,
                "review": False
            },
            "network.request": {
                "autonomous": False,
                "supervised": "approval",
                "explain-only": False,
                "review": False
            },
            "git.commit": {
                "autonomous": False,
                "supervised": "approval",
                "explain-only": False,
                "review": True
            }
        }
        
        # Запрещенные пути и паттерны
        self.forbidden_paths = [".env", ".git/", "id_rsa", "secrets/"]
        self.safe_write_paths = ["./workspace", "./tmp", "./projects"]

    def check_action(self, tool_name: str, args: Dict[str, Any]) -> PolicyDecision:
        """Проверяет действие против политик."""
        
        # 1. Проверка запрещенных путей
        path = args.get("path", "") or args.get("cwd", "")
        for forbidden in self.forbidden_paths:
            if forbidden in path:
                return PolicyDecision(
                    status=ActionStatus.DENY,
                    reason=f"Access to '{forbidden}' is strictly forbidden."
                )

        # 2. Определение типа действия — сначала точное совпадение по имени
        # инструмента, и только если инструмент неизвестен движку — консервативный
        # fallback по подстрокам (лучше лишний раз спросить подтверждение,
        # чем тихо разрешить незнакомый tool).
        if tool_name in self.tool_action_map:
            action_key = self.tool_action_map[tool_name]
        elif tool_name == "shell.run":
            action_key = "shell.run"
        elif "network" in tool_name:
            action_key = "network.request"
        elif "commit" in tool_name or "push" in tool_name:
            action_key = "git.commit"
        elif "git" in tool_name:
            action_key = "git.read"
        elif "patch" in tool_name:
            action_key = "fs.patch"
        elif "write" in tool_name or "create" in tool_name:
            action_key = "fs.write"
        elif "read" in tool_name or "list" in tool_name or "search" in tool_name:
            action_key = "fs.read"
        else:
            # Неизвестный тул — не угадываем, требуем approval
            return PolicyDecision(
                status=ActionStatus.REQUEST_APPROVAL,
                reason=f"Незнакомый инструмент '{tool_name}' не описан в политике — требуется подтверждение"
            )
        
        rule = self.rules.get(action_key, {})
        permission = rule.get(self.mode, False)

        if permission is True:
            return PolicyDecision(status=ActionStatus.ALLOW, reason="Policy allowed")
        elif permission == "approval":
            return PolicyDecision(
                status=ActionStatus.REQUEST_APPROVAL, 
                reason="Requires user confirmation in this mode"
            )
        else:
            return PolicyDecision(status=ActionStatus.DENY, reason="Action forbidden in current mode")

    def get_mode_description(self) -> str:
        modes = {
            "autonomous": "Полная автономность (с ограничениями безопасности)",
            "supervised": "Запрос подтверждения на опасные действия",
            "explain-only": "Только объяснения, без изменений",
            "review": "Только анализ и чтение"
        }
        return modes.get(self.mode, "Unknown")
