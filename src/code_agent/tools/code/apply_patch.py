"""
tools/code/apply_patch.py — точечное редактирование вместо полной перезаписи файла.
Требование 'old_text встречается РОВНО один раз' — это не бюрократия, это защита
от того самого паттерна который мы ловили: модель 'чинит' один баг и попутно
переписывает весь файл, теряя всё что было рабочим. Патч технически не может
снести остальной файл, максимум — заменить именно указанный фрагмент.
"""
from pydantic import BaseModel

from code_agent.infrastructure.atomic_write import atomic_write
from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext


class ApplyPatchArgs(BaseModel):
    path: str
    old_text: str
    new_text: str


class ApplyPatchTool(Tool[ApplyPatchArgs]):
    name = "code.apply_patch"
    description = (
        "Заменяет ТОЧНЫЙ фрагмент old_text на new_text в файле. "
        "old_text должен встречаться в файле РОВНО один раз, иначе — ошибка. "
        "Предпочтительнее filesystem.write_file для любого изменения существующего файла."
    )
    args_model = ApplyPatchArgs
    default_risk = RiskLevel.REVIEW

    def execute(self, arguments: ApplyPatchArgs, context: ToolContext) -> ToolResult:
        try:
            target = resolve_project_path(context.project_root, arguments.path)
        except SafetyError as e:
            return ToolResult(success=False, error=str(e))

        if not target.exists():
            return ToolResult(success=False, error=f"Файл не существует: {arguments.path}")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, error=f"Ошибка чтения: {e}")

        occurrences = content.count(arguments.old_text)
        if occurrences == 0:
            return ToolResult(
                success=False,
                error="old_text не найден в файле дословно — проверь точное совпадение "
                      "(включая отступы и переносы строк), возможно файл уже изменился",
            )
        if occurrences > 1:
            return ToolResult(
                success=False,
                error=f"old_text встречается {occurrences} раз(а) — нужно ровно 1 совпадение, "
                      f"уточни фрагмент чтобы он был уникальным",
            )

        new_content = content.replace(arguments.old_text, arguments.new_text, 1)

        try:
            atomic_write(target, new_content)
        except Exception as e:
            return ToolResult(success=False, error=f"Ошибка записи: {e}")

        rel_path = str(target.relative_to(context.project_root.resolve()))
        return ToolResult(
            success=True,
            output=f"Патч применён в {rel_path}",
            changed_files=[rel_path],
        )
