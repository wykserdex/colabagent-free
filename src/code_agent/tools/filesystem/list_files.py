"""
tools/filesystem/list_files.py — показывает дерево файлов проекта.
Игнорирует .git/.venv/node_modules/runtime по умолчанию, ограничивает глубину
и количество файлов, чтобы не раздуть контекст на большом репозитории.
"""
from pydantic import BaseModel, Field

from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext

_IGNORED_DIRS = {".git", ".venv", "node_modules", "runtime", "__pycache__", ".pytest_cache"}


class ListFilesArgs(BaseModel):
    path: str = "."
    max_depth: int = Field(default=4, ge=1, le=10)
    max_files: int = Field(default=500, ge=1, le=5000)


class ListFilesTool(Tool[ListFilesArgs]):
    name = "filesystem.list_files"
    description = "Показывает дерево файлов и папок внутри проекта"
    args_model = ListFilesArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: ListFilesArgs, context: ToolContext) -> ToolResult:
        try:
            root = resolve_project_path(context.project_root, arguments.path)
        except SafetyError as e:
            return ToolResult(success=False, error=str(e))

        if not root.exists():
            return ToolResult(success=False, error=f"Путь не существует: {arguments.path}")

        lines = []
        count = 0
        base_depth = len(root.parts)

        for dirpath, dirnames, filenames in _walk(root, base_depth, arguments.max_depth):
            dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
            rel_dir = "/".join(dirpath.parts[base_depth:]) or "."
            for fname in sorted(filenames):
                if count >= arguments.max_files:
                    lines.append(f"... остановлено на {arguments.max_files} файлах (лимит)")
                    return ToolResult(success=True, output="\n".join(lines))
                lines.append(f"{rel_dir}/{fname}" if rel_dir != "." else fname)
                count += 1

        return ToolResult(success=True, output="\n".join(lines) if lines else "(пусто)")


def _walk(root, base_depth, max_depth):
    import os
    from pathlib import Path
    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        depth = len(p.parts) - base_depth
        if depth >= max_depth:
            dirnames[:] = []
        yield p, dirnames, filenames
