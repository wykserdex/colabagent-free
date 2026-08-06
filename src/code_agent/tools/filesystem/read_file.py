"""
tools/filesystem/read_file.py — читает диапазон строк файла, добавляет номера строк
(модели проще ссылаться на конкретные строки при apply_patch). path_guard уже
запрещает .env/.git/ключи на уровне resolve_project_path — здесь просто используем его.
"""
from pydantic import BaseModel, Field
from typing import Optional

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext


class ReadFileArgs(BaseModel):
    path: str
    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)


class ReadFileTool(Tool[ReadFileArgs]):
    name = "filesystem.read_file"
    description = "Читает файл (опционально диапазон строк) внутри проекта"
    args_model = ReadFileArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: ReadFileArgs, context: ToolContext) -> ToolResult:
        try:
            target = resolve_project_path(context.project_root, arguments.path)
        except SafetyError as e:
            return ToolResult(success=False, error=str(e))

        if not target.exists():
            return ToolResult(success=False, error=f"Файл не существует: {arguments.path}")
        if not target.is_file():
            return ToolResult(success=False, error=f"Это не файл: {arguments.path}")

        try:
            with open(target, encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            return ToolResult(success=False, error=f"Ошибка чтения: {e}")

        start = (arguments.start_line or 1) - 1
        end = arguments.end_line or len(all_lines)
        selected = all_lines[start:end]

        numbered = "".join(f"{start + i + 1:>5}\t{line}" for i, line in enumerate(selected))
        return ToolResult(success=True, output=limit_output(numbered))
